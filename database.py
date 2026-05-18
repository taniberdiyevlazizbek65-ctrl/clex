import sqlite3
from datetime import date, datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("clex.db", check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, name TEXT, username TEXT,
            xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
            streak INTEGER DEFAULT 0, last_active TEXT, joined TEXT,
            cabinet TEXT, subject TEXT, knowledge_level TEXT DEFAULT 'beginner')""")
        c.execute("""CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            cabinet TEXT, subject TEXT, score INTEGER, total INTEGER, date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, badge_name TEXT, earned_date TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS mooc_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            week TEXT, subject TEXT, score INTEGER, total INTEGER,
            certificate_level TEXT, date TEXT)""")
        self.conn.commit()

    def add_user(self, user_id, name, username):
        c = self.conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO users (user_id,name,username,joined,last_active) VALUES (?,?,?,?,?)",
                      (user_id, name, username, str(date.today()), str(date.today())))
            self.conn.commit()

    def get_user(self, user_id):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if row:
            keys = ["user_id","name","username","xp","level","streak","last_active","joined","cabinet","subject","knowledge_level"]
            return dict(zip(keys, row))
        return None

    def get_user_stats(self, user_id):
        return self.get_user(user_id) or {"xp":0,"level":1,"streak":0}

    def add_xp(self, user_id, amount):
        c = self.conn.cursor()
        user = self.get_user(user_id)
        if user:
            new_xp = user["xp"] + amount
            new_level = new_xp // 500 + 1
            c.execute("UPDATE users SET xp=?, level=? WHERE user_id=?", (new_xp, new_level, user_id))
            self.conn.commit()

    def update_streak(self, user_id):
        c = self.conn.cursor()
        user = self.get_user(user_id)
        if not user: return 0
        today = str(date.today())
        if user["last_active"] == today: return user["streak"]
        yesterday = str(date.fromordinal(date.today().toordinal()-1))
        new_streak = user["streak"]+1 if user["last_active"]==yesterday else 1
        c.execute("UPDATE users SET streak=?,last_active=? WHERE user_id=?", (new_streak,today,user_id))
        self.conn.commit()
        return new_streak

    def set_cabinet(self, user_id, cabinet):
        self.conn.execute("UPDATE users SET cabinet=? WHERE user_id=?", (cabinet, user_id))
        self.conn.commit()

    def set_subject(self, user_id, subject):
        self.conn.execute("UPDATE users SET subject=? WHERE user_id=?", (subject, user_id))
        self.conn.commit()

    def set_knowledge_level(self, user_id, level):
        self.conn.execute("UPDATE users SET knowledge_level=? WHERE user_id=?", (level, user_id))
        self.conn.commit()

    def save_test_result(self, user_id, cabinet, subject, score, total):
        self.conn.execute("INSERT INTO test_results (user_id,cabinet,subject,score,total,date) VALUES (?,?,?,?,?,?)",
                          (user_id, cabinet, subject, score, total, str(date.today())))
        self.conn.commit()

    def add_badge(self, user_id, badge_name):
        c = self.conn.cursor()
        c.execute("SELECT id FROM badges WHERE user_id=? AND badge_name=?", (user_id, badge_name))
        if not c.fetchone():
            c.
          execute("INSERT INTO badges (user_id,badge_name,earned_date) VALUES (?,?,?)",
                      (user_id, badge_name, str(date.today())))
            self.conn.commit()
            return True
        return False

    def get_badges(self, user_id):
        c = self.conn.cursor()
        c.execute("SELECT badge_name FROM badges WHERE user_id=?", (user_id,))
        return c.fetchall()

    def get_leaderboard(self, limit=10):
        c = self.conn.cursor()
        c.execute("SELECT name,xp,level,streak FROM users ORDER BY xp DESC LIMIT ?", (limit,))
        return c.fetchall()

    def save_mooc_result(self, user_id, subject, score, total):
        week = datetime.now().strftime("%Y-W%U")
        ratio = score/total if total>0 else 0
        level = "Oltin" if ratio>=0.9 else "Kumush" if ratio>=0.7 else "Bronza"
        self.conn.execute("INSERT INTO mooc_results (user_id,week,subject,score,total,certificate_level,date) VALUES (?,?,?,?,?,?,?)",
                          (user_id, week, subject, score, total, level, str(date.today())))
        self.conn.commit()
        return level
