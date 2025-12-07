import os
import time
import random
from functools import wraps
from flask import Flask, request, jsonify, session
import psycopg2
import sqlite3
from psycopg2.extras import RealDictCursor
from base64 import b64decode

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://demo:demo_pass@db:5432/demo_db")
DEMO_USERNAME = os.getenv("DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "changeme")
SECRET_KEY    = os.getenv("SECRET_KEY", "supersecretchangeit")

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_conn(retries=10, delay=1.0):
    for i in range(retries):
        try:
            if "postgresql" in DATABASE_URL:
                return psycopg2.connect(DATABASE_URL)
            else:
                return sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
        except Exception:
            time.sleep(delay)
    raise RuntimeError("DB connection failed")

# Ensure table/row exist (id=1 holding the sum)
def init_db():
    with get_conn() as conn:
        if "postgresql" in DATABASE_URL:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS totals (
                        id INT PRIMARY KEY,
                        sum INT NOT NULL DEFAULT 0
                    );
                """)
                cur.execute("INSERT INTO totals (id, sum) VALUES (1, 0) ON CONFLICT (id) DO NOTHING;")
                conn.commit()
        else:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS totals (
                    id INTEGER PRIMARY KEY,
                    sum INTEGER NOT NULL DEFAULT 0
                );
            """)
            # SQLite uses INSERT OR IGNORE instead of ON CONFLICT DO NOTHING
            cur.execute("INSERT OR IGNORE INTO totals (id, sum) VALUES (1, 0);")
            conn.commit()
            cur.close()

init_db()

def basic_auth_ok():
    # Expect "Authorization: Basic base64(user:pass)"
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        userpass = b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        user, pw = userpass.split(":", 1)
        return (user == DEMO_USERNAME) and (pw == DEMO_PASSWORD)
    except Exception:
        return False

def session_ok():
    return session.get("user") == DEMO_USERNAME

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session_ok() or basic_auth_ok():
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return wrapper

@app.get("/")
def index():
    return """
    <html>
      <body>
        <h1>welcome dear customer</h1>
        <button onclick="checkHealth()">health</button>
        <div id="health-result"></div>
        <script>
          async function checkHealth() {
            const resultDiv = document.getElementById('health-result');
            resultDiv.innerHTML = 'Checking health...';
            const start = performance.now();
            try {
              const resp = await fetch('/health');
              const data = await resp.json();
              const end = performance.now();
              resultDiv.innerHTML =
                '<pre>' + JSON.stringify(data) + '</pre>' +
                '<div>Took: ' + (end - start).toFixed(2) + ' ms</div>';
            } catch (e) {
              resultDiv.innerHTML = 'Error: ' + e;
            }
          }
        </script>
      </body>
    </html>
    """, 200, {"Content-Type": "text/html"}

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = data.get("username")
    pw   = data.get("password")
    if user == DEMO_USERNAME and pw == DEMO_PASSWORD:
        session["user"] = DEMO_USERNAME
        return jsonify({"message": "logged in"})
    return jsonify({"error": "Invalid credentials"}), 401

@app.post("/logout")
def logout():
    session.pop("user", None)
    return jsonify({"message": "logged out"})

@app.get("/add")
@require_auth
def get_sum():
    with get_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT sum FROM totals WHERE id=1;")
        row = cur.fetchone()
        return jsonify({"sum": row["sum"]})

@app.post("/add")
@require_auth
def add_sum():
    payload = request.get_json(silent=True) or {}
    # Also allow form or query if someone posts differently
    value = payload.get("value", request.form.get("value", request.args.get("value")))
    try:
        value = int(value)
    except Exception:
        return jsonify({"error": "Provide integer 'value'"}), 400

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE totals SET sum = sum + %s WHERE id=1 RETURNING sum;", (value,))
        new_sum = cur.fetchone()[0]
        conn.commit()
    return jsonify({"sum": new_sum})

@app.get("/io")
@require_auth
def simulate_io():
    """Simulate I/O-bound work by sleeping for a random short duration."""
    duration = random.uniform(0.5, 5.0)  # Sleep between 0.5 and 5 seconds
    time.sleep(duration)
    return jsonify({"message": "I/O-bound simulation complete", "slept_seconds": round(duration, 2)})

@app.get("/compute")
@require_auth
def simulate_compute():
    """Simulate CPU-bound work by performing a simple computation."""
    n = 10**6
    result = sum(i*i for i in range(n))
    return jsonify({"message": "CPU-bound simulation complete", "result": result})
