import re
from datetime import datetime, timedelta
import dateparser

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# -------- إعدادات -------- #
API_ID = 34257542
API_HASH = "614a1b5c5b712ac6de5530d5c571c42a"
BOT_TOKEN = "8543191006:AAFGAWKQa23bt26qYJ86MkvrjYXz_5d2gAA"
ADMIN_ID = 1486879970

app = Client("smart_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = AsyncIOScheduler()

user_states = {}
tasks = {}
task_counter = 0


# -------- تحليل الوقت الذكي 🔥 -------- #
def parse_time(text):
    text = text.strip()

    # أرقام + وحدات
    m = re.search(r"بعد\s*(\d+)\s*(ثانية|ثواني|دقيقة|دقائق|ساعة|ساعات|يوم|ايام|أيام|شهر|شهور|سنة|سنوات)", text)
    if m:
        num = int(m.group(1))
        unit = m.group(2)

        if "ثان" in unit:
            return datetime.now() + timedelta(seconds=num)
        if "دقيق" in unit:
            return datetime.now() + timedelta(minutes=num)
        if "ساع" in unit:
            return datetime.now() + timedelta(hours=num)
        if "يوم" in unit:
            return datetime.now() + timedelta(days=num)
        if "شهر" in unit:
            return datetime.now() + timedelta(days=30 * num)
        if "سنة" in unit:
            return datetime.now() + timedelta(days=365 * num)

    # بدون رقم
    if "بكرا" in text or "غدا" in text or "غداً" in text:
        return datetime.now() + timedelta(days=1)

    if "شهر" in text:
        return datetime.now() + timedelta(days=30)

    if "سنة" in text:
        return datetime.now() + timedelta(days=365)

    if "يوم" in text:
        return datetime.now() + timedelta(days=1)

    if "ساعة" in text:
        return datetime.now() + timedelta(hours=1)

    # fallback
    return dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})


# -------- التكرار -------- #
def parse_interval(text):
    nums = re.findall(r"\d+", text)
    val = int(nums[0]) if nums else 1

    if "ثان" in text:
        return {"seconds": val}
    if "دقيق" in text:
        return {"minutes": val}
    if "ساع" in text:
        return {"hours": val}
    if "يوم" in text:
        return {"days": val}

    return {"days": 1}


# -------- العداد -------- #
def countdown_markup(target):
    diff = target - datetime.now()
    if diff.total_seconds() <= 0:
        return None

    days = diff.days
    hours = int(diff.total_seconds() // 3600)
    minutes = int((diff.total_seconds() % 3600) // 60)

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{days} يوم", "n"),
         InlineKeyboardButton(f"{hours} ساعة", "n"),
         InlineKeyboardButton(f"{minutes} دقيقة", "n")]
    ])


async def send_job(client, chat_id, task_id):
    task = tasks.get(task_id)
    if not task or not task["active"]:
        return

    try:
        if task["type"] == "text":
            await client.send_message(chat_id, task["content"])

        elif task["type"] == "photo":
            await client.send_photo(chat_id, task["content"], caption=task.get("caption"))

        elif task["type"] == "video":
            await client.send_video(chat_id, task["content"], caption=task.get("caption"))

        elif task["type"] == "counter":
            markup = countdown_markup(task["target"])
            await client.send_message(chat_id, f"⏳ {task['content']}", reply_markup=markup)

    except Exception as e:
        print(e)


# -------- الأوامر -------- #

is_admin = filters.user(ADMIN_ID)


@app.on_message(is_admin & filters.regex(r"(نص|صورة|فيديو) تلقائي"))
async def auto_start(client, message):
    mapping = {"نص": "text", "صورة": "photo", "فيديو": "video"}

    user_states[message.from_user.id] = {
        "action": "content",
        "type": mapping[message.matches[0].group(1)]
    }

    await message.reply("أرسل المحتوى")


@app.on_message(is_admin & filters.regex(r"عداد \((.*)\) \((.*)\)"))
async def counter_start(client, message):
    text, time_str = message.matches[0].group(1), message.matches[0].group(2)

    target = parse_time(time_str)
if not target:
        return await message.reply("❌ وقت غير مفهوم")

    user_states[message.from_user.id] = {
        "action": "interval",
        "type": "counter",
        "content": text,
        "target": target
    }

    await message.reply("حدد التكرار (مثال: كل ساعة)")


@app.on_message(is_admin)
async def flow(client, message):
    global task_counter

    uid = message.from_user.id
    if uid not in user_states:
        return

    state = user_states[uid]

    if state["action"] == "content":
        if state["type"] == "photo":
            state["content"] = message.photo.file_id
        elif state["type"] == "video":
            state["content"] = message.video.file_id
        else:
            state["content"] = message.text

        state["caption"] = message.caption
        state["action"] = "interval"

        return await message.reply("حدد التكرار")

    elif state["action"] == "interval":
        interval = parse_interval(message.text)

        task_counter += 1
        task_id = task_counter

        tasks[task_id] = {
            "type": state["type"],
            "content": state["content"],
            "caption": state.get("caption"),
            "target": state.get("target"),
            "interval": interval,
            "active": True
        }

        scheduler.add_job(
            send_job,
            "interval",
            args=[client, message.chat.id, task_id],
            id=str(task_id),
            **interval
        )

        await message.reply(f"✅ تم إنشاء المهمة #{task_id}")
        del user_states[uid]


# -------- إدارة -------- #

@app.on_message(is_admin & filters.command("tasks"))
async def list_tasks(client, message):
    if not tasks:
        return await message.reply("لا توجد مهام")

    text = "📋 المهام:\n\n"
    for tid, t in tasks.items():
        status = "✅" if t["active"] else "⛔"
        text += f"{tid} - {t['type']} ({status})\n"

    await message.reply(text)


@app.on_message(is_admin & filters.command("delete"))
async def delete_task(client, message):
    try:
        tid = int(message.command[1])
    except:
        return await message.reply("اكتب ID صحيح")

    if tid not in tasks:
        return await message.reply("غير موجود")

    scheduler.remove_job(str(tid))
    del tasks[tid]

    await message.reply("تم الحذف 🗑️")


@app.on_message(is_admin & filters.command("stop"))
async def stop_task(client, message):
    tid = int(message.command[1])
    if tid in tasks:
        tasks[tid]["active"] = False
        await message.reply("تم الإيقاف ⛔")


@app.on_message(is_admin & filters.command("start"))
async def start_task(client, message):
    tid = int(message.command[1])
    if tid in tasks:
        tasks[tid]["active"] = True
        await message.reply("تم التشغيل ✅")


@app.on_message(is_admin & filters.command("clear"))
async def clear_tasks(client, message):
    scheduler.remove_all_jobs()
    tasks.clear()
    await message.reply("تم حذف الكل 🧹")


# -------- تشغيل -------- #

if name == "__main__":
    scheduler.start()
    print("Bot running 🔥")
    app.run()
