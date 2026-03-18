import asyncio
import re
from datetime import datetime

import dateparser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# --- الإعدادات ---
API_ID = 34257542
API_HASH = "614a1b5c5b712ac6de5530d5c571c42a"
BOT_TOKEN = "8543191006:AAFGAWKQa23bt26qYJ86MkvrjYXz_5d2gAA"
ADMIN_ID = 1486879970

app = Client("FaisalBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = AsyncioScheduler()

# مخزن مؤقت لحفظ الحالات
user_states = {}


# --- وظائف مساعدة ---


def get_countdown_markup(target_date):
    now = datetime.now()
    diff = target_date - now
    if diff.total_seconds() <= 0:
        return None

    days = diff.days
    weeks = days // 7
    hours = int(diff.total_seconds() // 3600)

    if days < 1:
        minutes = int((diff.total_seconds() % 3600) // 60)
        seconds = int(diff.total_seconds() % 60)
        btns = [
            [
                InlineKeyboardButton(f"{hours} ساعة", callback_data="n"),
                InlineKeyboardButton(f"{minutes} دقيقة", callback_data="n"),
                InlineKeyboardButton(f"{seconds} ثانية", callback_data="n"),
            ]
        ]
    else:
        btns = [
            [
                InlineKeyboardButton(f"{days} يوم", callback_data="n"),
                InlineKeyboardButton(f"{weeks} أسبوع", callback_data="n"),
            ],
            [InlineKeyboardButton(f"{hours} ساعة", callback_data="n")],
        ]
    return InlineKeyboardMarkup(btns)


async def send_scheduled_msg(chat_id, msg_type, content, caption=None, target_date=None):
    try:
        if msg_type == "text":
            await app.send_message(chat_id, content)
        elif msg_type == "photo":
            await app.send_photo(chat_id, content, caption=caption)
        elif msg_type == "video":
            await app.send_video(chat_id, content, caption=caption)
        elif msg_type == "counter":
            markup = get_countdown_markup(target_date)
            await app.send_message(chat_id, f"⏳ {content}", reply_markup=markup)
    except Exception as e:
        print(f"Error: {e}")


def parse_interval(text):
    nums = re.findall(r"\d+", text)
    val = int(nums[0]) if nums else 1
    if "دقيق" in text:
        return {"minutes": val}
    if "ساع" in text:
        return {"hours": val}
    if "يوم" in text:
        return {"days": val}
    return {"days": 1}


# --- معالجة الأوامر ---

is_admin = filters.user(ADMIN_ID)


@app.on_message(is_admin & filters.regex(r"عداد \((.*)\) \((.*)\)"))
async def counter_cmd(client, message):
    text, time_str = message.matches[0].group(1), message.matches[0].group(2)
    target_date = dateparser.parse(time_str, settings={"PREFER_DATES_FROM": "future"})

    if not target_date:
        return await message.reply("❌ لم أفهم الوقت.")

    user_states[message.from_user.id] = {
        "action": "set_interval",
        "type": "counter",
        "content": text,
        "target_date": target_date,
    }
    await message.reply(
        f"✅ تم تحديد الهدف: {target_date}\nأرسل الآن التكرار (مثلاً: كل ساعة أو كل 5 دقائق)"
    )


@app.on_message(is_admin & filters.regex(r"(فيديو|صورة|نص) تلقائي"))
async def auto_send_cmd(client, message):
    m_type = message.matches[0].group(1)
    type_map = {"فيديو": "video", "صورة": "photo", "نص": "text"}
    user_states[message.from_user.id] = {
        "action": "wait_content",
        "type": type_map[m_type],
    }
    await message.reply(f"حسناً، أرسل {m_type} الآن.")


@app.on_message(is_admin)
async def handle_responses(client, message):
    uid = message.from_user.id
    if uid not in user_states:
        return
    state = user_states[uid]

    if state["action"] == "wait_content":
        state["content"] = (
            message.video.file_id
            if state["type"] == "video"
            else (message.photo.file_id if state["type"] == "photo" else message.text)
        )
        state["caption"] = message.caption
        state["action"] = "set_interval"
        await message.reply("تمام، أرسل الآن وقت التكرار (مثلاً: كل يوم)")
    elif state["action"] == "set_interval":
        interval = parse_interval(message.text)
        scheduler.add_job(
            send_scheduled_msg,
            "interval",
            args=[
                message.chat.id,
                state["type"],
                state["content"],
                state.get("caption"),
                state.get("target_date"),
            ],
            **interval,
        )
        await message.reply(f"🚀 تم تفعيل الجدولة بنجاح!")
        del user_states[uid]


# تشغيل البوت
if __name__ == "__main__":
    scheduler.start()
    app.run()
