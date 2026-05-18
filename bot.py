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
SUBJECTS = {"math":{"Matematika":"Matematika","Fizika":"Fizika","Informatika":"Informatika"},"chem":{"Kimyo":"Kimyo","Biologiya":"Biologiya"},"hum":{"Tarix":"Tarix","Adabiyot":"Adabiyot"},"soc":{"Geografiya":"Geografiya","Iqtisodiyot":"Iqtisodiyot"},"it":{"Python":"Python","Web":"Web"},"art":{"Dizayn":"Dizayn"}}
GAME_SUBJECTS = ["Ingliz tili","Matematika","Kimyo","Biologiya","Tarix","Geografiya","Fizika","Informatika"]
LEVEL_NAMES = {"beginner":"Boshlangich","elementary":"Asosiy","intermediate":"Orta","upper":"Yuqori","advanced":"Ilgor","master":"Ustoz"}

def s(uid):
    if uid not in user_sessions: user_sessions[uid] = {}
    return user_sessions[uid]

def bar(cur, total, n=10):
    f = int(n*cur/total) if total>0 else 0
    return f"{'#'*f}{'-'*(n-f)} {int(100*cur/total) if total>0 else 0}%"

def menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Kabinetlar",callback_data="cabinets"),InlineKeyboardButton("Oyinlar",callback_data="games_menu")],
        [InlineKeyboardButton("Reyting",callback_data="leaderboard"),InlineKeyboardButton("Profilim",callback_data="profile")],
        [InlineKeyboardButton("MOOC Test",callback_data="mooc_menu"),InlineKeyboardButton("AI Suhbat",callback_data="ai_chat")]
    ])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.first_name, user.username)
    streak = db.update_streak(user.id)
    st = db.get_user_stats(user.id)
    xp, level = st.get("xp",0), st.get("level",1)
    await update.message.reply_text(f"CLEX - Bilimning Yangi Davri\n\nSalom, {user.first_name}!\nDaraja: {level} | XP: {xp}\n{bar(xp%500,500)}\nStreak: {streak} kun\n\nBugun ham organamizmi?", reply_markup=menu_kb())

async def main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    st = db.get_user_stats(q.from_user.id)
    await q.edit_message_text(f"CLEX\nDaraja: {st.get('level',1)} | XP: {st.get('xp',0)}\n{bar(st.get('xp',0)%500,500)}\nStreak: {st.get('streak',0)} kun", reply_markup=menu_kb())

async def show_cabinets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb = []; row = []
    for k,v in CABINETS.items():
        row.append(InlineKeyboardButton(v,callback_data=f"cab_{k}"))
        if len(row)==2: kb.append(row); row=[]
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")])
    await q.edit_message_text("Kabinetni tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_cabinet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cab = q.data.replace("cab_",""); uid = q.from_user.id
    s(uid)["cabinet"] = cab; db.set_cabinet(uid, cab)
    if cab=="lang":
        kb=[]; row=[]
        for code,name in LANGUAGES.items():
            row.append(InlineKeyboardButton(name,callback_data=f"lang_{code}"))
            if len(row)==3: kb.append(row); row=[]
        if row: kb.append(row)
        kb.append([InlineKeyboardButton("Orqaga",callback_data="cabinets")])
        await q.edit_message_text("Qaysi tilni organmoqchisiz?",reply_markup=InlineKeyboardMarkup(kb))
    else:
        subjs = SUBJECTS.get(cab,{})
        kb=[[InlineKeyboardButton(en,callback_data=f"subj_{sn}")] for en,sn in subjs.items()]
        kb.append([InlineKeyboardButton("Orqaga",callback_data="cabinets")])
        await q.edit_message_text(f"{CABINETS[cab]}\n\nFanni tanlang:",reply_markup=InlineKeyboardMarkup(kb))

async def handle_language(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    code = q.data.replace("lang_",""); uid = q.from_user.id
    name = LANGUAGES.get(code,code); s(uid)["subject"] = name; db.set_subject(uid, name)
    await show_knowledge_check(q, name)

async def handle_subject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    subj = q.data.replace("subj_",""); uid = q.from_user.id
    s(uid)["subject"] = subj; db.set_subject(uid, subj)
    await show_knowledge_check(q, subj)

async def show_knowledge_check(q, subject):
    kb=[[InlineKeyboardButton("0 dan boshlayman",callback_data="lvl_zero")],[InlineKeyboardButton("Biroz bilaman",callback_data="lvl_test")],[InlineKeyboardButton("Yaxshi bilaman",callback_data="lvl_assess")]]
    await q.edit_message_text(f"{subject} boyicha bilim darajangiz?\n\nAI shaxsiy oquv reja tuzadi!", reply_markup=InlineKeyboardMarkup(kb))

async def handle_level(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; choice = q.data; ss = s(uid)
    subject = ss.get("subject","Umumiy")
    if choice=="lvl_zero":
        db.set_knowledge_level(uid,"beginner"); ss["level"]="beginner"
        await q.edit_message_text(f"{subject} ni noldan boshlaymiz!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Birinchi dars",callback_data="lesson_start")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))
    else:
        await q.edit_message_text("AI savollar tayyorlamoqda...")
        questions = await generate_assessment_questions(subject, 5)
        if questions:
            ss["aq"]=questions; ss["ai"]=0; ss["aa"]=[]
            await show_assess_q(q, ss)
        else:
            db.set_knowledge_level(uid,"beginner"); ss["level"]="beginner"
            await q.edit_message_text("Boshlangich darajadan boshlaymiz!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Dars boshlash",callback_data="lesson_start")]]))

async def show_assess_q(q, ss):
    qs=ss["aq"]; i=ss["ai"]; qdata=qs[i]
    kb=[[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}",callback_data=f"aq_{j}")] for j,opt in enumerate(qdata["options"])]
    await q.edit_message_text(f"Savol {i+1}/{len(qs)}\n\n{qdata['question']}", reply_markup=InlineKeyboardMarkup(kb))

async def handle_assess(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ss = s(uid); ans = int(q.data.replace("aq_",""))
    qs=ss["aq"]; i=ss["ai"]
    ss["aa"].append({"question":qs[i]["question"],"correct":ans==qs[i]["correct"],"user_answer":qs[i]["options"][ans]})
    ss["ai"]+=1
    if ss["ai"]>=len(qs):
        await q.edit_message_text("AI natijalarni tahlil qilmoqda...")
        result = await assess_knowledge(ss.get("subject","Umumiy"), ss["aa"])
        level=result.get("level","beginner"); score=result.get("score",0)
        db.set_knowledge_level(uid,level); ss["level"]=level
        await q.edit_message_text(f"Natija!\nBall: {score}/100\nDaraja: {LEVEL_NAMES.get(level,level)}\n\n{result.get('feedback','')}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Darsni boshlash",callback_data="lesson_start")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))
    else:
        await show_assess_q(q, ss)

async def lesson_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ss = s(uid)
    subject=ss.get("subject","Umumiy"); level=ss.get("level","beginner")
    await q.edit_message_text("AI dars tayyorlamoqda...")
    topics = await get_topics(subject, level)
    ss["topics"]=topics; ss["ti"]=0
    if topics:
        topic=topics[0]; ss["topic"]=topic
        lesson = await generate_lesson(subject,topic,level)
        db.add_xp(uid,10); db.add_badge(uid,"Birinchi Dars")
        await q.edit_message_text(f"{topic}\n\n{lesson}\n\n+10 XP!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Test",callback_data="do_quiz"),InlineKeyboardButton("Keyingi",callback_data="next_topic")],[InlineKeyboardButton("AI dan sorash",callback_data="ai_chat"),InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))

async def next_topic(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ss = s(uid)
    topics=ss.get("topics",[]); idx=ss.get("ti",0)+1; ss["ti"]=idx
    if idx>=len(topics):
        await q.edit_message_text("Barcha mavzularni tugatdingiz!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("MOOC Test",callback_data="mooc_menu")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]])); return
    subject=ss.get("subject","Umumiy"); level=ss.get("level","beginner")
    topic=topics[idx]; ss["topic"]=topic
    await q.edit_message_text("Keyingi dars tayyorlanmoqda...")
    lesson = await generate_lesson(subject,topic,level)
    db.add_xp(uid,10)
    await q.edit_message_text(f"{topic} ({idx+1}/{len(topics)})\n\n{lesson}\n\n+10 XP!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Test",callback_data="do_quiz"),InlineKeyboardButton("Keyingi",callback_data="next_topic")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))

async def do_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ss = s(uid)
    subject=ss.get("subject","Umumiy"); topic=ss.get("topic",subject); level=ss.get("level","beginner")
    await q.edit_message_text("Test savollar tayyorlanmoqda...")
    questions = await generate_quiz(subject,topic,level,5)
    if not questions:
        await q.edit_message_text("Test yuklanmadi."); return
    ss["qq"]=questions; ss["qi"]=0; ss["qs"]=0
    await show_quiz_q(q,ss)

async def show_quiz_q(q,ss):
    qs=ss["qq"]; i=ss["qi"]; qdata=qs[i]
    kb=[[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}",callback_data=f"qz_{j}")] for j,opt in enumerate(qdata["options"])]
    await q.edit_message_text(f"Test\nSavol {i+1}/{len(qs)} | Ball: {ss['qs']}\n\n{qdata['question']}", reply_markup=InlineKeyboardMarkup(kb))

async def handle_quiz(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid = q.from_user.id; ss = s(uid); ans = int(q.data.replace("qz_",""))
    qs=ss["qq"]; i=ss["qi"]; qdata=qs[i]
    correct = ans==qdata["correct"]
    if correct: ss["qs"]+=1; fb=f"Togri!\n{qdata.get('explanation','')}"
    else: fb=f"Notogri!\nTogri: {qdata['options'][qdata['correct']]}\n{qdata.get('explanation','')}"
    ss["qi"]+=1
    if ss["qi"]>=len(qs):
        score=ss["qs"]; total=len(qs); xp=score*20
        db.save_test_result(uid,ss.get("cabinet",""),ss.get("subject",""),score,total)
        db.add_xp(uid,xp)
        await q.edit_message_text(f"{fb}\n\nNatija: {score}/{total}\n+{xp} XP", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Qayta test",callback_data="do_quiz"),InlineKeyboardButton("Keyingi dars",callback_data="next_topic")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))
    else:
        next_q=qs[ss["qi"]]
        kb=[[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}",callback_data=f"qz_{j}")] for j,opt in enumerate(next_q["options"])]
        await q.edit_message_text(f"{fb}\n\nSavol {ss['qi']+1}/{len(qs)}\n\n{next_q['question']}", reply_markup=InlineKeyboardMarkup(kb))

async def mooc_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()kb=[[InlineKeyboardButton(s,callback_data=f"mooc_{s}")] for s in GAME_SUBJECTS]
    kb.append([InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")])
    await q.edit_message_text("Haftalik MOOC Test\n\nHar Yakshanba yangi test!\n90%+ Oltin | 70%+ Kumush | 50%+ Bronza\n\nFan tanlang:", reply_markup=InlineKeyboardMarkup(kb))

async def start_mooc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    subject=q.data.replace("mooc_",""); uid=q.from_user.id; ss=s(uid)
    await q.edit_message_text(f"{subject} uchun MOOC test tayyorlanmoqda...")
    questions = await generate_mooc_test(subject,"intermediate")
    if not questions:
        await q.edit_message_text("Test yuklanmadi."); return
    ss["mq"]=questions; ss["ms"]=subject; ss["mi"]=0; ss["msc"]=0
    await show_mooc_q(q,ss)

async def show_mooc_q(q,ss):
    qs=ss["mq"]; i=ss["mi"]; qdata=qs[i]
    kb=[[InlineKeyboardButton(f"{['A','B','C','D'][j]}. {opt}",callback_data=f"ma_{j}")] for j,opt in enumerate(qdata["options"])]
    await q.edit_message_text(f"MOOC Test\nSavol {i+1}/{len(qs)} | Ball: {ss['msc']}\n\n{qdata['question']}", reply_markup=InlineKeyboardMarkup(kb))

async def handle_mooc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    uid=q.from_user.id; ss=s(uid); ans=int(q.data.replace("ma_",""))
    qs=ss["mq"]; i=ss["mi"]
    if ans==qs[i]["correct"]: ss["msc"]+=1
    ss["mi"]+=1
    if ss["mi"]>=len(qs):
        score=ss["msc"]; total=len(qs); subject=ss.get("ms","")
        cert=db.save_mooc_result(uid,subject,score,total); xp=score*30
        db.add_xp(uid,xp)
        await q.edit_message_text(f"MOOC Natija\n{subject}\n{score}/{total} ({int(score/total*100)}%)\n{cert}\n+{xp} XP", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Dars organish",callback_data="cabinets")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))
    else:
        await show_mooc_q(q,ss)

async def games_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kb=[[InlineKeyboardButton("Viktorina",callback_data="gi_v"),InlineKeyboardButton("Duello",callback_data="gi_d")],[InlineKeyboardButton("Survival",callback_data="gi_s"),InlineKeyboardButton("Speed Round",callback_data="gi_sp")],[InlineKeyboardButton("Turnir",callback_data="gi_t"),InlineKeyboardButton("Jamoa Jangi",callback_data="gi_j")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]
    await q.edit_message_text("Oyinlar\n\nGuruhga olib boring va dostlaringiz bilan oynang!", reply_markup=InlineKeyboardMarkup(kb))

async def game_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    infos={"v":"Viktorina\nGuruhda: /viktorin","d":"Duello\n1v1","s":"Survival\nNotogri=chiqib ketish","sp":"Speed Round\n60 sekund","t":"Turnir\nTez kunda...","j":"Jamoa Jangi\nGuruhda: /team"}
    await q.edit_message_text(infos.get(q.data.replace("gi_",""),""), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Oyinlar",callback_data="games_menu")],[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))

async def cmd_viktorin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id=update.effective_chat.id
    if chat_id>0:
        await update.message.reply_text("Faqat guruhda!"); return
    import random
    args=ctx.args; subject=" ".join(args) if args else random.choice(GAME_SUBJECTS)
    active_games[chat_id]={"subject":subject,"players":{},"scores":{},"active":False,"current_q":None,"answered":set(),"start_time":None}
    kb=[[InlineKeyboardButton("Qoshilish",callback_data=f"jn_{chat_id}")]]
    await update.message.reply_text(f"CLEX Viktorina!\nFan: {subject}\n30 sekund ichida qoshiling!", reply_markup=InlineKeyboardMarkup(kb))
    await asyncio.sleep(30)
    game=active_games.get(chat_id)
    if not game or game["active"]: return
    if not game["players"]:
        await ctx.bot.send_message(chat_id,"Oyinchi yoq.")
        active_games.pop(chat_id,None); returngame["active"]=True
    await run_viktorin(ctx.bot, chat_id, game, subject)

async def join_game(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    chat_id=int(q.data.replace("jn_","")); user=q.from_user
    game=active_games.get(chat_id)
    if game and not game["active"]:
        game["players"][user.id]=user.first_name; game["scores"][user.id]=0
        await q.answer(f"{user.first_name} qoshildi!",show_alert=True)

async def run_viktorin(bot, chat_id, game, subject):
    import random
    for rnd in range(10):
        if chat_id not in active_games: return
        question=await generate_game_question(random.choice(GAME_SUBJECTS) if subject=="Aralash" else subject)
        if not question: continue
        game["current_q"]=question; game["answered"]=set(); game["start_time"]=datetime.now()
        kb=[[InlineKeyboardButton(f"{['A','B','C','D'][i]}. {opt}",callback_data=f"va_{i}_{chat_id}")] for i,opt in enumerate(question["options"])]
        await bot.send_message(chat_id,f"Savol {rnd+1}/10\n\n{question['question']}\n\n30 sekund!", reply_markup=InlineKeyboardMarkup(kb))
        await asyncio.sleep(30)
        await bot.send_message(chat_id,f"Togri javob: {question['options'][question['correct']]}")
        await asyncio.sleep(3)
    game=active_games.pop(chat_id,None)
    if not gameph: return
    scores=sorted(game["scores"].items(),key=lambda x:x[1],reverse=True)
    lb="\n".join([f"{i+1}. {game['players'].get(uid,'?')}: {sc} ball" for i,(uid,sc) in enumerate(scores[:5])])
    await bot.send_message(chat_id,f"Viktorina tugadi!\n\n{lb}\n\nQayta: /viktorin")

async def viktorin_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    parts=q.data.split("_"); ans=int(parts[1]); chat_id=int(parts[2]); user=q.from_user
    game=active_games.get(chat_id)
    if not game: await q.answer("Oyin tugagan."); return
    if user.id in game.get("answered",set()):
        await q.answer("Allaqachon javob berdingiz!"); return
    game["answered"].add(user.id)
    qdata=game.get("current_q",{})
    if ans==qdata.get("correct",999):
        elapsed=int((datetime.now()-game["start_time"]).total_seconds())
        pts=max(10,30-elapsed); game["scores"][user.id]=game["scores"].get(user.id,0)+pts
        db.add_xp(user.id,pts); await q.answer(f"Togri! +{pts} ball!")
    else:
        await q.answer("Notogri!")

async def show_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); uid=q.from_user.id
    st=db.get_user_stats(uid); badges=db.get_badges(uid)
    badge_text="\n".join([f"  {b[0]}" for b in badges]) or "  Hali badge yoq"
    await q.edit_message_text(f"Profilim\nDaraja: {st.get('level',1)}\nXP: {st.get('xp',0)}\nStreak: {st.get('streak',0)} kun\nFan: {st.get('subject','—')}\n\nBadgelar:\n{badge_text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))

async def show_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    leaders=db.get_leaderboard(10)
    text="Top Oquvchilar\n\n"
    for i,(name,xp,level,streak) in enumerate(leaders):
        text+=f"{i+1}. {name} - {xp} XP | Daraja {level}\n"
    if not leaders: text+="Hali hech kim yoq!"
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))

async def ai_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); uid=q.from_user.id; ss=s(uid)
    ss["mode"]="chat"; ss["history"]=[]; subject=ss.get("subject","Umumiy")
    await q.edit_message_text(f"AI Oqituvchi\n\n{subject} boyicha savol bering!\n\nChiqish: /stop")

async def handle_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id; ss=s(uid); text=update.message.text
    if ss.get("mode")=="chat":
        reply=await chat_with_ai(text,ss.get("subject","Umumiy"),ss.get("level","beginner"),ss.get("history",[]))
        ss.setdefault("history",[]).append({"role":"user","content":text})
        ss["history"].append({"role":"assistant","content":reply})
        ss["history"]=ss["history"][-10:]; db.add_xp(uid,2)
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("Menyu uchun /start bosing", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))

async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s(update.effective_user.id)["mode"]=None
    await update.message.reply_text("Tugatildi.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Bosh sahifa",callback_data="main_menu")]]))

def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("stop",stop))
    app.add_handler(CommandHandler("viktorin",cmd_viktorin))
    app.add_handler(CallbackQueryHandler(main_menu,pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(show_cabinets,pattern="^cabinets$"))
    app.add_handler(CallbackQueryHandler(handle_cabinet,pattern="^cab_"))
    app.add_handler(CallbackQueryHandler(handle_language,pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(handle_subject,pattern="^subj_"))
    app.add_handler(CallbackQueryHandler(handle_level,pattern="^lvl_"))
    app.add_handler(CallbackQueryHandler(handle_assess,pattern="^aq_"))
    app.add_handler(CallbackQueryHandler(lesson_start,pattern="^lesson_start$"))
    app.add_handler(CallbackQueryHandler(next_topic,pattern="^next_topic$"))
    app.add_handler(CallbackQueryHandler(do_quiz,pattern="^do_quiz$"))
    app.add_handler(CallbackQueryHandler(handle_quiz,pattern="^qz_"))
    app.add_handler(CallbackQueryHandler(mooc_menu,pattern="^mooc_menu$"))
    app.add_handler(CallbackQueryHandler(start_mooc,pattern="^mooc_"))
    app.add_handler(CallbackQueryHandler(handle_mooc,pattern="^ma_"))
    app.add_handler(CallbackQueryHandler(games_menu,pattern="^games_menu$"))
    app.add_handler(CallbackQueryHandler(game_info,pattern="^gi_"))
    app.add_handler(CallbackQueryHandler(join_game,pattern="^jn_"))
    app.add_handler(CallbackQueryHandler(viktorin_answer,pattern="^va_"))
    app.add_handler(CallbackQueryHandler(show_profile,pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(show_leaderboard,pattern="^leaderboard$"))
    app.add_handler(CallbackQueryHandler(ai_chat,pattern="^ai_chat$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    print("CLEX Bot ishga tushdi!")
    
    # Railway-da barqaror ishlashi uchun asosiy tsikl
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    app.run_polling()

if __name__=="__main__":
    main()
