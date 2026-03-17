Import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncioScheduler
import dateparser
import re
from datetime import datetime

# --- الإعدادات التي زودتني بها ---
API_ID = 34257542
API_HASH = "614a1b5c5b712ac6de5530d5c571c42a"
BOT_TOKEN = "8543191006:AAFGAWKQa23bt26qYJ86MkvrjYXz_5d2gAA"
ADMIN_ID = 1486879970  # الايدي الخاص بك للتحكم

app = Client("FaisalBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = AsyncioScheduler()
scheduler.start()

# مخزن مؤقت لحفظ الحالات
user_states = {}

# --- وظائف مساعدة ---

def get_countdown_markup(target_date):
    """تحسب الفرق الزمني وتنسق الأزرار بشكل ذكي"""
    now = datetime.now()
    diff = target_date - now
    if diff.total_seconds() <= 0: return None
    
    days = diff.days
    weeks = days // 7
    hours = int(diff.total_seconds() // 3600)
    
    if days < 1:
        minutes = int((diff.total_seconds() % 3600) // 60)
        seconds = int(diff.total_seconds() % 60)
        btns = [[InlineKeyboardButton(f"{hours} ساعة", callback_data="n"),
                 InlineKeyboardButton(f"{minutes} دقيقة", callback_data="n"),
                 InlineKeyboardButton(f"{seconds} ثانية", callback_data="n")]]
    else:
        btns = [[InlineKeyboardButton(f"{days} يوم", callback_data="n"),
                 InlineKeyboardButton(f"{weeks} أسبوع", callback_data="n")],
                [InlineKeyboardButton(f"{hours} ساعة", callback_data="n")]]
    return InlineKeyboardMarkup(btns)

async def send_scheduled_msg(chat_id, type, content, caption=None, target_date=None):
    """إرسال المحتوى المجدول"""
    try:
        if type == "text":
            await app.send_message(chat_id, content)
        elif type == "photo":
            await app.send_photo(chat_id, content, caption=caption)
        elif type == "video":
            await app.send_video(chat_id, content, caption=caption)
        elif type == "counter":
            markup = get_countdown_markup(target_date)
            # تحديث النص ليكون دائماً طازجاً وقت الإرسال
            await app.send_message(chat_id, f"**{content}**", reply_markup=markup)
    except Exception as e:
        print(f"Error in scheduled task: {e}")

def parse_interval(text):
    """تحويل كلمات مثل 'كل دقيقة' إلى ثواني للجدولة"""
    text = text.replace("١", "1").replace("٢", "2").replace("٣", "3").replace("٤", "4").replace("٥", "5")
    nums = re.findall(r'\d+', text)
    val = int(nums[0]) if nums else 1
    
    if "دقيق" in text: return {"minutes": val}
    if "ساع" in text: return {"hours": val}
    if "يوم" in text: return {"days": val}
    if "أسبوع" in text or "اسبوع" in text: return {"weeks": val}
    return {"days": 1} # افتراضي يومي

# --- معالجة الأوامر (محمي بالايدي حقك) ---

# فلاتر خاصة للتأكد أنك أنت من يرسل الأمر
is_admin = filters.user(ADMIN_ID)

@app.on_message(is_admin & filters.regex(r"عداد \((.*)\) \((.*)\)"))
async def counter_cmd(client, message):
    text, time_str = message.matches[0].group(1), message.matches[0].group(2)
    target_date = dateparser.parse(time_str, settings={'PREFER_DATES_FROM': 'future'})
    
    if not target_date:
        return await message.reply("❌ لم أفهم الوقت، جرب: ( شهر ) أو ( 10 أيام )")

    user_states[message.from_user.id] = {
        "action": "set_interval", "type": "counter", 
        "content": text, "target_date": target_date
    }
    await message.reply(f"✅ تم حساب العداد لـ: {text}\n**كل متى تبيني أرسله؟** (دقيقة، ساعة، يوم..)")

@app.on_message(is_admin & filters.regex(r"(فيديو|صورة|نص) تلقائي"))
async def auto_send_cmd(client, message):
    m_type = message.matches[0].group(1)
    type_map = {"فيديو": "video", "صورة": "photo", "نص": "text"}
    user_states[message.from_user.id] = {"action": "wait_content", "type": type_map[m_type]}
    await message.reply(f"حسناً، أرسل {m_type} الآن.")

@app.on_message(is_admin)
async def handle_responses(client, message):
    uid = message.from_user.id
    if uid not in user_states: return

    state = user_states[uid]

    if state["action"] == "wait_content":
        if state["type"] == "photo" and message.photo:
            state["content"] = message.photo.file_id
            state["caption"] = message.caption
        elif state["type"] == "video" and message.video:
            state["content"] = message.video.file_id
            state["caption"] = message.caption
        elif state["type"] == "text" and message.text:
            state["content"] = message.text
        else: return

        state["action"] = "set_interval"
        await message.reply("وصل المحتوى ✅. **متى أو كل متى تبي الجدولة؟**")

    elif state["action"] == "set_interval":
        interval_str = message.text
        
        if "كل" in interval_str:
            params = parse_interval(interval_str)
            scheduler.add_job(send_scheduled_msg, "interval", **params, 
                              args=[message.chat.id, state["type"], state["content"], 
                                    state.get("caption"), state.get("target_date")])
            await message.reply(f"🚀 تمت الجدولة التلقائية: {interval_str}")
        else:
            run_time = dateparser.parse(interval_str, settings={'PREFER_DATES_FROM': 'future'})
            if run_time:
                scheduler.add_job(send_scheduled_msg, "date", run_date=run_time, 
                                  args=[message.chat.id, state["type"], state["content"], 
                                        state.get("caption"), state.get("target_date")])
                await message.reply(f"📌 تم ضبط الموعد لمرة واحدة: {run_time.strftime('%Y-%m-%d %H:%M')}")
            else:
                return await message.reply("ما فهمت الوقت، أعد المحاولة.")
        
        del user_states[uid]

print("--- البوت شغال وتحت أمرك يا فيصل ---")
app.run()
