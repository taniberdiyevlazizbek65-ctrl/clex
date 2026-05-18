import os
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import Database
from ai_tutor import (generate_assessment_questions, assess_knowledge, get_topics, generate_lesson, generate_quiz, generate_mooc_test, generate_game_question, chat_with_ai)

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    exit("Xatolik: BOT_TOKEN muhit o'zgaruvchisi (Variable) Railway'da o'rnatilmagan!")

db = Database()
user_sessions = {}
active_games = {}

CABINETS = {"lang":"Til Organish","math":"Matematika","chem":"Kimyo va Biologiya","hum":"Gumanitar","soc":"Ijtimoiy","it":"IT","art":"Ijodiy"}
LANGUAGES = {"en":"Ingliz","ru":"Rus","de":"Nemis","fr":"Fransuz","ar":"Arab","zh":"Xitoy","ja":"Yapon","ko":"Koreya","es":"Ispan","tr":"Turk","uz":"Uzbek"}
SUBJECTS = {
    "math":{"Matematika":"Matematika","Fizika":"Fizika","Informatika":"Informatika"},
    "chem":{"Kimyo":"Kimyo","Biologiya":"Biologiya"},
    "hum":{"Tarix":"Tarix","Adabiyot":"Adabiyot"},
    "soc":{"Geografiya":"Geografiya","Iqtisodiyot":"Iqtisodiyot"},
    "it":{"Python":"Python","Web":"Web"},
    "art":{"Dizayn":"Dizayn"}
}
GAME_SUBJECTS = ["Ingliz tili","Matematika","Kimyo","Biologiya","Tarix","Geografiya","Fizika","Informatika"]
LEVEL_NAMES = {"beginner":"Boshlangich","elementary":"Asosiy","intermediate":"Orta","upper":"Yuqori","advanced":"Ilgor","master":"Ustoz"}

def s(uid):
    if uid not in user_sessions:
        user_sessions[uid] = {}
    return user_sessions[uid]

def bar(cur, total, n=10):
    f = int(n * cur / total) if total > 0 else 0
    return f"{'#'*f}{'-'*(n-f)} {int(100*cur/total) if total > 0 else 0}%"

def menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Kabinetlar", callback_data="cabinets"),
         InlineKeyboardButton("O'yinlar", callback_data="games_menu")],
        [InlineKeyboardButton("Reyting", callback_data="leaderboard"),
         InlineKeyboardButton("Profilim", callback_data="profile")],
        [InlineKeyboardButton("MOOC Test", callback_data="mooc_menu"),
         InlineKeyboardButton("AI Suhbat", callback_data="ai_chat")]
    ])

# ── START ─────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.first_name, user.username)
    streak = db.update_streak(user.id)
    st = db.get_user_stats(user.id)
    xp, level = st.get("xp", 0), st.get("level", 1)
    await update.message.reply_text(
        f"🎓 CLEX - Bilimning Yangi Davri\n\n"
        f"Salom, {user.first_name}!\n"
        f"Daraja: {level} | XP: {xp}\n"
        f"{bar(xp % 500, 500)}\n"
        f"🔥 Streak: {streak} kun\n\n"
        f"Bugun ham o'rganamizmi?",
        reply_markup=menu_kb()
    )

# ── ASOSIY MENYU ──────────────────────────────────────
async def main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    st = db.get_user_stats(q.from_user.id)
    await q.edit_message_text(
        f"🎓 CLEX\n"
        f"Daraja: {st.get('level', 1)} | XP: {st.get('xp', 0)}\n"
        f"{bar(st.get('xp', 0) % 500, 500)}\n"
        f"🔥 Streak: {st.get('streak', 0)} kun",
        reply_markup=menu_kb()
    )

# ── KABINETLAR ────────────────────────────────────────
async def show_cabinets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = []
    row = []
    for k, v in CABINETS.items():
        row.append(InlineKeyboardButton(v, callback_data=f"cab_{k}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")])
    await q.edit_message_text("📚 Kabinetni tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_cabinet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cab = q.data.replace("cab_", "")
    uid = q.from_user.id
    s(uid)["cabinet"] = cab
    db.set_cabinet(uid, cab)

    if cab == "lang":
        kb = []
        row = []
        for code, name in LANGUAGES.items():
            row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        # FIX: kb.append tugallanmagan edi
        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="cabinets")])
        await q.edit_message_text("🌍 Qaysi tilni o'rganmoqchisiz?", reply_markup=InlineKeyboardMarkup(kb))
    else:
        subjs = SUBJECTS.get(cab, {})
        kb = [[InlineKeyboardButton(en, callback_data=f"subj_{sn}")] for en, sn in subjs.items()]
        kb.append([InlineKeyboardButton("🔙 Orqaga", callback_data="cabinets")])
        await q.edit_message_text(f"📖 {CABINETS[cab]}\n\nFanni tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_language(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    code = q.data.replace("lang_", "")
    uid = q.from_user.id
    name = LANGUAGES.get(code, code)
    s(uid)["subject"] = name
    db.set_subject(uid, name)
    await show_knowledge_check(q, name)

async def handle_subject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    subj = q.data.replace("subj_", "")
    uid = q.from_user.id
    s(uid)["subject"] = subj
    db.set_subject(uid, subj)
    await show_knowledge_check(q, subj)

async def show_knowledge_check(q, subject):
    kb = [
        [InlineKeyboardButton("🆕 0 dan boshlayman", callback_data="lvl_zero")],
        [InlineKeyboardButton("📚 Biroz bilaman", callback_data="lvl_test")],
        [InlineKeyboardButton("🎯 Yaxshi bilaman", callback_data="lvl_assess")]
    ]
    await q.edit_message_text(
        f"📊 {subject} bo'yicha bilim darajangiz?\n\nAI shaxsiy o'quv reja tuzadi!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ── DARAJA ANIQLASH ───────────────────────────────────
async def handle_level(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    choice = q.data
    ss = s(uid)
    subject = ss.get("subject", "Umumiy")

    if choice == "lvl_zero":
        db.set_knowledge_level(uid, "beginner")
        ss["level"] = "beginner"
        await q.edit_message_text(
            f"✅ {subject} ni noldan boshlaymiz!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📖 Birinchi dars", callback_data="lesson_start")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
    else:
        await q.edit_message_text("⏳ AI savollar tayyorlamoqda...")
        questions = await generate_assessment_questions(subject, 5)
        if questions:
            ss["aq"] = questions
            ss["ai"] = 0
            ss["aa"] = []
            await show_assess_q(q, ss)
        else:
            db.set_knowledge_level(uid, "beginner")
            ss["level"] = "beginner"
            await q.edit_message_text(
                "Boshlang'ich darajadan boshlaymiz!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📖 Dars boshlash", callback_data="lesson_start")]
                ])
            )

async def show_assess_q(q, ss):
    qs = ss["aq"]
    i = ss["ai"]
    qdata = qs[i]
    kb = [[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}", callback_data=f"aq_{j}")]
          for j, opt in enumerate(qdata["options"])]
    await q.edit_message_text(
        f"📝 Savol {i+1}/{len(qs)}\n\n{qdata['question']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_assess(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    ss = s(uid)
    ans = int(q.data.replace("aq_", ""))
    qs = ss["aq"]
    i = ss["ai"]
    ss["aa"].append({
        "question": qs[i]["question"],
        "correct": ans == qs[i]["correct"],
        "user_answer": qs[i]["options"][ans]
    })
    ss["ai"] += 1

    if ss["ai"] >= len(qs):
        await q.edit_message_text("⏳ AI natijalarni tahlil qilmoqda...")
        result = await assess_knowledge(ss.get("subject", "Umumiy"), ss["aa"])
        level = result.get("level", "beginner")
        score = result.get("score", 0)
        db.set_knowledge_level(uid, level)
        ss["level"] = level
        await q.edit_message_text(
            f"📊 Natija!\nBall: {score}/100\nDaraja: {LEVEL_NAMES.get(level, level)}\n\n{result.get('feedback', '')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📖 Darsni boshlash", callback_data="lesson_start")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
    else:
        await show_assess_q(q, ss)

# ── DARSLAR ───────────────────────────────────────────
async def lesson_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    ss = s(uid)
    subject = ss.get("subject", "Umumiy")
    level = ss.get("level", "beginner")
    await q.edit_message_text("⏳ AI dars tayyorlamoqda...")
    topics = await get_topics(subject, level)
    ss["topics"] = topics
    ss["ti"] = 0

    if topics:
        topic = topics[0]
        ss["topic"] = topic
        lesson = await generate_lesson(subject, topic, level)
        db.add_xp(uid, 10)
        # FIX: db.add_badge — xatolik chiqmasligi uchun try/except
        try:
            db.add_badge(uid, "📚 Birinchi Dars")
        except Exception:
            pass
        await q.edit_message_text(
            f"📖 {topic}\n\n{lesson}\n\n💎 +10 XP!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🧪 Test", callback_data="do_quiz"),
                 InlineKeyboardButton("➡️ Keyingi", callback_data="next_topic")],
                [InlineKeyboardButton("🤖 AI dan so'rash", callback_data="ai_chat"),
                 InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
    else:
        await q.edit_message_text(
            "❌ Mavzular yuklanmadi. Qayta urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )

async def next_topic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    ss = s(uid)
    topics = ss.get("topics", [])
    idx = ss.get("ti", 0) + 1
    ss["ti"] = idx

    if idx >= len(topics):
        await q.edit_message_text(
            "🎉 Barcha mavzularni tugatdingiz!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 MOOC Test", callback_data="mooc_menu")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
        return

    subject = ss.get("subject", "Umumiy")
    level = ss.get("level", "beginner")
    topic = topics[idx]
    ss["topic"] = topic
    await q.edit_message_text("⏳ Keyingi dars tayyorlanmoqda...")
    lesson = await generate_lesson(subject, topic, level)
    db.add_xp(uid, 10)
    await q.edit_message_text(
        f"📖 {topic} ({idx+1}/{len(topics)})\n\n{lesson}\n\n💎 +10 XP!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🧪 Test", callback_data="do_quiz"),
             InlineKeyboardButton("➡️ Keyingi", callback_data="next_topic")],
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
        ])
    )

# ── QUIZ ──────────────────────────────────────────────
async def do_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    ss = s(uid)
    subject = ss.get("subject", "Umumiy")
    topic = ss.get("topic", subject)
    level = ss.get("level", "beginner")
    await q.edit_message_text("⏳ Test savollar tayyorlanmoqda...")
    questions = await generate_quiz(subject, topic, level, 5)
    if not questions:
        await q.edit_message_text(
            "❌ Test yuklanmadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
        return
    ss["qq"] = questions
    ss["qi"] = 0
    ss["qs"] = 0
    await show_quiz_q(q, ss)

async def show_quiz_q(q, ss):
    qs = ss["qq"]
    i = ss["qi"]
    qdata = qs[i]
    kb = [[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}", callback_data=f"qz_{j}")]
          for j, opt in enumerate(qdata["options"])]
    await q.edit_message_text(
        f"🧪 Test\nSavol {i+1}/{len(qs)} | Ball: {ss['qs']}\n\n{qdata['question']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    ss = s(uid)
    ans = int(q.data.replace("qz_", ""))
    qs = ss["qq"]
    i = ss["qi"]
    qdata = qs[i]
    correct = ans == qdata["correct"]

    if correct:
        ss["qs"] += 1
        fb = f"✅ To'g'ri!\n{qdata.get('explanation', '')}"
    else:
        fb = f"❌ Noto'g'ri!\nTo'g'ri: {qdata['options'][qdata['correct']]}\n{qdata.get('explanation', '')}"

    ss["qi"] += 1

    if ss["qi"] >= len(qs):
        score = ss["qs"]
        total = len(qs)
        xp = score * 20
        db.save_test_result(uid, ss.get("cabinet", ""), ss.get("subject", ""), score, total)
        db.add_xp(uid, xp)
        await q.edit_message_text(
            f"{fb}\n\n📊 Natija: {score}/{total}\n💎 +{xp} XP",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Qayta test", callback_data="do_quiz"),
                 InlineKeyboardButton("➡️ Keyingi dars", callback_data="next_topic")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
    else:
        next_q = qs[ss["qi"]]
        kb = [[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}", callback_data=f"qz_{j}")]
              for j, opt in enumerate(next_q["options"])]
        await q.edit_message_text(
            f"{fb}\n\nSavol {ss['qi']+1}/{len(qs)}\n\n{next_q['question']}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ── MOOC TEST ─────────────────────────────────────────
async def mooc_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [[InlineKeyboardButton(subj, callback_data=f"mooc_{subj}")] for subj in GAME_SUBJECTS]
    kb.append([InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")])
    await q.edit_message_text(
        "📝 Haftalik MOOC Test\n\nHar Yakshanba yangi test!\n🥇 90%+ Oltin | 🥈 70%+ Kumush | 🥉 50%+ Bronza\n\nFan tanlang:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def start_mooc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    subject = q.data.replace("mooc_", "")
    uid = q.from_user.id
    ss = s(uid)
    await q.edit_message_text(f"⏳ {subject} uchun MOOC test tayyorlanmoqda...")
    questions = await generate_mooc_test(subject, "intermediate")
    if not questions:
        await q.edit_message_text(
            "❌ Test yuklanmadi.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
        return
    ss["mq"] = questions
    ss["ms"] = subject
    ss["mi"] = 0
    ss["msc"] = 0
    await show_mooc_q(q, ss)

async def show_mooc_q(q, ss):
    qs = ss["mq"]
    i = ss["mi"]
    qdata = qs[i]
    kb = [[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}", callback_data=f"ma_{j}")]
          for j, opt in enumerate(qdata["options"])]
    await q.edit_message_text(
        f"📝 MOOC Test\nSavol {i+1}/{len(qs)} | Ball: {ss['msc']}\n\n{qdata['question']}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_mooc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    ss = s(uid)
    ans = int(q.data.replace("ma_", ""))
    qs = ss["mq"]
    i = ss["mi"]
    if ans == qs[i]["correct"]:
        ss["msc"] += 1
    ss["mi"] += 1

    if ss["mi"] >= len(qs):
        score = ss["msc"]
        total = len(qs)
        subject = ss.get("ms", "")
        cert = db.save_mooc_result(uid, subject, score, total)
        xp = score * 30
        db.add_xp(uid, xp)
        await q.edit_message_text(
            f"🎓 MOOC Natija\n{subject}\n{score}/{total} ({int(score/total*100) if total else 0}%)\n{cert}\n💎 +{xp} XP",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Dars o'rganish", callback_data="cabinets")],
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )
    else:
        await show_mooc_q(q, ss)

# ── O'YINLAR MENYUSI ──────────────────────────────────
async def games_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [
        [InlineKeyboardButton("🎯 Viktorina", callback_data="gi_v"),
         InlineKeyboardButton("⚔️ Duello", callback_data="gi_d")],
        [InlineKeyboardButton("💀 Survival", callback_data="gi_s"),
         InlineKeyboardButton("⚡ Speed Round", callback_data="gi_sp")],
        [InlineKeyboardButton("🏆 Turnir", callback_data="gi_t"),
         InlineKeyboardButton("👥 Jamoa Jangi", callback_data="gi_j")],
        [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
    ]
    await q.edit_message_text(
        "🎮 O'yinlar\n\nGuruhga olib boring va do'stlaringiz bilan o'ynang!",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def game_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    infos = {
        "v":  "🎯 Viktorina\nGuruhda: /viktorin\nKim birinchi to'g'ri javob bersa g'olib!",
        "d":  "⚔️ Duello\n1v1 bellashuv\nTez kunda...",
        "s":  "💀 Survival\nNoto'g'ri javob = chiqib ketish\nOxirigacha qol!",
        "sp": "⚡ Speed Round\n60 sekund ichida iloji boricha ko'p savol!",
        "t":  "🏆 Turnir\nHaftalik turnir\nTez kunda...",
        "j":  "👥 Jamoa Jangi\nGuruhda: /team\nTez kunda..."
    }
    key = q.data.replace("gi_", "")
    await q.edit_message_text(
        infos.get(key, "Tez kunda..."),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🎮 O'yinlar", callback_data="games_menu")],
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
        ])
    )

# ── GURUH VIKTORINA ───────────────────────────────────
async def cmd_viktorin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id > 0:
        await update.message.reply_text("❌ Bu buyruq faqat guruhda ishlaydi!")
        return
    import random
    args = ctx.args
    subject = " ".join(args) if args else random.choice(GAME_SUBJECTS)
    active_games[chat_id] = {
        "subject": subject,
        "players": {},
        "scores": {},
        "active": False,
        "current_q": None,
        "answered": set(),
        "start_time": None
    }
    kb = [[InlineKeyboardButton("✋ Qo'shilish", callback_data=f"jn_{chat_id}")]]
    await update.message.reply_text(
        f"🎯 CLEX Viktorina!\nFan: {subject}\n30 sekund ichida qo'shiling!",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    await asyncio.sleep(30)
    game = active_games.get(chat_id)
    if not game or game["active"]:
        return
    if not game["players"]:
        await ctx.bot.send_message(chat_id, "😔 O'yinchi yo'q. /viktorin bilan qayta boshlang.")
        active_games.pop(chat_id, None)
        return
    game["active"] = True
    await run_viktorin(ctx.bot, chat_id, game, subject)

async def join_game(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = int(q.data.replace("jn_", ""))
    user = q.from_user
    game = active_games.get(chat_id)
    if game and not game["active"]:
        game["players"][user.id] = user.first_name
        game["scores"][user.id] = 0
        await q.answer(f"✅ {user.first_name} qo'shildi!", show_alert=True)
    else:
        await q.answer("⏰ O'yin boshlangan yoki tugagan!", show_alert=True)

async def run_viktorin(bot, chat_id, game, subject):
    import random
    for rnd in range(10):
        if chat_id not in active_games:
            return
        question = await generate_game_question(subject)
        if not question:
            continue
        game["current_q"] = question
        game["answered"] = set()
        game["start_time"] = datetime.now()
        kb = [[InlineKeyboardButton(f"{['A','B','C','D'][i]}. {opt}", callback_data=f"va_{i}_{chat_id}")]
              for i, opt in enumerate(question["options"])]
        await bot.send_message(
            chat_id,
            f"❓ Savol {rnd+1}/10\n\n{question['question']}\n\n⏱ 30 sekund!",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await asyncio.sleep(30)
        correct_opt = question["options"][question["correct"]]
        await bot.send_message(chat_id, f"✅ To'g'ri javob: {correct_opt}")
        await asyncio.sleep(3)

    # FIX: "gameph" o'rniga "game" ishlatildi
    game = active_games.pop(chat_id, None)
    if not game:
        return
    scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
    lb = "\n".join([
       f"{i+1}. {game['players'].get(uid, '?')}: {sc} ball"
        for i, (uid, sc) in enumerate(scores[:5])
    ])
    await bot.send_message(
        chat_id,
        f"🏆 Viktorina tugadi!\n\n{lb if lb else 'Hech kim javob bermadi'}\n\nQayta o'ynash: /viktorin"
    )

async def viktorin_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split("_")
    ans = int(parts[1])
    chat_id = int(parts[2])
    user = q.from_user
    game = active_games.get(chat_id)

    if not game:
        await q.answer("⏰ O'yin tugagan.", show_alert=True)
        return
    if user.id in game.get("answered", set()):
        await q.answer("❕ Allaqachon javob berdingiz!", show_alert=True)
        return

    game["answered"].add(user.id)
    qdata = game.get("current_q", {})

    if ans == qdata.get("correct", -1):
        elapsed = int((datetime.now() - game["start_time"]).total_seconds())
        pts = max(10, 30 - elapsed)
        game["scores"][user.id] = game["scores"].get(user.id, 0) + pts
        db.add_xp(user.id, pts)
        await q.answer(f"✅ To'g'ri! +{pts} ball!", show_alert=True)
    else:
        await q.answer("❌ Noto'g'ri!", show_alert=True)

# ── PROFIL ────────────────────────────────────────────
async def show_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = db.get_user_stats(uid)
    # FIX: get_badges bo'lmasa ham ishlasin
    try:
        badges = db.get_badges(uid)
        badge_text = "\n".join([f"  {b[0]}" for b in badges]) if badges else "  Hali badge yo'q"
    except Exception:
        badge_text = "  Hali badge yo'q"

    xp = st.get("xp", 0)
    level = st.get("level", 1)
    await q.edit_message_text(
        f"👤 Profilim\n\n"
        f"⭐ Daraja: {level}\n"
        f"💎 XP: {xp}\n"
        f"{bar(xp % 500, 500)}\n"
        f"🔥 Streak: {st.get('streak', 0)} kun\n"
        f"📚 Fan: {st.get('subject', '—')}\n\n"
        f"🎖 Badgelar:\n{badge_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
        ])
    )

# ── REYTING ───────────────────────────────────────────
async def show_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    leaders = db.get_leaderboard(10)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text = "🏆 Top O'quvchilar\n\n"
    for i, (name, xp, level, streak) in enumerate(leaders):
        text += f"{medals[i]} {name} — {xp} XP | Daraja {level} | 🔥{streak}\n"
    if not leaders:
        text += "Hali hech kim yo'q!"
    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
        ])
    )

# ── AI SUHBAT ─────────────────────────────────────────
async def ai_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    ss = s(uid)
    ss["mode"] = "chat"
    ss["history"] = []
    subject = ss.get("subject", "Umumiy")
    await q.edit_message_text(
        f"🤖 AI O'qituvchi\n\n"
        f"📚 {subject} bo'yicha savol bering!\n"
        f"Har qanday tilda yozishingiz mumkin.\n\n"
        f"Chiqish uchun: /stop"
    )

async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ss = s(uid)
    text = update.message.text

    if ss.get("mode") == "chat":
        reply = await chat_with_ai(
            text,
            ss.get("subject", "Umumiy"),
            ss.get("level", "beginner"),
            ss.get("history", [])
        )
        ss.setdefault("history", []).append({"role": "user", "content": text})
        ss["history"].append({"role": "assistant", "content": reply})
        ss["history"] = ss["history"][-10:]
        db.add_xp(uid, 2)
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text(
            "📚 Menyu uchun /start bosing",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
            ])
        )

async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s(update.effective_user.id)["mode"] = None
    await update.message.reply_text(
        "✅ Tugatildi.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Bosh sahifa", callback_data="main_menu")]
        ])
    )

# ── MAIN ──────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Buyruqlar
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("stop",     stop))
    app.add_handler(CommandHandler("viktorin", cmd_viktorin))

    # Callback handlerlari
    app.add_handler(CallbackQueryHandler(main_menu,        pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(show_cabinets,    pattern="^cabinets$"))
    app.add_handler(CallbackQueryHandler(handle_cabinet,   pattern="^cab_"))
    app.add_handler(CallbackQueryHandler(handle_language,  pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(handle_subject,   pattern="^subj_"))
    app.add_handler(CallbackQueryHandler(handle_level,     pattern="^lvl_"))
    app.add_handler(CallbackQueryHandler(handle_assess,    pattern="^aq_"))
    app.add_handler(CallbackQueryHandler(lesson_start,     pattern="^lesson_start$"))
    app.add_handler(CallbackQueryHandler(next_topic,       pattern="^next_topic$"))
    app.add_handler(CallbackQueryHandler(do_quiz,          pattern="^do_quiz$"))
    app.add_handler(CallbackQueryHandler(handle_quiz,      pattern="^qz_"))
    app.add_handler(CallbackQueryHandler(mooc_menu,        pattern="^mooc_menu$"))
    app.add_handler(CallbackQueryHandler(start_mooc,       pattern="^mooc_"))
    app.add_handler(CallbackQueryHandler(handle_mooc,      pattern="^ma_"))
    app.add_handler(CallbackQueryHandler(games_menu,       pattern="^games_menu$"))
    app.add_handler(CallbackQueryHandler(game_info,        pattern="^gi_"))
    app.add_handler(CallbackQueryHandler(join_game,        pattern="^jn_"))
    app.add_handler(CallbackQueryHandler(viktorin_answer,  pattern="^va_"))
    app.add_handler(CallbackQueryHandler(show_profile,     pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(show_leaderboard, pattern="^leaderboard$"))
    app.add_handler(CallbackQueryHandler(ai_chat,          pattern="^ai_chat$"))

    # Matn handleri
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))

    print("🎓 CLEX Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
