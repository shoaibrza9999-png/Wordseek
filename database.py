import sqlite3
import json
import random

DB_FILE = 'wordseek.db'

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Users table for global points
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            global_points INTEGER DEFAULT 0
        )
    ''')
    # Group users table for group-specific points
    c.execute('''
        CREATE TABLE IF NOT EXISTS group_users (
            group_id INTEGER,
            user_id INTEGER,
            points INTEGER DEFAULT 0,
            PRIMARY KEY (group_id, user_id)
        )
    ''')
    # Words table
    c.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE,
            meaning_en TEXT,
            meaning_hi TEXT,
            sentence TEXT,
            difficulty INTEGER DEFAULT 1,
            similar_words TEXT,
            rhyming_words TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_points(user_id, username, group_id, points):
    conn = get_connection()
    c = conn.cursor()

    # Update global
    c.execute('''
        INSERT INTO users (user_id, username, global_points)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            global_points = global_points + excluded.global_points
    ''', (user_id, username, points))

    # Update group
    if group_id:
        c.execute('''
            INSERT INTO group_users (group_id, user_id, points)
            VALUES (?, ?, ?)
            ON CONFLICT(group_id, user_id) DO UPDATE SET
                points = points + excluded.points
        ''', (group_id, user_id, points))

    conn.commit()
    conn.close()

def get_top_global(limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT username, global_points FROM users
        ORDER BY global_points DESC LIMIT ?
    ''', (limit,))
    results = c.fetchall()
    conn.close()
    return results

def get_top_group(group_id, limit=10):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT u.username, gu.points
        FROM group_users gu
        JOIN users u ON gu.user_id = u.user_id
        WHERE gu.group_id = ?
        ORDER BY gu.points DESC LIMIT ?
    ''', (group_id, limit))
    results = c.fetchall()
    conn.close()
    return results

def get_user_global_points(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT global_points FROM users WHERE user_id = ?', (user_id,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def get_user_group_points(user_id, group_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT points FROM group_users WHERE user_id = ? AND group_id = ?', (user_id, group_id))
    res = c.fetchone()
    conn.close()
    return res[0] if res else 0

def seed_words(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        words_data = json.load(f)

    conn = get_connection()
    c = conn.cursor()
    for item in words_data:
        # Provide default values for new fields if they don't exist in the json
        difficulty = item.get('difficulty', 1)
        similar_words = json.dumps(item.get('similar_words', []))
        rhyming_words = json.dumps(item.get('rhyming_words', []))

        try:
            c.execute('''
                INSERT OR IGNORE INTO words (word, meaning_en, meaning_hi, sentence, difficulty, similar_words, rhyming_words)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (item['word'].lower(), item['meaning_en'], item['meaning_hi'], item['sentence'], difficulty, similar_words, rhyming_words))
        except Exception as e:
            print(f"Error inserting word {item['word']}: {e}")

    conn.commit()
    conn.close()

def get_random_word():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT word, meaning_en, meaning_hi, sentence, difficulty, similar_words, rhyming_words FROM words ORDER BY RANDOM() LIMIT 1')
    res = c.fetchone()
    conn.close()
    if res:
        return {
            "word": res[0],
            "meaning_en": res[1],
            "meaning_hi": res[2],
            "sentence": res[3],
            "difficulty": res[4],
            "similar_words": json.loads(res[5] if res[5] else '[]'),
            "rhyming_words": json.loads(res[6] if res[6] else '[]')
        }
    return None

def is_valid_word(word):
    return len(word) == 5

if __name__ == '__main__':
    init_db()
