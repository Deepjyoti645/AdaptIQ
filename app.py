import os
import json
import re
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from pywebpush import webpush, WebPushException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# ============================================================
# VAPID KEYS FOR PUSH NOTIFICATIONS
# ============================================================

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
VAPID_CLAIMS = {"sub": "mailto:admin@adaptiq.com"}


# ============================================================
# FLASK & PATH SETUP
# ============================================================

script_dir = os.path.dirname(os.path.abspath(__file__))

template_folder_path = os.path.join(script_dir, "templates")
static_folder_path = os.path.join(script_dir, "static")

if not os.path.exists(template_folder_path):
    template_folder_path = "/storage/emulated/0/Download/AdaptIQ/templates"

if not os.path.exists(static_folder_path):
    static_folder_path = "/storage/emulated/0/Download/AdaptIQ/static"

app = Flask(
    __name__,
    template_folder=template_folder_path,
    static_folder=static_folder_path,
    static_url_path="/static"
)

CORS(app)


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-pro-preview"
]


# ============================================================
# DATABASE PATH & INITIALIZATION
# ============================================================

DATABASE_PATH = os.path.join(script_dir, "adaptiq.db")


def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            password TEXT,
            age INTEGER,
            class_num INTEGER,
            country TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_streak (
            user_id INTEGER PRIMARY KEY,
            last_active_date TEXT,
            streak_count INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subject TEXT,
            score INTEGER,
            total INTEGER,
            date TEXT,
            feedback TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_topics_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            topic TEXT,
            correct_count INTEGER DEFAULT 0,
            wrong_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'neutral',
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            subscription_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ============================================================
# HELPER: FETCH USER LEARNING PROFILE
# ============================================================

def get_user_learning_profile(user_id):
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT name, age, class_num, country FROM users WHERE id = ?", (user_id,))
        user_info = cursor.fetchone()

        if not user_info:
            conn.close()
            return {}

        name, age, class_num, country = user_info

        cursor.execute("SELECT topic, status FROM user_topics_performance WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()

        weak_topics = [row[0] for row in rows if row[1] == 'weak']
        strong_topics = [row[0] for row in rows if row[1] == 'strong']

        cursor.execute("SELECT COALESCE(SUM(score), 0), COALESCE(SUM(total), 0), COUNT(id) FROM test_results WHERE user_id = ?", (user_id,))
        score_row = cursor.fetchone()

        total_correct = int(score_row[0]) if score_row and score_row[0] is not None else 0
        total_questions = int(score_row[1]) if score_row and score_row[1] is not None else 0
        total_tests = int(score_row[2]) if score_row and score_row[2] is not None else 0

        accuracy = round((total_correct / total_questions) * 100) if total_questions > 0 else 0

        cursor.execute("SELECT feedback FROM test_results WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
        last_fb_row = cursor.fetchone()
        last_feedback = last_fb_row[0] if last_fb_row else "Take your first mock test to see performance insights here."

        conn.close()

        return {
            "name": name,
            "age": age,
            "classNum": class_num,
            "country": country,
            "weak_topics": weak_topics,
            "strong_topics": strong_topics,
            "overall_accuracy": accuracy,
            "overall_percentage": accuracy,
            "total_score": total_correct,
            "correct_count": total_correct,
            "total_questions": total_questions,
            "total_tests": total_tests,
            "tests_completed": total_tests,
            "last_feedback": last_feedback
        }
    except Exception as e:
        print("Error fetching profile:", e)
        return {}


# ============================================================
# GEMINI API CALL FUNCTION
# ============================================================

def call_gemini_api(prompt_text):
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text}
                    ]
                }
            ]
        }

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

        try:
            with urllib.request.urlopen(req) as response:
                res_body = response.read().decode('utf-8')
                res_json = json.loads(res_body)
                text = res_json['candidates'][0]['content']['parts'][0]['text']
                return text
        except urllib.error.HTTPError as e:
            print(f"Gemini API Error with model {model}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected Error with model {model}: {e}")
            continue

    return None


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()
    age = data.get('age')
    class_num = data.get('classNum')
    country = data.get('country')

    if not name or not password:
        return jsonify({'status': 'error', 'message': 'Name and Password are required'}), 400

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO users (name, password, age, class_num, country) VALUES (?, ?, ?, ?, ?)",
                       (name, password, age, class_num, country))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success',
            'user': {
                'id': user_id,
                'name': name,
                'age': age,
                'classNum': class_num,
                'country': country
            }
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Username already exists! Please login.'}), 400


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, age, class_num, country FROM users WHERE LOWER(name) = LOWER(?) AND password = ?", (name, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify({
            'status': 'success',
            'user': {
                'id': user[0],
                'name': user[1],
                'age': user[2],
                'classNum': user[3],
                'country': user[4]
            }
        })
    else:
        return jsonify({'status': 'error', 'message': 'Invalid Name or Password'}), 401


@app.route('/api/streak', methods=['GET'])
def get_streak():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User ID required'}), 400

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    today_str = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT last_active_date, streak_count FROM user_streak WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO user_streak (user_id, last_active_date, streak_count) VALUES (?, ?, ?)",
                       (user_id, today_str, 1))
        conn.commit()
        streak = 1
    else:
        last_date_str, count = row
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()

        if today == last_date:
            streak = count
        elif today == last_date + timedelta(days=1):
            streak = count + 1
            cursor.execute("UPDATE user_streak SET last_active_date = ?, streak_count = ? WHERE user_id = ?",
                           (today_str, streak, user_id))
            conn.commit()
        else:
            streak = 1
            cursor.execute("UPDATE user_streak SET last_active_date = ?, streak_count = ? WHERE user_id = ?",
                           (today_str, streak, user_id))
            conn.commit()

    conn.close()
    return jsonify({'status': 'success', 'streak': streak})


@app.route('/api/generate-test', methods=['POST'])
def generate_test():
    data = request.json or {}
    user_id = data.get('user_id')
    subject = data.get('subject', 'Mathematics')
    num_questions = data.get('num_questions', 5)
    difficulty = data.get('difficulty', 'Medium')
    topics = data.get('topics', [])
    class_num = data.get('classNum', 8)

    profile = get_user_learning_profile(user_id) if user_id else {}

    prompt = f"""
    You are an AI Exam Generator for AdaptIQ platform.
    Generate exactly {num_questions} Multiple Choice Questions (MCQs) for Class {class_num} level in JSON format.
    
    Student context:
    - Name: {profile.get('name', 'Student')}
    - Subject: {subject}
    - Difficulty: {difficulty}
    - Specific Topics: {', '.join(topics) if topics else 'General Syllabus'}
    - Weak Topics to include if relevant: {', '.join(profile.get('weak_topics', []))}
    
    CRITICAL RULES:
    1. Output ONLY raw valid JSON array of objects. Do NOT use markdown ```json codeblocks.
    2. Do NOT use LaTeX or single backslashes in math expressions. Write plain text (e.g. use "angle B" instead of "\\angle B", use "y/2" instead of "\\frac{{y}}{{2}}").
    
    JSON Format:
    [
      {{
        "id": 1,
        "question": "Question text here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_answer_index": 0,
        "topic": "Topic Name"
      }}
    ]
    """

    ai_raw = call_gemini_api(prompt)

    if not ai_raw:
        return jsonify({'status': 'error', 'message': 'Failed to reach AI server'}), 500

    clean_raw = ai_raw.strip()
    if clean_raw.startswith("```json"):
        clean_raw = clean_raw[7:]
    if clean_raw.startswith("```"):
        clean_raw = clean_raw[3:]
    if clean_raw.endswith("```"):
        clean_raw = clean_raw[:-3]
    clean_raw = clean_raw.strip()

    clean_raw = re.sub(r'\\([^\/\\\"bfnrtu])', r'\\\\\\\\1', clean_raw)

    try:
        questions = json.loads(clean_raw, strict=False)
        return jsonify({'status': 'success', 'questions': questions})
    except Exception as e:
        print("JSON parse error:", e, "Raw output:", ai_raw)
        return jsonify({'status': 'error', 'message': 'Invalid questions JSON from AI'}), 500


@app.route('/api/submit-test', methods=['POST'])
def submit_test():
    data = request.json or {}
    user_id = data.get('user_id')
    subject = data.get('subject', 'General')
    questions = data.get('questions', [])
    user_answers = data.get('user_answers', {})

    if not user_id:
        return jsonify({'status': 'error', 'message': 'User ID required'}), 400

    total = len(questions)
    correct_count = 0

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    for idx, q in enumerate(questions):
        correct_idx = q.get('correct_answer_index')
        user_idx = user_answers.get(str(idx))
        topic = q.get('topic', subject)

        is_correct = (user_idx is not None and int(user_idx) == int(correct_idx))
        if is_correct:
            correct_count += 1

        cursor.execute("SELECT id, correct_count, wrong_count FROM user_topics_performance WHERE user_id = ? AND topic = ?", (user_id, topic))
        row = cursor.fetchone()

        if row:
            row_id, c_cnt, w_cnt = row
            if is_correct:
                c_cnt += 1
            else:
                w_cnt += 1
            status = 'strong' if c_cnt >= (w_cnt + 1) else 'weak'
            cursor.execute("UPDATE user_topics_performance SET correct_count = ?, wrong_count = ?, status = ? WHERE id = ?", (c_cnt, w_cnt, status, row_id))
        else:
            c_cnt = 1 if is_correct else 0
            w_cnt = 0 if is_correct else 1
            status = 'strong' if is_correct else 'weak'
            try:
                cursor.execute("INSERT INTO user_topics_performance (user_id, topic, correct_count, wrong_count, status) VALUES (?, ?, ?, ?, ?)",
                               (user_id, topic, c_cnt, w_cnt, status))
            except sqlite3.IntegrityError:
                cursor.execute("UPDATE user_topics_performance SET correct_count = correct_count + ?, wrong_count = wrong_count + ? WHERE topic = ?",
                               (c_cnt, w_cnt, topic))

    percentage = round((correct_count / total) * 100) if total > 0 else 0
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    profile = get_user_learning_profile(user_id)
    
    feedback_prompt = f"""
    You are a friendly mascot AI tutor for {profile.get('name', 'Student')}.
    Class: {profile.get('classNum', 8)}, Country: {profile.get('country', 'India')}.
    Student scored {correct_count}/{total} ({percentage}%) in a {subject} test.
    Provide a warm, personalized 2-sentence encouraging feedback and study advice.
    Do NOT mention 'Gemini' or 'AI'.
    """

    feedback = call_gemini_api(feedback_prompt) or f"Great effort {profile.get('name', '')}! Keep practicing to build speed and accuracy."

    cursor.execute("""
        INSERT INTO test_results (user_id, subject, score, total, date, feedback)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, subject, correct_count, total, today_str, feedback))

    conn.commit()
    conn.close()

    updated_profile = get_user_learning_profile(user_id)

    return jsonify({
        'status': 'success',
        'score': correct_count,
        'total': total,
        'percentage': percentage,
        'feedback': feedback,
        'analytics': updated_profile
    })


@app.route('/api/performance', methods=['GET'])
def get_performance():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'User ID required'}), 400

    profile = get_user_learning_profile(user_id)

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT subject, score, total, date, feedback FROM test_results WHERE user_id = ? ORDER BY id DESC LIMIT 10", (user_id,))
    rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            'subject': r[0],
            'score': r[1],
            'total': r[2],
            'date': r[3],
            'feedback': r[4]
        })

    conn.close()

    total_correct = profile.get('total_score', 0)
    total_qs = profile.get('total_questions', 0)
    total_tests = profile.get('total_tests', 0)
    accuracy = profile.get('overall_accuracy', 0)

    return jsonify({
        'status': 'success',
        'overall_accuracy': accuracy,
        'overall_percentage': accuracy,
        'summary_7days': {
            'overall_percentage': accuracy,
            'total_tests': total_tests,
            'total_points': total_correct,
            'total_questions': total_qs
        },
        'results': results
    })


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    message = data.get('message', '')
    user_id = data.get('user_id')

    if not message:
        return jsonify({'status': 'error', 'message': 'Empty message'}), 400

    profile = get_user_learning_profile(user_id) if user_id else {}

    system_prompt = f"""
    You are AdaptIQ AI Tutor, an intelligent, empathetic, and highly personalized mentor.
    
    Student Details:
    - Name: {profile.get('name', 'Student')}
    - Age: {profile.get('age', 'Unknown')}
    - Class/Grade: {profile.get('classNum', 'Unknown')}
    - Country: {profile.get('country', 'Unknown')}
    - Weak Topics: {', '.join(profile.get('weak_topics', [])) if profile.get('weak_topics') else 'None'}
    - Strong Topics: {', '.join(profile.get('strong_topics', [])) if profile.get('strong_topics') else 'None'}
    - Recent Test Accuracy: {profile.get('overall_accuracy', 0)}%
    
    Rules:
    1. Address the student warmly using their name ({profile.get('name', 'Learner')}).
    2. Tailor your explanations according to Class {profile.get('classNum', 8)} level and curriculum context of {profile.get('country', 'India')}.
    3. Keep responses clear, motivating, and easy to understand. Use bullet points or step-by-step explanations for doubts.
    4. Never say 'I am Gemini' or 'Google AI'. Always refer to yourself as AdaptIQ AI Tutor.
    
    User Query: {message}
    """

    reply = call_gemini_api(system_prompt) or f"Hello {profile.get('name', 'Learner')}! I am here to help you solve any doubt."

    return jsonify({'status': 'success', 'reply': reply})


# ============================================================
# PUSH NOTIFICATION ROUTES
# ============================================================

@app.route('/api/subscribe-push', methods=['POST'])
def subscribe_push():
    data = request.json or {}
    user_id = data.get('user_id')
    subscription = data.get('subscription')

    if not user_id or not subscription:
        return jsonify({'status': 'error', 'message': 'Invalid subscription payload'}), 400

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    sub_json = json.dumps(subscription)
    
    cursor.execute("SELECT id FROM push_subscriptions WHERE user_id = ? AND subscription_json = ?", (user_id, sub_json))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO push_subscriptions (user_id, subscription_json) VALUES (?, ?)", (user_id, sub_json))
        conn.commit()

    conn.close()
    return jsonify({'status': 'success', 'message': 'Push notification subscription saved.'})


@app.route('/api/send-push', methods=['POST'])
def send_push():
    data = request.json or {}
    user_id = data.get('user_id')
    title = data.get('title', 'AdaptIQ Daily Alert 🚀')
    message = data.get('message', 'Time for a quick practice session!')
    icon = data.get('icon', '/static/images/Normal.png')

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT subscription_json FROM push_subscriptions WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({'status': 'error', 'message': 'No push subscription found'}), 404

    payload = json.dumps({
        "title": title,
        "body": message,
        "icon": icon,
        "url": "/"
    })

    sent_count = 0
    for r in rows:
        sub_info = json.loads(r[0])
        try:
            webpush(
                subscription_info=sub_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            sent_count += 1
        except WebPushException as ex:
            print("WebPush Error:", ex)

    return jsonify({'status': 'success', 'sent_count': sent_count})


@app.route('/api/check-inactivity-push', methods=['POST'])
def check_inactivity_push():
    data = request.json or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'status': 'error', 'message': 'User ID required'}), 400

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT last_active_date FROM user_streak WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'status': 'error', 'message': 'Streak data not found'}), 404

    last_active_str = row[0]
    last_active = datetime.strptime(last_active_str, "%Y-%m-%d").date()
    days_absent = (datetime.now().date() - last_active).days

    title = ""
    message = ""
    icon = "/static/images/Normal.png"

    if days_absent == 3:
        title = "I miss you! 🥺"
        message = "3 din ho gaye aapne practice nahi ki. Aao thoda padh lo!"
        icon = "/static/images/Little_Sad.png"
    elif days_absent == 5:
        title = "Main bohot udaas hu... 😭"
        message = "5 din se aap gayab ho! Streak break ho jayegi."
        icon = "/static/images/Very_Sad.png"
    elif days_absent >= 7:
        title = "Hopeless... 💔"
        message = "Aapne padhai chhod di kya? Please wapas aao!"
        icon = "/static/images/Very_Sad.png"

    if message:
        req_data = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "icon": icon
        }
        with app.test_client() as client:
            client.post('/api/send-push', json=req_data)
        return jsonify({'status': 'success', 'message': 'Inactivity notification triggered', 'days_absent': days_absent})

    return jsonify({'status': 'info', 'message': 'User active recently, no notification sent.', 'days_absent': days_absent})


@app.route('/api/send-score-push', methods=['POST'])
def send_score_push():
    data = request.json or {}
    user_id = data.get('user_id')
    score_percentage = data.get('percentage', 0)

    if not user_id:
        return jsonify({'status': 'error', 'message': 'User ID required'}), 400

    if score_percentage >= 80:
        title = "Superb Performance! 🎉"
        message = f"Wow! Aapne test mein {score_percentage}% score kiya! Keep it up!"
        icon = "/static/images/Very_Happy.png"
    elif score_percentage >= 50:
        title = "Good Try! 👍"
        message = f"Aapne {score_percentage}% score kiya hai. Thodi aur mehnat se 80%+ ho jayega!"
        icon = "/static/images/Normal.png"
    else:
        title = "Udaas mat ho! 💪"
        message = f"Score: {score_percentage}%. Koi baat nahi, dobara attempt karo aur concepts clear karo!"
        icon = "/static/images/Little_Sad.png"

    req_data = {
        "user_id": user_id,
        "title": title,
        "message": message,
        "icon": icon
    }
    with app.test_client() as client:
        client.post('/api/send-push', json=req_data)

    return jsonify({'status': 'success', 'message': 'Score notification sent successfully!'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
