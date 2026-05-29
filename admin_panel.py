from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import os
import time

app = Flask(__name__)
app.secret_key = 'rapid_uid_bypass_secret_key_786'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "bot_data.db")

ADMIN_EMAIL = "deepanshuyadav@gmail.com"
ADMIN_PASS = "adminuidbypass"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if email == ADMIN_EMAIL and password == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid email or password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/api/uids', methods=['GET'])
def get_uids():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT uid, region, expires_at FROM whitelist")
        rows = cur.fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/uids', methods=['POST'])
def add_uid():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    uid = data.get('uid')
    region = data.get('region', 'GLOBAL')
    duration = data.get('duration', 'lifetime')
    
    expires_at = 0
    if duration != 'lifetime':
        try:
            hours = int(duration)
            if hours > 0:
                expires_at = int(time.time()) + (hours * 3600)
        except ValueError:
            pass
    
    if not uid:
        return jsonify({"error": "UID is required"}), 400
    
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Ensure column exists for backwards compatibility
        try:
            cur.execute("ALTER TABLE whitelist ADD COLUMN expires_at INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        cur.execute("INSERT OR REPLACE INTO whitelist (uid, region, expires_at) VALUES (?, ?, ?)", (uid, region, expires_at))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "UID already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/uids/<uid>', methods=['DELETE'])
def delete_uid(uid):
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM whitelist WHERE uid=?", (uid,))
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    if not session.get('logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Ensure tables exist
        cur.execute("CREATE TABLE IF NOT EXISTS whitelist (uid TEXT PRIMARY KEY, region TEXT DEFAULT 'GLOBAL', expires_at INTEGER DEFAULT 0)")
        
        # Backward compatibility for existing databases
        try:
            cur.execute("ALTER TABLE whitelist ADD COLUMN expires_at INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
            
        cur.execute("CREATE TABLE IF NOT EXISTS blacklist (uid TEXT PRIMARY KEY)")
        cur.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)")
        
        cur.execute("SELECT count(*) as count FROM whitelist")
        whitelist_count = cur.fetchone()['count']
        
        cur.execute("SELECT count(*) as count FROM blacklist")
        blacklist_count = cur.fetchone()['count']
        
        cur.execute("SELECT key, value FROM stats")
        stats = {row['key']: row['value'] for row in cur.fetchall()}
        
        conn.close()
        
        return jsonify({
            "whitelist_count": whitelist_count,
            "blacklist_count": blacklist_count,
            "stats": stats
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start the web app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
