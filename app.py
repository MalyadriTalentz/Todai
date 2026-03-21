from flask import Flask, render_template, request, jsonify, session, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
from functools import wraps
import json
import os
import uuid
import sqlite3
from dotenv import load_dotenv
import base64

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here-change-in-production')
CORS(app)

# Database initialization
def init_db():
    conn = sqlite3.connect('todai.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT DEFAULT 'User',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Todos table
    c.execute('''
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            text TEXT NOT NULL,
            completed BOOLEAN DEFAULT 0,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Focus sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS focus_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            duration INTEGER NOT NULL,
            completed BOOLEAN DEFAULT 0,
            session_date DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Calendar events table
    c.execute('''
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            title TEXT NOT NULL,
            date DATE NOT NULL,
            time TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Flashcards table
    c.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            topic TEXT,
            subject TEXT,
            cards TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # PYQ Questions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS pyq_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            topic TEXT,
            subject TEXT,
            difficulty TEXT DEFAULT 'medium',
            questions TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # Schedules table
    c.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            goal TEXT,
            routine TEXT,
            subjects TEXT,
            preferences TEXT,
            schedule_data TEXT,
            tips TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # User settings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            clock_format TEXT DEFAULT '24h',
            dashboard_name TEXT DEFAULT 'User',
            show_quotes BOOLEAN DEFAULT 1,
            show_streak BOOLEAN DEFAULT 1,
            show_spotify BOOLEAN DEFAULT 1,
            current_theme TEXT DEFAULT 'default',
            theme_category TEXT DEFAULT 'gradients',
            custom_background TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Daily quotes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            quote TEXT,
            date DATE DEFAULT CURRENT_DATE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Custom backgrounds table
    c.execute('''
        CREATE TABLE IF NOT EXISTS custom_backgrounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            name TEXT,
            image_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Initialize Groq client for AI features
try:
    from groq import Groq
    groq_api_key = os.getenv('GROQ_API_KEY')
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY environment variable not set")
    groq_client = Groq(api_key=groq_api_key)
    AI_AVAILABLE = True
    print("[OK] Groq AI initialized successfully!")
except Exception as e:
    print(f"[ERROR] Error initializing Groq: {e}")
    print("Installing/updating Groq library might help: pip install --upgrade groq")
    groq_client = None
    AI_AVAILABLE = False

# Database helper functions
def get_db():
    conn = sqlite3.connect('todai.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_id():
    """Get or create user ID from session"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        # Create user record
        conn = get_db()
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (id) VALUES (?)', (session['user_id'],))
        c.execute('INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)', (session['user_id'],))
        conn.commit()
        conn.close()
    return session['user_id']

# Curated themes
THEMES = {
    'gradients': [
        {'id': 'gradient-1', 'name': 'Midnight', 'url': 'https://images.unsplash.com/photo-1557683316-973673baf926?w=1920&q=80', 'category': 'gradients'},
        {'id': 'gradient-2', 'name': 'Sunset', 'url': 'https://images.unsplash.com/photo-1579546929518-9e396f3cc809?w=1920&q=80', 'category': 'gradients'},
        {'id': 'gradient-3', 'name': 'Ocean', 'url': 'https://images.unsplash.com/photo-1558591710-4b4a1ae0f04d?w=1920&q=80', 'category': 'gradients'},
        {'id': 'gradient-4', 'name': 'Aurora', 'url': 'https://images.unsplash.com/photo-1557682250-33bd709cbe85?w=1920&q=80', 'category': 'gradients'},
    ],
    'lofi': [
        {'id': 'lofi-1', 'name': 'Cozy Room', 'url': 'https://images.unsplash.com/photo-1513519245088-0e12902e35a6?w=1920&q=80', 'category': 'lofi'},
        {'id': 'lofi-2', 'name': 'Rainy Window', 'url': 'https://images.unsplash.com/photo-1515694346937-94d85e41e6f0?w=1920&q=80', 'category': 'lofi'},
        {'id': 'lofi-3', 'name': 'Study Desk', 'url': 'https://images.unsplash.com/photo-1507842217343-583bb7270b66?w=1920&q=80', 'category': 'lofi'},
        {'id': 'lofi-4', 'name': 'Coffee Shop', 'url': 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=1920&q=80', 'category': 'lofi'},
        {'id': 'lofi-5', 'name': 'City Night', 'url': 'https://images.unsplash.com/photo-1519501025264-65ba15a82390?w=1920&q=80', 'category': 'lofi'},
    ],
    'travel': [
        {'id': 'travel-1', 'name': 'Tokyo Night', 'url': 'https://images.unsplash.com/photo-1503899036084-c55cdd92da26?w=1920&q=80', 'category': 'travel'},
        {'id': 'travel-2', 'name': 'Snowy Forest', 'url': 'https://images.unsplash.com/photo-1483664852095-d6cc6870705d?w=1920&q=80', 'category': 'travel'},
        {'id': 'travel-3', 'name': 'Mountains', 'url': 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=1920&q=80', 'category': 'travel'},
        {'id': 'travel-4', 'name': 'Beach', 'url': 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=1920&q=80', 'category': 'travel'},
        {'id': 'travel-5', 'name': 'Northern Lights', 'url': 'https://images.unsplash.com/photo-1531366936337-7c912a4589a7?w=1920&q=80', 'category': 'travel'},
    ],
    'minimal': [
        {'id': 'minimal-1', 'name': 'White', 'url': '', 'category': 'minimal', 'color': '#ffffff'},
        {'id': 'minimal-2', 'name': 'Dark', 'url': '', 'category': 'minimal', 'color': '#1a1a2e'},
        {'id': 'minimal-3', 'name': 'Beige', 'url': '', 'category': 'minimal', 'color': '#f5f5dc'},
        {'id': 'minimal-4', 'name': 'Sage', 'url': '', 'category': 'minimal', 'color': '#9dc183'},
    ]
}

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/sitemap.xml')
def serve_sitemap():
    static_folder = app.static_folder or 'static'
    return send_from_directory(static_folder, 'sitemap.xml', mimetype='application/xml')

@app.route('/robots.txt')
def serve_robots():
    static_folder = app.static_folder or 'static'
    return send_from_directory(static_folder, 'robots.txt', mimetype='text/plain')

# API Routes

@app.route('/api/user/settings', methods=['GET', 'POST'])
def user_settings():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json or {}
        c.execute('''
            UPDATE user_settings 
            SET clock_format = ?, dashboard_name = ?, show_quotes = ?, 
                show_streak = ?, show_spotify = ?, current_theme = ?, theme_category = ?
            WHERE user_id = ?
        ''', (
            data.get('clock_format', '24h'),
            data.get('dashboard_name', 'User'),
            data.get('show_quotes', True),
            data.get('show_streak', True),
            data.get('show_spotify', True),
            data.get('current_theme', 'default'),
            data.get('theme_category', 'gradients'),
            user_id
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    c.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
    settings = dict(c.fetchone())
    conn.close()
    return jsonify(settings)

# Todo Routes
@app.route('/api/todos', methods=['GET', 'POST'])
def todos():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json or {}
        if not data.get('text'):
            return jsonify({'error': 'Text is required'}), 400
        c.execute('''
            INSERT INTO todos (user_id, text, order_index) 
            VALUES (?, ?, (SELECT COALESCE(MAX(order_index), 0) + 1 FROM todos WHERE user_id = ?))
        ''', (user_id, data['text'], user_id))
        conn.commit()
        todo_id = c.lastrowid
        conn.close()
        return jsonify({'id': todo_id, 'text': data['text'], 'completed': False, 'order_index': 0})
    
    c.execute('SELECT * FROM todos WHERE user_id = ? ORDER BY order_index', (user_id,))
    todos = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(todos)

@app.route('/api/todos/<int:todo_id>', methods=['PUT', 'DELETE'])
def update_todo(todo_id):
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'PUT':
        data = request.json or {}
        if data:
            if 'completed' in data:
                c.execute('UPDATE todos SET completed = ? WHERE id = ? AND user_id = ?', 
                         (data['completed'], todo_id, user_id))
            if 'text' in data:
                c.execute('UPDATE todos SET text = ? WHERE id = ? AND user_id = ?', 
                         (data['text'], todo_id, user_id))
            if 'order_index' in data:
                c.execute('UPDATE todos SET order_index = ? WHERE id = ? AND user_id = ?', 
                         (data['order_index'], todo_id, user_id))
            conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        c.execute('DELETE FROM todos WHERE id = ? AND user_id = ?', (todo_id, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    else:
        conn.close()
        return jsonify({'error': 'Method not allowed'}), 405

@app.route('/api/todos/reorder', methods=['POST'])
def reorder_todos():
    user_id = get_user_id()
    data = request.json or {}
    new_order = data.get('order', [])  # List of todo IDs in new order
    
    if not new_order:
        return jsonify({'error': 'Order array is required'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    for index, todo_id in enumerate(new_order):
        c.execute('UPDATE todos SET order_index = ? WHERE id = ? AND user_id = ?', 
                 (index, todo_id, user_id))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# Focus Sessions & Stats Routes
@app.route('/api/focus-sessions', methods=['GET', 'POST'])
def focus_sessions():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json or {}
        if not data.get('duration'):
            return jsonify({'error': 'Duration is required'}), 400
        c.execute('''
            INSERT INTO focus_sessions (user_id, duration, completed, session_date) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, data['duration'], data.get('completed', False), data.get('date', datetime.now().date().isoformat())))
        conn.commit()
        session_id = c.lastrowid
        conn.close()
        return jsonify({'id': session_id, 'success': True})
    
    # Get sessions with optional date filter
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if start_date and end_date:
        c.execute('''
            SELECT * FROM focus_sessions 
            WHERE user_id = ? AND session_date BETWEEN ? AND ? 
            ORDER BY created_at DESC
        ''', (user_id, start_date, end_date))
    else:
        c.execute('SELECT * FROM focus_sessions WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    
    sessions = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(sessions)

@app.route('/api/stats/<period>')
def get_stats(period):
    """Get productivity stats for a period: daily, weekly, monthly"""
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    today = datetime.now().date()
    stats = []  # Initialize to avoid unbound variable
    
    if period == 'daily':
        # Last 7 days
        dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        stats = []
        for date in dates:
            c.execute('''
                SELECT COALESCE(SUM(duration), 0) as total_duration, COUNT(*) as session_count
                FROM focus_sessions 
                WHERE user_id = ? AND session_date = ? AND completed = 1
            ''', (user_id, date))
            row = c.fetchone()
            stats.append({
                'date': date,
                'minutes': row['total_duration'] if row['total_duration'] else 0,
                'sessions': row['session_count'] if row['session_count'] else 0
            })
    
    elif period == 'weekly':
        # Last 4 weeks
        stats = []
        for i in range(3, -1, -1):
            week_start = today - timedelta(days=today.weekday() + (i * 7))
            week_end = week_start + timedelta(days=6)
            c.execute('''
                SELECT COALESCE(SUM(duration), 0) as total_duration, COUNT(*) as session_count
                FROM focus_sessions 
                WHERE user_id = ? AND session_date BETWEEN ? AND ? AND completed = 1
            ''', (user_id, week_start.isoformat(), week_end.isoformat()))
            row = c.fetchone()
            stats.append({
                'week_start': week_start.isoformat(),
                'week_end': week_end.isoformat(),
                'minutes': row['total_duration'] if row['total_duration'] else 0,
                'sessions': row['session_count'] if row['session_count'] else 0
            })
    
    elif period == 'monthly':
        # Last 6 months
        stats = []
        for i in range(5, -1, -1):
            month_date = today.replace(day=1) - timedelta(days=i * 30)
            month_start = month_date.replace(day=1)
            if month_date.month == 12:
                month_end = month_date.replace(year=month_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = month_date.replace(month=month_date.month + 1, day=1) - timedelta(days=1)
            
            c.execute('''
                SELECT COALESCE(SUM(duration), 0) as total_duration, COUNT(*) as session_count
                FROM focus_sessions 
                WHERE user_id = ? AND session_date BETWEEN ? AND ? AND completed = 1
            ''', (user_id, month_start.isoformat(), month_end.isoformat()))
            row = c.fetchone()
            stats.append({
                'month': month_date.strftime('%B %Y'),
                'minutes': row['total_duration'] if row['total_duration'] else 0,
                'sessions': row['session_count'] if row['session_count'] else 0
            })
    
    # Calculate streak
    c.execute('''
        SELECT DISTINCT session_date FROM focus_sessions 
        WHERE user_id = ? AND completed = 1 
        ORDER BY session_date DESC
    ''', (user_id,))
    dates_with_sessions = [row['session_date'] for row in c.fetchall()]
    
    streak = 0
    check_date = today
    for date_str in dates_with_sessions:
        if date_str == check_date.isoformat():
            streak += 1
            check_date -= timedelta(days=1)
        elif date_str == (check_date + timedelta(days=1)).isoformat():
            # Same day, continue
            continue
        else:
            break
    
    # Total stats
    c.execute('''
        SELECT COALESCE(SUM(duration), 0) as total_minutes, COUNT(*) as total_sessions
        FROM focus_sessions 
        WHERE user_id = ? AND completed = 1
    ''', (user_id,))
    totals = c.fetchone()
    
    conn.close()
    
    return jsonify({
        'period': period,
        'data': stats,
        'streak': streak,
        'total_minutes': totals['total_minutes'] if totals['total_minutes'] else 0,
        'total_sessions': totals['total_sessions'] if totals['total_sessions'] else 0
    })

# Themes Routes
@app.route('/api/themes')
def get_themes():
    category = request.args.get('category', 'all')
    if category == 'all':
        return jsonify(THEMES)
    return jsonify({category: THEMES.get(category, [])})

@app.route('/api/themes/current', methods=['GET', 'POST'])
def current_theme():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json or {}
        theme_id = data.get('theme_id')
        category = data.get('category', 'gradients')
        
        c.execute('''
            UPDATE user_settings 
            SET current_theme = ?, theme_category = ?
            WHERE user_id = ?
        ''', (theme_id, category, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    c.execute('SELECT current_theme, theme_category, custom_background FROM user_settings WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    
    return jsonify({
        'current_theme': row['current_theme'] if row else 'default',
        'theme_category': row['theme_category'] if row else 'gradients',
        'custom_background': row['custom_background'] if row else None
    })

@app.route('/api/themes/custom', methods=['GET', 'POST'])
def custom_themes():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json or {}
        name = data.get('name', 'Custom Theme')
        image_data = data.get('image_data')  # Base64 encoded image
        
        c.execute('''
            INSERT INTO custom_backgrounds (user_id, name, image_data) 
            VALUES (?, ?, ?)
        ''', (user_id, name, image_data))
        conn.commit()
        bg_id = c.lastrowid
        conn.close()
        return jsonify({'id': bg_id, 'name': name, 'success': True})
    
    c.execute('SELECT id, name, created_at FROM custom_backgrounds WHERE user_id = ?', (user_id,))
    backgrounds = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(backgrounds)

@app.route('/api/themes/custom/<int:bg_id>')
def get_custom_background(bg_id):
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT image_data FROM custom_backgrounds WHERE id = ? AND user_id = ?', (bg_id, user_id))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify({'image_data': row['image_data']})
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/themes/custom/<int:bg_id>', methods=['DELETE'])
def delete_custom_background(bg_id):
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM custom_backgrounds WHERE id = ? AND user_id = ?', (bg_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# Quotes Routes
@app.route('/api/quote')
def get_quote():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    # Check if we have a quote for today
    today = datetime.now().date().isoformat()
    c.execute('SELECT quote FROM daily_quotes WHERE user_id = ? AND date = ?', (user_id, today))
    row = c.fetchone()
    
    if row:
        conn.close()
        return jsonify({'quote': row['quote'], 'date': today})
    
    # Generate new quote using AI
    if not AI_AVAILABLE:
        # Fallback quotes
        fallback_quotes = [
            "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle.",
            "The only way to do great work is to love what you do.",
            "Success is not final, failure is not fatal: it is the courage to continue that counts.",
            "Your time is limited, don't waste it living someone else's life.",
            "The future belongs to those who believe in the beauty of their dreams.",
            "Don't watch the clock; do what it does. Keep going.",
            "Everything you've ever wanted is on the other side of fear.",
            "Hardships often prepare ordinary people for an extraordinary destiny.",
            "The only limit to our realization of tomorrow will be our doubts of today.",
            "Do what you can, with what you have, where you are."
        ]
        import random
        quote = random.choice(fallback_quotes)
    else:
        try:
            if groq_client is None:
                quote = "Believe in yourself and all that you are."
            else:
                chat_completion = groq_client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": """Generate ONE motivational, self-care, or gratitude quote for productivity and focus.
                        The quote should be inspiring but practical, related to studying, working, or personal growth.
                        Return ONLY the quote text, no author name, no quotation marks, no additional text."""
                    }],
                    model="llama-3.3-70b-versatile",
                    temperature=0.8,
                    max_tokens=200
                )
                content = chat_completion.choices[0].message.content if chat_completion.choices else None
                quote = content.strip().strip('"') if content else "Believe in yourself and all that you are."
        except Exception as e:
            quote = "Believe in yourself and all that you are."
    
    # Save quote
    c.execute('INSERT INTO daily_quotes (user_id, quote, date) VALUES (?, ?, ?)', 
              (user_id, quote, today))
    conn.commit()
    conn.close()
    
    return jsonify({'quote': quote, 'date': today})

# Greeting Route
@app.route('/api/greeting')
def get_greeting():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT dashboard_name FROM user_settings WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    name = row['dashboard_name'] if row else 'User'
    
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting = f"Good morning, {name}"
    elif 12 <= hour < 17:
        greeting = f"Good afternoon, {name}"
    elif 17 <= hour < 21:
        greeting = f"Good evening, {name}"
    else:
        greeting = f"Good night, {name}"
    
    conn.close()
    return jsonify({'greeting': greeting, 'name': name})

# Legacy Routes (keep for compatibility)
@app.route('/api/calendar/events', methods=['GET', 'POST'])
def calendar_events():
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        event = request.json or {}
        if not event.get('title') or not event.get('date'):
            return jsonify({'error': 'Title and date are required'}), 400
        c.execute('''
            INSERT INTO calendar_events (user_id, title, date, time, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, event['title'], event['date'], event.get('time', ''), event.get('description', '')))
        conn.commit()
        event_id = c.lastrowid
        conn.close()
        return jsonify({'success': True, 'event': {**event, 'id': event_id}})
    
    c.execute('SELECT * FROM calendar_events WHERE user_id = ? ORDER BY date, time', (user_id,))
    events = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(events)

@app.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    user_id = get_user_id()
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM calendar_events WHERE id = ? AND user_id = ?', (event_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/schedule/generate', methods=['POST'])
def generate_schedule():
    data = request.json or {}
    goal = data.get('goal', '')
    routine = data.get('routine', '')
    subjects = data.get('subjects', '')
    preferences = data.get('preferences', '')
    
    if not AI_AVAILABLE or groq_client is None:
        return jsonify({
            'error': 'AI service is not available. Please check the installation.',
            'schedule': {'schedule': [], 'tips': ['AI service unavailable.']}
        }), 500
    
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"""Create a detailed weekly study schedule.

STUDENT INFORMATION:
Goal: {goal}
Current Routine: {routine}
Subjects to Study: {subjects}
Preferences: {preferences}

Create JSON with schedule array (day, tasks with time/duration/activity/subject/description) and tips.
Include breaks between sessions. Duration in minutes."""
            }],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=2000
        )
        
        response_text = chat_completion.choices[0].message.content if chat_completion.choices else None
        
        # Extract JSON
        schedule_data = {'schedule': [], 'tips': []}
        try:
            if response_text and '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    schedule_data = json.loads(response_text[json_start:json_end].strip())
            elif response_text and '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    schedule_data = json.loads(response_text[json_start:json_end].strip())
            elif response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    schedule_data = json.loads(response_text[start_idx:end_idx])
        except:
            schedule_data = {'schedule': [], 'tips': []}
        
        # Save to database
        user_id = get_user_id()
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO schedules (user_id, goal, routine, subjects, preferences, schedule_data, tips)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, goal, routine, subjects, preferences, 
              json.dumps(schedule_data.get('schedule', [])),
              json.dumps(schedule_data.get('tips', []))))
        conn.commit()
        conn.close()
        
        return jsonify(schedule_data)
    
    except Exception as e:
        return jsonify({'error': str(e), 'schedule': {'schedule': [], 'tips': [f'Error: {str(e)}']}}), 500

@app.route('/api/flashcards/generate', methods=['POST'])
def generate_flashcards():
    data = request.json or {}
    topic = data.get('topic', '')
    subject = data.get('subject', '')
    is_new = data.get('new', False)
    
    if not AI_AVAILABLE:
        return jsonify({'flashcards': []}), 500
    
    try:
        if groq_client is None:
            return jsonify({'flashcards': []}), 500
        
        # Higher temperature for more variation when generating new cards
        temperature = 1.0 if is_new else 0.7
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"""Generate 5 NEW and DIFFERENT educational flashcards for {topic} in {subject}.
These must be completely different from any previously generated flashcards.
Provide in JSON format: {{"flashcards": [{{"question": "...", "answer": "...", "hint": "..."}}]}}"""
            }],
            model="llama-3.3-70b-versatile",
            temperature=temperature,
            max_tokens=1500
        )
        
        response_text = chat_completion.choices[0].message.content if chat_completion.choices else None
        
        flashcards_data = {'flashcards': []}
        try:
            if response_text and '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    flashcards_data = json.loads(response_text[json_start:json_end].strip())
            elif response_text and '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    flashcards_data = json.loads(response_text[json_start:json_end].strip())
            elif response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    flashcards_data = json.loads(response_text[start_idx:end_idx])
        except:
            flashcards_data = {'flashcards': []}
        
        # Save to database
        user_id = get_user_id()
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO flashcards (user_id, topic, subject, cards)
            VALUES (?, ?, ?, ?)
        ''', (user_id, topic, subject, json.dumps(flashcards_data.get('flashcards', []))))
        conn.commit()
        conn.close()
        
        return jsonify(flashcards_data)
    
    except Exception as e:
        return jsonify({'error': str(e), 'flashcards': []}), 500

@app.route('/api/pyq/generate', methods=['POST'])
def generate_pyq():
    data = request.json or {}
    topic = data.get('topic', '')
    subject = data.get('subject', '')
    difficulty = data.get('difficulty', 'medium')
    count = data.get('count', 10)
    
    if not AI_AVAILABLE:
        return jsonify({'questions': []}), 500
    
    try:
        if groq_client is None:
            return jsonify({'questions': []}), 500
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"""Generate {count} {difficulty} difficulty multiple choice questions for {topic} in {subject}.
Provide in JSON format: {{"questions": [{{"question": "...", "options": ["A", "B", "C", "D"], "correct": "A", "explanation": "...", "subject": "{subject}", "topic": "{topic}", "difficulty": "{difficulty}"}}]}}"""
            }],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=3000
        )
        
        response_text = chat_completion.choices[0].message.content if chat_completion.choices else None
        
        questions_data = {'questions': []}
        try:
            if response_text and '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    questions_data = json.loads(response_text[json_start:json_end].strip())
            elif response_text and '```' in response_text:
                json_start = response_text.find('```') + 3
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    questions_data = json.loads(response_text[json_start:json_end].strip())
            elif response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    questions_data = json.loads(response_text[start_idx:end_idx])
        except:
            questions_data = {'questions': []}
        
        # Save to database
        user_id = get_user_id()
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO pyq_questions (user_id, topic, subject, difficulty, questions)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, topic, subject, difficulty, json.dumps(questions_data.get('questions', []))))
        conn.commit()
        conn.close()
        
        return jsonify(questions_data)
    
    except Exception as e:
        return jsonify({'error': str(e), 'questions': []}), 500

@app.route('/api/timer/break-suggestion', methods=['POST'])
def get_break_suggestion():
    data = request.json or {}
    study_minutes = data.get('study_minutes', 25)
    
    if not AI_AVAILABLE:
        if study_minutes <= 25:
            suggested_break = 5
        elif study_minutes <= 50:
            suggested_break = 10
        else:
            suggested_break = 15
        
        return jsonify({
            'suggested_break_minutes': suggested_break,
            'explanation': f'After {study_minutes} minutes of study, take a {suggested_break}-minute break.',
            'tips': ['Stretch', 'Rest your eyes', 'Hydrate']
        })
    
    try:
        if groq_client is None:
            raise Exception("Groq client not available")
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"""Student completed {study_minutes} minutes of focused study.
Suggest optimal break duration and tips. Respond in JSON: 
{{"suggested_break_minutes": number, "explanation": "...", "tips": ["..."]}}"""
            }],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=500
        )
        
        response_text = chat_completion.choices[0].message.content if chat_completion.choices else None
        
        suggestion_data = {
            'suggested_break_minutes': 5,
            'explanation': 'Take a short break to recharge.',
            'tips': ['Stretch', 'Hydrate']
        }
        try:
            if response_text and '```json' in response_text:
                json_start = response_text.find('```json') + 7
                json_end = response_text.find('```', json_start)
                if json_end != -1:
                    suggestion_data = json.loads(response_text[json_start:json_end].strip())
            elif response_text:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    suggestion_data = json.loads(response_text[start_idx:end_idx])
        except:
            suggestion_data = {
                'suggested_break_minutes': 5,
                'explanation': 'Take a short break to recharge.',
                'tips': ['Stretch', 'Hydrate']
            }
        
        return jsonify(suggestion_data)
    
    except Exception as e:
        return jsonify({
            'suggested_break_minutes': 5,
            'explanation': 'Take a break to recharge.',
            'tips': ['Stretch', 'Hydrate']
        })

NON_EDUCATIONAL_KEYWORDS = [
    'bomb', 'weapon', 'drug', 'hack', 'steal', 'crime', 'murder', 'attack',
    'pornography', 'explicit', 'violence', 'harmful', 'illegal', 'fraud',
    'discrimination', 'hate', 'extremism', 'terrorism', 'suicide', 'self-harm'
]

@app.route('/api/doubt/explain', methods=['POST'])
def explain_doubt():
    if not AI_AVAILABLE or groq_client is None:
        return jsonify({'error': 'AI service is not available', 'explanation': ''}), 500
    
    data = request.json or {}
    question = data.get('question', '').strip()
    mode = data.get('mode', 'normal')
    
    if not question:
        return jsonify({'error': 'Please enter your question', 'explanation': ''}), 400
    
    question_lower = question.lower()
    for keyword in NON_EDUCATIONAL_KEYWORDS:
        if keyword in question_lower:
            return jsonify({
                'error': 'This question does not appear to be educational or study-related.',
                'explanation': 'Please ask questions about subjects like Math, Science, History, Literature, or other academic topics.'
            }), 400
    
    try:
        if mode == 'baby':
            system_prompt = """You are a knowledgeable and patient teacher explaining concepts to someone who has absolutely zero prior knowledge of the topic.
Start from the absolute basics - define every term you use on first mention.
Build understanding step by step, connecting new concepts to simple, universal ideas everyone can understand.
Use clear analogies from everyday life rather than jargon.
Be thorough but not condescending - treat the learner as an intelligent adult who simply hasn't encountered this subject before.
Include the "why" behind things, not just the "what".
Keep explanations concise but complete - aim for 2-3 well-crafted paragraphs that leave the learner with genuine understanding."""
            user_prompt = f"""Please explain this concept to someone who knows absolutely nothing about this topic. 
Assume they are an intelligent beginner with no background in this area whatsoever:

{question}

Start with the absolute basics, define any technical terms, and build up understanding step by step."""
        else:
            system_prompt = """You are a concise, expert tutor. Give clear, precise, and to-the-point explanations.
Get straight to the answer without fluff. Use technical terms appropriately.
Be direct but still helpful. Aim for short, impactful responses.
If explaining a concept, give the core definition first, then key details."""
            user_prompt = f"""Explain this concisely and precisely:

{question}

Give a clear, direct answer. Keep it brief but informative."""
        
        chat_completion = groq_client.chat.completions.create(
            messages=[{
                "role": "system",
                "content": system_prompt
            }, {
                "role": "user",
                "content": user_prompt
            }],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=800
        )
        
        response_text = chat_completion.choices[0].message.content if chat_completion.choices else None
        
        if response_text:
            return jsonify({
                'question': question,
                'explanation': response_text.strip(),
                'mode': mode,
                'error': None
            })
        else:
            return jsonify({
                'error': 'Could not generate explanation',
                'explanation': '',
                'question': question
            }), 500
            
    except Exception as e:
        return jsonify({
            'error': f'Error generating explanation: {str(e)}',
            'explanation': ''
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
