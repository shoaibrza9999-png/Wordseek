import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
import random
import os

# You will need to replace 'YOUR_BOT_TOKEN' with your actual bot token
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize database and seed words
db.init_db()
if os.path.exists('words.json'):
    db.seed_words('words.json')

# In-memory store for active games
# Structure: { chat_id: {'word_info': {...}, 'guesses': set(), 'guess_count': 0} }
active_games = {}

def checkword(userword, guessedword):
    a = ""
    for x in range(0, 5):
        if userword[x] == guessedword[x]:
            a += "🟩 "
        elif userword[x] in guessedword:
            a += "🟨 "
        else:
            a += "🟥 "
    return a

def format_word_details(word_info):
    return (
        f"The word was: *{word_info['word'].upper()}*\n\n"
        f"📖 *Meaning (EN):* {word_info['meaning_en']}\n"
        f"📖 *Meaning (HI):* {word_info['meaning_hi']}\n\n"
        f"📝 *Sentence:* {word_info['sentence']}"
    )

@bot.message_handler(commands=['new'])
def start_new_game(message):
    chat_id = message.chat.id

    if chat_id in active_games:
        bot.reply_to(message, "A game is already running in this chat! Send a 5-letter word or use /end to stop it.")
        return

    word_info = db.get_random_word()
    if not word_info:
        bot.reply_to(message, "No words available in the database. Please add some!")
        return

    active_games[chat_id] = {
        'word_info': word_info,
        'guesses': set(),
        'guess_count': 0
    }

    bot.send_message(chat_id, "🎮 *Wordseek Game Started!*\n\nI have picked a random 5-letter word.\nStart guessing by sending 5-letter words!", parse_mode='Markdown')

@bot.message_handler(commands=['end'])
def end_game(message):
    chat_id = message.chat.id

    if chat_id not in active_games:
        bot.reply_to(message, "No active game in this chat. Start one with /new")
        return

    word_info = active_games[chat_id]['word_info']
    details = format_word_details(word_info)

    bot.send_message(chat_id, f"Game ended by {message.from_user.first_name}.\n\n{details}", parse_mode='Markdown')
    del active_games[chat_id]

@bot.message_handler(commands=['leaderboard'])
def show_leaderboard(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Get global leaderboard
    top_global = db.get_top_global(10)

    msg = "🏆 *Global Leaderboard (Top 10)*\n\n"
    if not top_global:
        msg += "No players yet.\n"
    else:
        for i, (username, points) in enumerate(top_global, 1):
            msg += f"{i}. {username if username else 'Unknown'} - {points} pts\n"

    # Add user's score
    user_points = db.get_user_global_points(user_id)
    msg += f"\n👉 *Your Global Points:* {user_points}"

    # Button to see group leaderboard (only makes sense in groups)
    markup = InlineKeyboardMarkup()
    if message.chat.type in ['group', 'supergroup']:
        btn = InlineKeyboardButton("Group Leaderboard", callback_data=f"group_lb_{chat_id}")
        markup.add(btn)

    bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('group_lb_'))
def group_leaderboard_callback(call):
    try:
        group_id = int(call.data.split('_')[2])
    except ValueError:
        return

    top_group = db.get_top_group(group_id, 10)
    msg = "🏆 *Group Leaderboard (Top 10)*\n\n"

    if not top_group:
        msg += "No players in this group yet.\n"
    else:
        for i, (username, points) in enumerate(top_group, 1):
            msg += f"{i}. {username if username else 'Unknown'} - {points} pts\n"

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_guess(message):
    chat_id = message.chat.id

    if chat_id not in active_games:
        return

    # Process text: remove spaces from ends, check length
    text = message.text.strip()
    if len(text) != 5:
        return

    text = text.lower()
    game = active_games[chat_id]

    # Check if already guessed
    if text in game['guesses']:
        return

    game['guesses'].add(text)
    game['guess_count'] += 1

    guessed_word = game['word_info']['word']

    # Generate the visual feedback string
    result_str = checkword(text, guessed_word)

    # Send result string without replying
    bot.send_message(chat_id, result_str)

    # Check if correct
    if text == guessed_word:
        # User guessed it correctly!
        tries = game['guess_count']

        # Calculate points based on tries (1-5 points, e.g. 1 try = 5 pts, 5+ tries = 1 pt)
        if tries == 1:
            points = 5
        elif tries == 2:
            points = 4
        elif tries == 3:
            points = 3
        elif tries == 4:
            points = 2
        else:
            points = 1

        user = message.from_user
        username = user.username or user.first_name

        # Determine group_id. If private chat, group_id is 0 or chat_id. Let's use 0 for private chats
        group_id = chat_id if message.chat.type in ['group', 'supergroup'] else 0

        # Add points to DB
        db.add_points(user.id, username, group_id, points)

        # React to message randomly
        reactions = ["🏆", "🎉", "🎊"]
        # Note: reactions in telegram bot api requires specific setup (can only react in chats where bot is admin etc.)
        # As an alternative if reactions are not supported, we can send a reply
        try:
            bot.set_message_reaction(chat_id, message.id, [telebot.types.ReactionTypeEmoji(random.choice(reactions))], is_big=False)
        except Exception as e:
            # Fallback if bot can't react (e.g. not admin, or api limit)
            print(f"Failed to react: {e}")

        # Send word details
        details = format_word_details(game['word_info'])
        bot.send_message(chat_id, f"🎉 *{username}* guessed the word in {tries} tries and earned *{points} points*!\n\n{details}", parse_mode='Markdown')

        # End game
        del active_games[chat_id]

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
