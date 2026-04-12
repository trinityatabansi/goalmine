from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from groq import Groq
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection, init_db
import os
import random

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "goalmine_secret_2025")

GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
client = Groq(api_key=GROQ_KEY)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

init_db()

AFFIRMATIONS = [
    "God placed this goal in you for a reason. Trust the process.",
    "You are not behind. You are building something that lasts.",
    "Every check-in is proof that you chose yourself today.",
    "She who mines her goals, finds her gold.",
    "Big goals don't scare you — they were made for you.",
    "Your consistency is your superpower. Keep mining.",
    "Rest is part of the process. You are still winning.",
    "You were built for this. Not someday, right now.",
    "Faith without works is dead. You are putting in the work.",
    "The person you are becoming is worth every hard day.",
    "Done is better than perfect. Keep moving forward.",
    "Your dream is valid. Your effort is real. Keep going.",
    "God did not give you this vision to leave you without provision.",
    "You are the first generation of something great.",
    "Small steps every day beat big steps never.",
    "You are not just chasing a goal, you are building a legacy.",
    "Discipline is the bridge between your dream and your reality.",
    "The grind is temporary. The results are forever.",
    "Bet on yourself every single time.",
    "You have already done the hardest part, you started.",
]

class User(UserMixin):
    def __init__(self, id, name, email, coin_balance):
        self.id = id
        self.name = name
        self.email = email
        self.coin_balance = coin_balance

@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user:
        return User(user["id"], user["name"], user["email"], user["coin_balance"])
    return None

def get_all_goals():
    if not current_user.is_authenticated:
        return []
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT g.id, g.goal_text,
               COUNT(s.id) as total_steps,
               SUM(s.is_completed) as completed_steps
        FROM goals g
        LEFT JOIN steps s ON s.goal_id = g.id
        WHERE g.user_id = %s
        GROUP BY g.id, g.goal_text
        ORDER BY g.created_at DESC
    """, (current_user.id,))
    goals = cursor.fetchall()
    cursor.close()
    conn.close()
    return goals

@app.route("/", methods=["GET", "POST"])
def index():
    plan = None
    goal = ""
    error = None
    steps_data = []
    saved_goal_id = None
    pace = "standard"
    affirmation = random.choice(AFFIRMATIONS)

    if current_user.is_authenticated:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM goals WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (current_user.id,))
        last_goal = cursor.fetchone()
        if last_goal:
            cursor.execute("SELECT * FROM steps WHERE goal_id = %s ORDER BY week_number, id", (last_goal["id"],))
            saved_steps = cursor.fetchall()
            if saved_steps:
                saved_goal_id = last_goal["id"]
                goal = last_goal["goal_text"]
                steps_data = saved_steps
        cursor.close()
        conn.close()

    if request.method == "POST":
        goal = request.form.get("goal", "").strip()
        pace = request.form.get("pace", "standard")

        if goal:
            try:
                pace_map = {
                    "quick": "1 to 2 weeks",
                    "standard": "4 weeks",
                    "deep": "6 to 8 weeks"
                }
                plan_length = pace_map.get(pace, "4 weeks")
                system_prompt = f"You are GoalMine, an AI goal planner. When a user gives you a goal, break it into milestones with a {plan_length} action plan. Format your response EXACTLY like this, no extra text:\n\nMilestone 1: [milestone name] (~[estimated time, e.g. 3 days, 1 week])\n* [action step]\n* [action step]\n\nMilestone 2: [milestone name] (~[estimated time])\n* [action step]\n* [action step]\n\n(continue for the appropriate number of milestones)\n\nKeep each milestone name short and motivating. Keep each action step specific and doable. 2-3 steps per milestone."

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"My goal is: {goal}"}
                    ],
                    max_tokens=600
                )
                plan = response.choices[0].message.content

                if current_user.is_authenticated:
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO goals (user_id, goal_text) VALUES (%s, %s)", (current_user.id, goal))
                    goal_id = cursor.lastrowid
                    saved_goal_id = goal_id
                    current_week = 0
                    for line in plan.split("\n"):
                        line = line.strip()
                        if line.startswith("Milestone"):
                            current_week += 1
                        elif line.startswith("*"):
                            step_text = line[1:].strip()
                            cursor.execute("INSERT INTO steps (goal_id, week_number, step_text) VALUES (%s, %s, %s)", (goal_id, current_week, step_text))
                    cursor.execute("UPDATE users SET coin_balance = coin_balance + 10 WHERE id = %s", (current_user.id,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    conn = get_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT * FROM steps WHERE goal_id = %s ORDER BY week_number, id", (goal_id,))
                    steps_data = cursor.fetchall()
                    cursor.close()
                    conn.close()

            except Exception as e:
                error = f"Something went wrong: {str(e)}"

    coins = 0
    if current_user.is_authenticated:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT coin_balance FROM users WHERE id = %s", (current_user.id,))
        row = cursor.fetchone()
        coins = row["coin_balance"] if row else 0
        cursor.close()
        conn.close()

    return render_template("index.html",
        plan=plan,
        goal=goal,
        error=error,
        affirmation=affirmation,
        steps_data=steps_data,
        saved_goal_id=saved_goal_id,
        coins=coins,
        pace=pace,
        all_goals=get_all_goals()
    )

@app.route("/load_goal/<int:goal_id>")
@login_required
def load_goal(goal_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM goals WHERE id = %s AND user_id = %s", (goal_id, current_user.id))
    goal_row = cursor.fetchone()
    cursor.execute("SELECT * FROM steps WHERE goal_id = %s ORDER BY week_number, id", (goal_id,))
    steps_data = cursor.fetchall()
    cursor.execute("SELECT coin_balance FROM users WHERE id = %s", (current_user.id,))
    row = cursor.fetchone()
    coins = row["coin_balance"] if row else 0
    cursor.close()
    conn.close()
    affirmation = random.choice(AFFIRMATIONS)
    return render_template("index.html",
        plan=None,
        goal=goal_row["goal_text"] if goal_row else "",
        error=None,
        affirmation=affirmation,
        steps_data=steps_data,
        saved_goal_id=goal_id,
        coins=coins,
        pace="standard",
        all_goals=get_all_goals()
    )

@app.route("/toggle_step", methods=["POST"])
@login_required
def toggle_step():
    data = request.get_json()
    step_id = data.get("step_id")
    completed = bool(data.get("completed"))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE steps SET is_completed = %s WHERE id = %s", (completed, step_id))
    if completed:
        cursor.execute("UPDATE users SET coin_balance = coin_balance + 5 WHERE id = %s", (current_user.id,))
    else:
        cursor.execute("UPDATE users SET coin_balance = GREATEST(0, coin_balance - 5) WHERE id = %s", (current_user.id,))
    conn.commit()
    cursor.execute("SELECT coin_balance FROM users WHERE id = %s", (current_user.id,))
    new_balance = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return jsonify({"coins": new_balance})

@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        else:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            existing = cursor.fetchone()
            if existing:
                error = "An account with that email already exists."
            else:
                hashed = generate_password_hash(password)
                cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed))
                conn.commit()
                user_id = cursor.lastrowid
                cursor.close()
                conn.close()
                user = User(user_id, name, email, 0)
                login_user(user)
                return redirect(url_for("index"))
            cursor.close()
            conn.close()
    return render_template("signup.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if not user or not check_password_hash(user["password"], password):
            error = "Invalid email or password."
        else:
            u = User(user["id"], user["name"], user["email"], user["coin_balance"])
            login_user(u)
            return redirect(url_for("index"))
    return render_template("login.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/delete_goal/<int:goal_id>", methods=["POST"])
@login_required
def delete_goal(goal_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM goals WHERE id = %s AND user_id = %s", (goal_id, current_user.id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("index"))
if __name__ == "__main__":
    app.run(debug=True)


