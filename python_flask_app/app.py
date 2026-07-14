import os
import json
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "flask_secret_key_123_abc")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "ai_question_generator")

mysql_available = False
db_type = 'sqlite'
db_error = None

# Programmatic driver installation if not installed
try:
    import mysql.connector
    mysql_available = True
except ImportError:
    print("mysql-connector-python not found. Attempting driver installation...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "mysql-connector-python==8.3.0", "--break-system-packages"])
        import mysql.connector
        mysql_available = True
    except Exception as e:
        print("Could not programmatically install mysql-connector-python:", e)
        db_error = f"MySQL driver install failed: {str(e)}"

# Attempt database connection
if mysql_available and DB_HOST:
    try:
        # Step 1: Connect to server without database to ensure schema is initialized
        conn_init = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            autocommit=True
        )
        cursor_init = conn_init.cursor()
        cursor_init.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor_init.close()
        conn_init.close()
        
        # Step 2: Establish connection to database
        conn_test = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True
        )
        conn_test.close()
        db_type = 'mysql'
        print("Successfully connected to MySQL database!")
    except Exception as e:
        print("MySQL connection failed. Falling back to SQLite. Error:", e)
        db_error = f"MySQL Connection Failed: {str(e)}"
else:
    if not DB_HOST:
        db_error = "MySQL connection variables are not configured in settings."
    print("Running with SQLite fallback.")

# Database Query Helper
def db_query(query, params=None, is_write=False, fetch_one=False):
    if params is None:
        params = ()
        
    if db_type == 'mysql':
        # Adapt placeholder ? to %s for MySQL compatibility
        mysql_query = query.replace('?', '%s')
        
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(mysql_query, params)
            if is_write:
                conn.commit()
                lastrowid = cursor.lastrowid
                return lastrowid
            else:
                if fetch_one:
                    return cursor.fetchone()
                else:
                    return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()
    else:
        # SQLite Connection
        conn = sqlite3.connect("ai_question_generator.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if is_write:
                conn.commit()
                lastrowid = cursor.lastrowid
                return lastrowid
            else:
                if fetch_one:
                    row = cursor.fetchone()
                    return dict(row) if row else None
                else:
                    rows = cursor.fetchall()
                    return [dict(r) for r in rows]
        finally:
            cursor.close()
            conn.close()

# Ensure database tables exist
def init_db():
    try:
        if db_type == 'mysql':
            db_query("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) NOT NULL DEFAULT 'Educator Pro',
                    email VARCHAR(100) NOT NULL,
                    grade_level VARCHAR(50) DEFAULT 'High School',
                    default_subject VARCHAR(100) DEFAULT 'General Science',
                    questions_generated INT DEFAULT 0,
                    quizzes_taken INT DEFAULT 0,
                    average_score FLOAT DEFAULT 0.0
                )
            """, is_write=True)
            
            db_query("""
                CREATE TABLE IF NOT EXISTS question_sets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    topic VARCHAR(150) NOT NULL,
                    difficulty VARCHAR(50) NOT NULL,
                    question_type VARCHAR(50) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """, is_write=True)
            
            db_query("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    set_id INT NOT NULL,
                    question_text TEXT NOT NULL,
                    options TEXT, -- Stored as JSON string
                    correct_answer VARCHAR(255) NOT NULL,
                    explanation TEXT,
                    FOREIGN KEY (set_id) REFERENCES question_sets(id) ON DELETE CASCADE
                )
            """, is_write=True)
        else:
            db_query("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL DEFAULT 'Educator Pro',
                    email TEXT NOT NULL,
                    grade_level TEXT DEFAULT 'High School',
                    default_subject TEXT DEFAULT 'General Science',
                    questions_generated INTEGER DEFAULT 0,
                    quizzes_taken INTEGER DEFAULT 0,
                    average_score REAL DEFAULT 0.0
                )
            """, is_write=True)
            
            db_query("""
                CREATE TABLE IF NOT EXISTS question_sets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    question_type TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """, is_write=True)
            
            db_query("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    set_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    options TEXT, -- Stored as JSON string
                    correct_answer TEXT NOT NULL,
                    explanation TEXT,
                    FOREIGN KEY (set_id) REFERENCES question_sets(id) ON DELETE CASCADE
                )
            """, is_write=True)
        
        # Seed default profile if not exists
        count_row = db_query("SELECT COUNT(*) as count FROM user_profile", fetch_one=True)
        if count_row and count_row['count'] == 0:
            db_query(
                "INSERT INTO user_profile (email, username) VALUES (?, ?)",
                ("mohammad.rihan31@gmail.com", "Educator Pro"),
                is_write=True
            )
            
    except Exception as e:
        print("Database initialization error:", e)

# Initialize database on startup
init_db()

# Call Gemini AI to generate structured questions
def generate_questions_gemini(topic, difficulty, question_type, count):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in the Secrets/environment settings.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    # Prepare prompt format and rules
    if question_type == 'multiple-choice':
        type_instructions = 'The question type is multiple-choice. Each question must have exactly 4 distinct options. The correctAnswer field must match one of these options exactly.'
    elif question_type == 'true-false':
        type_instructions = "The question type is true-false. Each question must have exactly 2 options: ['True', 'False']. The correctAnswer field must be either 'True' or 'False'."
    elif question_type == 'mixed':
        type_instructions = "The question type is mixed. Generate a combination of multiple-choice, true-false, and short-answer questions. For each question, set the 'type' field correctly: 'multiple-choice' (must have exactly 4 options, correctAnswer must be one of them), 'true-false' (must have exactly ['True', 'False'] options, correctAnswer must be 'True' or 'False'), or 'short-answer' (options array must be empty [], correctAnswer must be a concise response of 1-4 words)."
    else:
        type_instructions = 'The question type is short-answer. No options are required. The correctAnswer field should be a concise correct response (usually 1-4 words).'

    system_instruction = f"""You are an expert educator and exam designer. Your job is to generate highly accurate, clear, and age-appropriate educational questions.
{type_instructions}
Ensure questions are factual, engaging, and have well-reasoned explanations for the correct answers.
Return strictly valid JSON that conforms to the requested schema."""

    prompt = f"""Generate exactly {count} educational questions about the topic "{topic}" at a "{difficulty}" difficulty level."""

    print("Sending request to Gemini API with prompt:", prompt)
    print("System instruction:", system_instruction)
    
    # Structured Schema payload for Gemini API
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "systemInstruction": {
            "parts": [{
                "text": system_instruction
            }]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "topic": {"type": "STRING"},
                    "difficulty": {"type": "STRING"},
                    "questions": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "question_text": {"type": "STRING"},
                                "options": {
                                    "type": "ARRAY",
                                    "items": {"type": "STRING"}
                                },
                                "correct_answer": {"type": "STRING"},
                                "explanation": {"type": "STRING"}
                            },
                            "required": ["question_text", "correct_answer", "explanation"]
                        }
                    }
                },
                "required": ["topic", "difficulty", "questions"]
            }
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))

    try:
        candidates = result.get('candidates', [])
        if not candidates:
            raise ValueError("No response candidate from Gemini.")
        parts = candidates[0].get('content', {}).get('parts', [])
        if not parts:
            raise ValueError("No parts found in response content.")
        raw_text = parts[0].get('text', '')
        return json.loads(raw_text)
    except Exception as e:
        print("Gemini response formatting error. Raw result:", result)
        raise e

# Call OpenAI as a secondary option if configured and preferred
def generate_questions_openai(topic, difficulty, question_type, count):
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""
    Generate exactly {count} educational questions about the topic "{topic}" at a "{difficulty}" difficulty level.
    The question format must be "{question_type}".
    
    Return strictly valid JSON format with the following schema:
    {{
      "topic": "{topic}",
      "difficulty": "{difficulty}",
      "questions": [
        {{
          "question_text": "The text of the question?",
          "options": ["Option A", "Option B", "Option C", "Option D"],  // List of 4 elements for multiple-choice, ['True', 'False'] for true-false, or leave empty/None for short-answer
          "correct_answer": "The correct option text exactly, or a short answers phrase",
          "explanation": "Why this answer is correct"
        }}
      ]
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are an expert exam curriculum designer."},
            {"role": "user", "content": prompt}
        ]
    )
    raw_json = response.choices[0].message.content
    return json.loads(raw_json)


@app.route('/')
def index():
    profile = None
    try:
        profile = db_query("SELECT * FROM user_profile LIMIT 1", fetch_one=True)
    except Exception as e:
        print("Error fetching profile:", e)

    # Provide fallback if db is locked or empty
    if not profile:
        profile = {
            "username": "Educator Pro",
            "email": "user@example.com",
            "grade_level": "High School",
            "default_subject": "General Science",
            "questions_generated": 0,
            "quizzes_taken": 0,
            "average_score": 0.0
        }
        
    return render_template('index.html', profile=profile, db_type=db_type, db_error=db_error)


@app.route('/generate', methods=['POST'])
def generate():
    topic = request.form.get('topic')
    difficulty = request.form.get('difficulty', 'Medium')
    question_type = request.form.get('question_type', 'multiple-choice')
    count = int(request.form.get('count', 5))
    
    if not topic:
        flash("Please specify a topic.")
        return redirect(url_for('index'))
        
    try:
        # Prioritize Gemini API if the key exists, otherwise fall back to OpenAI API
        if os.getenv("GEMINI_API_KEY"):
            data = generate_questions_gemini(topic, difficulty, question_type, count)
        elif os.getenv("OPENAI_API_KEY"):
            data = generate_questions_openai(topic, difficulty, question_type, count)
        else:
            raise ValueError("No AI API key found. Please set GEMINI_API_KEY or OPENAI_API_KEY in the environment secrets.")
        
        # Save generated set
        set_id = db_query(
            "INSERT INTO question_sets (topic, difficulty, question_type) VALUES (?, ?, ?)",
            (topic, difficulty, question_type),
            is_write=True
        )
        
        # Insert each question
        for q in data.get('questions', []):
            options_str = json.dumps(q.get('options')) if q.get('options') else None
            db_query(
                "INSERT INTO questions (set_id, question_text, options, correct_answer, explanation) VALUES (?, ?, ?, ?, ?)",
                (set_id, q.get('question_text'), options_str, q.get('correct_answer'), q.get('explanation')),
                is_write=True
            )
            
        # Update profile stats
        db_query(
            "UPDATE user_profile SET questions_generated = questions_generated + ?",
            (len(data.get('questions', [])),),
            is_write=True
        )
        
        flash(f"Successfully generated {len(data.get('questions', []))} questions!")
        return redirect(url_for('saved_sets'))
        
    except Exception as e:
        flash(f"Error generating questions: {str(e)}")
        return redirect(url_for('index'))


@app.route('/saved')
def saved_sets():
    sets = []
    try:
        rows = db_query("SELECT * FROM question_sets ORDER BY created_at DESC")
        for r in rows:
            s = dict(r)
            q_rows = db_query("SELECT * FROM questions WHERE set_id = ?", (s['id'],))
            questions = []
            for qr in q_rows:
                q = dict(qr)
                if q['options']:
                    if isinstance(q['options'], str):
                        q['options'] = json.loads(q['options'])
                questions.append(q)
            s['questions'] = questions
            sets.append(s)
    except Exception as e:
        print("Error fetching sets:", e)
        
    return render_template('saved.html', sets=sets, db_type=db_type, db_error=db_error)


@app.route('/delete-set/<int:set_id>')
def delete_set(set_id):
    try:
        db_query("DELETE FROM question_sets WHERE id = ?", (set_id,), is_write=True)
        flash("Question set deleted successfully.")
    except Exception as e:
        flash(f"Failed to delete: {str(e)}")
        
    return redirect(url_for('saved_sets'))


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        username = request.form.get('username')
        grade_level = request.form.get('grade_level')
        default_subject = request.form.get('default_subject')
        
        db_query("""
            UPDATE user_profile 
            SET username = ?, grade_level = ?, default_subject = ?
        """, (username, grade_level, default_subject), is_write=True)
        flash("Profile updated successfully!")
        return redirect(url_for('profile'))
        
    profile_data = db_query("SELECT * FROM user_profile LIMIT 1", fetch_one=True)
    return render_template('profile.html', profile=profile_data, db_type=db_type, db_error=db_error)


@app.route('/api/quiz-taken', methods=['POST'])
def quiz_taken():
    try:
        data = request.get_json() or {}
        score = float(data.get('score', 0))
        total = float(data.get('total', 5))
        if total == 0:
            total = 1
            
        percentage = (score / total) * 100.0
        
        # Get current stats
        profile_data = db_query("SELECT * FROM user_profile LIMIT 1", fetch_one=True)
        if profile_data:
            current_quizzes = int(profile_data.get('quizzes_taken', 0))
            current_avg = float(profile_data.get('average_score', 0.0))
            
            new_quizzes = current_quizzes + 1
            new_avg = ((current_avg * current_quizzes) + percentage) / new_quizzes
            
            db_query("""
                UPDATE user_profile 
                SET quizzes_taken = ?, average_score = ?
                WHERE id = ?
            """, (new_quizzes, round(new_avg, 1), profile_data['id']), is_write=True)
            
            return jsonify({
                "status": "success",
                "quizzes_taken": new_quizzes,
                "average_score": round(new_avg, 1)
            })
        return jsonify({"status": "error", "message": "Profile not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    # Standard fallback port, our start-orchestration script will specify port 3000
    port = int(os.getenv("PORT", 3000))
    app.run(host='0.0.0.0', port=port, debug=True)
