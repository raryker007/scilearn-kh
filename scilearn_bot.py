#!/usr/bin/env python3
"""
SciLearn KH — Telegram Bot (Termux Version)
============================================
Grade 11 Science AI Tutor Bot — Gemini REST API (no grpc needed!)

SETUP IN TERMUX:
  pip install python-telegram-bot python-dotenv requests
  python scilearn_bot.py

REQUIRED ENV VARS (.env file):
  TELEGRAM_BOT_TOKEN=your_bot_token_here
  GEMINI_API_KEY=your_gemini_api_key_here
"""

import os
import logging
import asyncio
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode, ChatAction

# ─── Load environment variables ──────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    raise RuntimeError("❌ Missing TELEGRAM_BOT_TOKEN or GEMINI_API_KEY in .env file!")

# ─── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Gemini REST API ──────────────────────────────────────────────────
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SYSTEM_INSTRUCTION = """
You are Prof. Gemini, an expert science teacher specializing in the Grade 11
high school curriculum in Cambodia. You are accessed via Telegram.

YOUR ROLE:
- Teach Physics, Chemistry, Biology, and Mathematics at Grade 11 level.
- Give clear, structured, step-by-step explanations.
- Use simple language first, then introduce technical terms with definitions.
- Always show worked examples when solving problems.
- Encourage students with positive, supportive language.
- Format responses for Telegram (use plain text, not markdown tables).

STRICT BOUNDARIES:
- ONLY answer questions related to: Physics, Chemistry, Biology, Mathematics (Grade 11).
- If asked about anything else, reply:
  "I'm specialized for Grade 11 science subjects only! 📚
   Please ask me about Physics, Chemistry, Biology, or Math."
- Do NOT answer general knowledge, politics, entertainment, or off-topic questions.
- Always TEACH — never just give answers without explanation.

FORMATTING FOR TELEGRAM:
- Use numbered lists for steps: 1. 2. 3.
- Use *asterisks* for key terms (Telegram bold).
- Keep responses under 500 words for readability on mobile.
- Add a relevant emoji at the start of key points.
"""

# ─── Subjects ─────────────────────────────────────────────────────────
SUBJECTS = {
    "⚛️ Physics":   ["Newton's Laws", "Kinematics", "Waves", "Thermodynamics", "Electricity", "Optics"],
    "🧪 Chemistry": ["Atomic Structure", "Chemical Bonds", "Mole Concept", "Reactions", "Organic Chem", "Acids & Bases"],
    "🧬 Biology":   ["Cell Biology", "Genetics", "DNA & RNA", "Photosynthesis", "Respiration", "Ecology"],
    "📐 Math":      ["Calculus", "Trigonometry", "Logarithms", "Sequences", "Statistics", "Vectors"],
}

# ─── Session Storage ──────────────────────────────────────────────────
user_sessions: dict = {}

def get_or_create_session(user_id: int, subject: str = "General Science"):
    if user_id not in user_sessions or user_sessions[user_id]["subject"] != subject:
        user_sessions[user_id] = {
            "subject": subject,
            "history": [],
            "message_count": 0,
        }
        logger.info(f"New session: user={user_id} subject={subject}")
    return user_sessions[user_id]

# ─── Gemini Call ──────────────────────────────────────────────────────
def call_gemini(history: list, subject: str) -> str:
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": history,
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.85,
            "maxOutputTokens": 800,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT",  "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ],
    }
    response = requests.post(url, json=payload, timeout=30)
    data = response.json()
    if not response.ok:
        raise Exception(data.get("error", {}).get("message", "Gemini API error"))
    return data["candidates"][0]["content"]["parts"][0]["text"]

# ─── Handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 *Welcome, {user.first_name}!*\n\n"
        "I'm *Prof. Gemini* — your Grade 11 Science Tutor 🎓\n\n"
        "⚛️ *Physics* — Mechanics, Waves, Electricity\n"
        "🧪 *Chemistry* — Bonds, Reactions, Organic\n"
        "🧬 *Biology* — Cells, Genetics, Ecology\n"
        "📐 *Math* — Calculus, Algebra, Statistics\n\n"
        "Use /subject to pick a subject, or just ask your question!\n"
        "Use /help to see all commands.",
        parse_mode=None
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *SciLearn KH — Commands*\n\n"
        "/start — Welcome message\n"
        "/subject — Choose your subject\n"
        "/topics — Browse topics\n"
        "/reset — Fresh conversation\n"
        "/status — Current session info\n"
        "/help — Show this message\n\n"
        "💡 Just type any science question!",
        parse_mode=None
    )

async def subject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(s, callback_data=f"subject:{s}")] for s in SUBJECTS]
    await update.message.reply_text(
        "📖 *Choose your subject:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=None
    )

async def topics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(s, callback_data=f"showtopics:{s}")] for s in SUBJECTS]
    await update.message.reply_text(
        "🗂 *Which subject topics?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=None
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_sessions:
        del user_sessions[uid]
    await update.message.reply_text(
        "🔄 *Conversation reset!* Starting fresh.\nUse /subject or ask a question.",
        parse_mode=None
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_sessions:
        await update.message.reply_text("No active session. Use /subject to start!")
        return
    s = user_sessions[uid]
    await update.message.reply_text(
        f"📊 *Your Session*\n\nSubject: {s['subject']}\nMessages: {s['message_count']}\n\nUse /reset to clear.",
        parse_mode=None
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data.startswith("subject:"):
        subj = data.split(":", 1)[1]
        get_or_create_session(uid, subj)
        await query.edit_message_text(
            f"✅ Subject set to *{subj}*\nAsk me anything! 🎓",
            parse_mode=None
        )

    elif data.startswith("showtopics:"):
        subj = data.split(":", 1)[1]
        kb = [
            [InlineKeyboardButton(f"📌 {t}", callback_data=f"asktopic:{subj}:{t}")]
            for t in SUBJECTS[subj]
        ]
        kb.append([InlineKeyboardButton("⬅️ Back", callback_data="backtotopics")])
        await query.edit_message_text(
            f"📚 *{subj} Topics:*\nTap to learn!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=None
        )

    elif data.startswith("asktopic:"):
        _, subj, topic = data.split(":", 2)
        sess = get_or_create_session(uid, subj)
        await query.edit_message_text(f"🔍 Loading *{topic}*...", parse_mode=None)
        prompt = f"[Subject: {subj}] Explain {topic} for Grade 11. Give key concepts and one worked example."
        sess["history"].append({"role": "user", "parts": [{"text": prompt}]})
        try:
            reply = await asyncio.to_thread(call_gemini, sess["history"], subj)
            sess["history"].append({"role": "model", "parts": [{"text": reply}]})
            sess["message_count"] += 1
            await query.edit_message_text(
                f"📖 *{topic}* ({subj})\n\n{reply}",
                parse_mode=None
            )
        except Exception as e:
            sess["history"].pop()
            await query.edit_message_text(f"⚠️ Error: {e}")

    elif data == "backtotopics":
        kb = [[InlineKeyboardButton(s, callback_data=f"showtopics:{s}")] for s in SUBJECTS]
        await query.edit_message_text(
            "🗂 *Choose a subject:*",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=None
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    if not text:
        return

    sess = get_or_create_session(uid)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    prompt = f"[Subject: {sess['subject']}]\n\n{text}"
    sess["history"].append({"role": "user", "parts": [{"text": prompt}]})

    try:
        reply = await asyncio.to_thread(call_gemini, sess["history"], sess["subject"])
        sess["history"].append({"role": "model", "parts": [{"text": reply}]})
        sess["message_count"] += 1
        if len(reply) > 3800:
            reply = reply[:3800] + "\n\n_(trimmed — ask me to continue!)_"
        await update.message.reply_text(reply, parse_mode=None)
    except Exception as e:
        sess["history"].pop()
        logger.error(f"Error user={uid}: {e}")
        await update.message.reply_text(
            f"⚠️ *Error:* {e}\n\nTry /reset",
            parse_mode=None
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

# ─── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("  SciLearn KH Bot — Gemini REST API")
    print("  Grade 11 Science Tutor")
    print("=" * 50)
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("help",    help_command))
    app.add_handler(CommandHandler("subject", subject_command))
    app.add_handler(CommandHandler("topics",  topics_command))
    app.add_handler(CommandHandler("reset",   reset_command))
    app.add_handler(CommandHandler("status",  status_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
