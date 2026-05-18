import requests
import os
import json

API_KEY = os.environ.get("GEMINI_API_KEY")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

LEVEL_NAMES = {
    "beginner":"Boshlang'ich (A1)", "elementary":"Asosiy (A2)",
    "intermediate":"O'rta (B1)", "upper":"Yuqori O'rta (B2)",
    "advanced":"Ilg'or (C1)", "master":"Ustoz (C2)"
}

def ask_gemini(prompt):
    try:
        r = requests.post(URL, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=30)
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except:
        return ""

def parse_json(text):
    try:
        text = text.strip().replace("```json","").replace("```","").strip()
        return json.loads(text)
    except:
        return None

async def generate_assessment_questions(subject, count=5):
    prompt = f"""{subject} fanidan bilim darajasini aniqlash uchun {count} ta savol tuzin.
JSON: [{{"question":"...","options":["A","B","C","D"],"correct":0,"difficulty":"easy/medium/hard"}}]
Faqat JSON qaytaring. O'zbekcha."""
    result = parse_json(ask_gemini(prompt))
    return result if result else []

async def assess_knowledge(subject, answers):
    prompt = f"""{subject} fanida foydalanuvchi javoblari: {answers}
JSON: {{"level":"beginner/elementary/intermediate/upper/advanced/master","score":0-100,"feedback":"...","recommendation":"..."}}
Faqat JSON. O'zbekcha."""
    result = parse_json(ask_gemini(prompt))
    return result if result else {"level":"beginner","score":0,"feedback":"Boshlang'ich darajadan boshlaymiz!","recommendation":"Asoslardan o'rganamiz."}

async def get_topics(subject, level):
    level_name = LEVEL_NAMES.get(level, "Boshlang'ich")
    prompt = f"""{subject} fanining {level_name} darajasida 8 ta mavzu.
JSON: ["Mavzu 1","Mavzu 2",...] Faqat JSON. O'zbekcha."""
    result = parse_json(ask_gemini(prompt))
    return result if result else ["Asosiy tushunchalar","Amaliy mashqlar","Murakkab mavzular"]

async def generate_lesson(subject, topic, level):
    level_name = LEVEL_NAMES.get(level, "Boshlang'ich")
    prompt = f"""Sen CLEX AI o'qituvchisisiz.
Fan: {subject}, Mavzu: {topic}, Daraja: {level_name}
Qisqa va chiroyli dars yozing. Emoji ishlating. Maksimal 250 so'z. O'zbekcha."""
    result = ask_gemini(prompt)
    return result if result else "Dars yuklanmadi. Qayta urinib koring."

async def generate_quiz(subject, topic, level, count=5):
    level_name = LEVEL_NAMES.get(level, "Boshlang'ich")
    prompt = f"""Sen CLEX AI o'qituvchisisiz. {subject} - {topic} ({level_name}) dan {count} ta test.
JSON: [{{"question":"...","options":["A","B","C","D"],"correct":0,"explanation":"..."}}]
Faqat JSON. O'zbekcha."""
    result = parse_json(ask_gemini(prompt))
    return result if result else []

async def generate_mooc_test(subject, level):
    prompt = f"""CLEX MOOC test. {subject} fanidan 10 ta savol.
JSON: [{{"question":"...","options":["A","B","C","D"],"correct":0,"explanation":"..."}}]
Faqat JSON. O'zbekcha."""
    result = parse_json(ask_gemini(prompt))
    return result if result else []

async def generate_game_question(subject, difficulty="medium"):
    prompt = f"""{subject} fanidan 1 ta {difficulty} savol.
JSON: {{"question":"...","options":["A","B","C","D"],"correct":0,"explanation":"..."}}
Faqat JSON. O'zbekcha."""
    result = parse_json(ask_gemini(prompt))
    return result if result else {}

async def chat_with_ai(user_message, subject, level, history=[]):
    level_name = LEVEL_NAMES.get(level, "Boshlang'ich")
    history_text = "\n".join([f"{m['role']}: {m['content']}" for m in history[-5:]])
    prompt = f"""Sen CLEX AI o'qituvchisisiz. Fan: {subject}, Daraja: {level_name}
Oldingi suhbat:\n{history_text}
Foydalanuvchi: {user_message}
Qisqa, aniq, do'stona javob. Emoji ishlating. O'zbekcha."""
    result = ask_gemini(prompt)
    return result if result else "Xatolik yuz berdi. Qayta urinib koring."
