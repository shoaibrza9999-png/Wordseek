import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
import random
import os
from flask import Flask, request, abort

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8487275902:AAE4rbFbYj9zrcXQQ9oUaVbUgkF0ic439Sg')
bot = telebot.TeleBot(BOT_TOKEN)

app = Flask(__name__)

# Initialize database and seed words
try:
    db.init_db()
    if os.path.exists('words.json'):
        db.seed_words('words.json')
except Exception as e:
    print(f"Error initializing DB: {e}")

# In-memory store for active games
# Note: Since this is going to run on Render which might restart,
# active games might be lost. In a real-world scenario, you would
# store active games in the database.
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
    details = (
        f"The word was: *{word_info['word'].upper()}*\n"
        f"Difficulty: {word_info.get('difficulty', 1)}/10\n\n"
        f"📖 *Meaning (EN):* {word_info['meaning_en']}\n"
        f"📖 *Meaning (HI):* {word_info['meaning_hi']}\n\n"
        f"📝 *Sentence:* {word_info['sentence']}\n"
    )

    similar = word_info.get('similar_words', [])
    if similar:
        details += f"\n🔄 *Similar Words:* {', '.join(similar)}"

    rhyming = word_info.get('rhyming_words', [])
    if rhyming:
        details += f"\n🎵 *Rhyming Words:* {', '.join(rhyming)}"

    return details

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

    difficulty = word_info.get('difficulty', 1)

    bot.send_message(
        chat_id,
        f"🎮 *Wordseek Game Started!*\n\n"
        f"I have picked a random 5-letter word.\n"
        f"Difficulty: {difficulty}/10\n\n"
        f"Start guessing by sending 5-letter words!",
        parse_mode='Markdown'
    )

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

    # Button to see group leaderboard
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

    # Process text
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

    result_str = checkword(text, guessed_word)

    bot.send_message(chat_id, result_str)

    if text == guessed_word:
        tries = game['guess_count']

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

        group_id = chat_id if message.chat.type in ['group', 'supergroup'] else 0

        db.add_points(user.id, username, group_id, points)

        reactions = ["🏆", "🎉", "🎊"]
        try:
            bot.set_message_reaction(chat_id, message.id, [telebot.types.ReactionTypeEmoji(random.choice(reactions))], is_big=False)
        except Exception:
            pass

        details = format_word_details(game['word_info'])
        bot.send_message(chat_id, f"🎉 *{username}* guessed the word in {tries} tries and earned *{points} points*!\n\n{details}", parse_mode='Markdown')

        del active_games[chat_id]

@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    else:
        abort(403)

@app.route('/', methods=['GET'])
def index():
    return 'Bot is running', 200

if __name__ == '__main__':
    bot.remove_webhook()
    # In production, this should be set to the public URL using the setWebhook API or manually
    # bot.set_webhook(url=os.environ.get('RENDER_EXTERNAL_URL'))

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
