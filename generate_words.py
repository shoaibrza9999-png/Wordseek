import json
import requests
import nltk
from nltk.corpus import words, wordnet
from deep_translator import GoogleTranslator
import time
import random

nltk.download('words', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)

def get_word_details(word):
    # Get meaning and sentence from wordnet
    synsets = wordnet.synsets(word)
    if not synsets:
        return None

    synset = synsets[0]
    meaning_en = synset.definition()

    examples = synset.examples()
    sentence = examples[0] if examples else f"This is an example sentence for {word}."

    # Calculate difficulty score based on wordnet depth (rough proxy for difficulty)
    # Shallow depth = more common concept, Deep depth = more specific/obscure
    try:
        max_depth = max([hyp.max_depth() for hyp in synsets])
        # Scale to roughly 1-10
        difficulty_score = min(max(int(max_depth / 2), 1), 10)
    except:
        difficulty_score = random.randint(1, 5)

    return meaning_en, sentence, difficulty_score

def get_datamuse_info(word):
    similar = []
    rhyming = []

    try:
        # Get similar meaning words
        resp_ml = requests.get(f'https://api.datamuse.com/words?ml={word}&max=3')
        if resp_ml.status_code == 200:
            similar = [item['word'] for item in resp_ml.json()]

        # Get rhyming words
        resp_rel_rhy = requests.get(f'https://api.datamuse.com/words?rel_rhy={word}&max=3')
        if resp_rel_rhy.status_code == 200:
            rhyming = [item['word'] for item in resp_rel_rhy.json()]
    except Exception as e:
        print(f"Error fetching from Datamuse for {word}: {e}")

    return similar, rhyming

def translate_to_hindi(text):
    try:
        return GoogleTranslator(source='en', target='hi').translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return "अनुवाद उपलब्ध नहीं है"

def generate():
    all_words = words.words()
    # Filter 5-letter words, lowercase, no proper nouns (no uppercase first letter in original corpus)
    five_letter_words = [w.lower() for w in all_words if len(w) == 5 and w.islower() and w.isalpha()]

    # Remove duplicates
    five_letter_words = list(set(five_letter_words))

    # Shuffle to get a random assortment
    random.shuffle(five_letter_words)

    target_count = 100
    results = []

    print(f"Starting word generation. Target: {target_count} words.")

    for word in five_letter_words:
        if len(results) >= target_count:
            break

        details = get_word_details(word)
        if not details:
            continue

        meaning_en, sentence, difficulty = details

        similar, rhyming = get_datamuse_info(word)

        # Translate meaning
        meaning_hi = translate_to_hindi(meaning_en)

        results.append({
            "word": word,
            "meaning_en": meaning_en,
            "meaning_hi": meaning_hi,
            "sentence": sentence,
            "difficulty": difficulty,
            "similar_words": similar,
            "rhyming_words": rhyming
        })

        print(f"Generated {len(results)}/{target_count}: {word}")
        # Small delay to not overwhelm APIs
        time.sleep(0.1)

    with open('/app/words.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    print(f"Successfully generated {len(results)} words and saved to words.json")

if __name__ == '__main__':
    generate()
