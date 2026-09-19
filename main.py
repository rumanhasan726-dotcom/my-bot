from flask import Flask
import os
import re
import telebot
from telebot import types
import threading
from pymongo import MongoClient
import pyotp
from datetime import datetime, timezone, timedelta
from bson.objectid import ObjectId

# ---------------- CONFIGURATION ----------------
TOKEN = "8965009856:AAE3bj58hOGw083tDuKFVy-d1DPiO_gs0ew"
bot = telebot.TeleBot(TOKEN)

# MongoDB Connection & Collections Setup
MONGO_URI = "mongodb+srv://js3262481_db_user:ruman%4045@cluster0.p7mypr2.mongodb.net/?appName=Cluster0"
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["telegram_bot_db"]
    users_collection = db["users"]
    settings_collection = db["settings"]
    tasks_collection = db["tasks"]
    withdraws_collection = db["withdraws"]
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"MongoDB connection error: {e}")

# বাংলাদেশ সময় জোন (UTC+6)
BD_TZ = timezone(timedelta(hours=6))

# উইকলি রিসেট চেক করার ফাংশন (প্রতিশুক্রবার রাত ৯টা)
def check_and_reset_leaderboard():
    try:
        now_bd = datetime.now(BD_TZ)
        current_weekday = now_bd.weekday()
        current_hour = now_bd.hour

        reset_doc = settings_collection.find_one({"setting_type": "leaderboard_cycle"})
        
        if current_weekday == 4 and current_hour >= 21:
            cycle_key = f"fri_9pm_{now_bd.strftime('%Y-%m-%d')}"
        else:
            days_to_last_fri = (current_weekday - 4) % 7
            if days_to_last_fri == 0 and current_hour < 21:
                days_to_last_fri = 7
            last_fri = now_bd - timedelta(days=days_to_last_fri)
            cycle_key = f"fri_9pm_{last_fri.strftime('%Y-%m-%d')}"

        if not reset_doc or reset_doc.get("active_cycle") != cycle_key:
            users_collection.update_many({}, {"$set": {"completed_tasks": 0}})
            settings_collection.update_one(
                {"setting_type": "leaderboard_cycle"},
                {"$set": {"active_cycle": cycle_key}},
                upsert=True
            )
            print(f"Leaderboard reset successfully for cycle: {cycle_key}")
    except Exception as e:
        print(f"Leaderboard reset error: {e}")

# ডাটাবেজ থেকে দৈনিক পাসওয়ার্ড ম্যানেজ করার ফাংশন
def get_current_password():
    s = settings_collection.find_one({"setting_type": "app_password"})
    if not s:
        default_pass = "Jahanur@08"
        settings_collection.update_one({"setting_type": "app_password"}, {"$set": {"password": default_pass}}, upsert=True)
        return default_pass
    return s.get("password", "Jahanur@08")

def update_current_password(new_pass):
    settings_collection.update_one({"setting_type": "app_password"}, {"$set": {"password": new_pass}}, upsert=True)

# টাস্ক প্রাইস ম্যানেজ করার ফাংশন
def get_cookie_task_price():
    s = settings_collection.find_one({"setting_type": "cookie_price"})
    if not s:
        default_price = 4.80
        settings_collection.update_one({"setting_type": "cookie_price"}, {"$set": {"price": default_price}}, upsert=True)
        return default_price
    return float(s.get("price", 4.80))

def update_cookie_task_price(new_price):
    settings_collection.update_one({"setting_type": "cookie_price"}, {"$set": {"price": float(new_price)}}, upsert=True)

def get_2fa_task_price():
    s = settings_collection.find_one({"setting_type": "2fa_price"})
    if not s:
        default_price = 5.40
        settings_collection.update_one({"setting_type": "2fa_price"}, {"$set": {"price": default_price}}, upsert=True)
        return default_price
    return float(s.get("price", 5.40))

def update_2fa_task_price(new_price):
    settings_collection.update_one({"setting_type": "2fa_price"}, {"$set": {"price": float(new_price)}}, upsert=True)

def get_2fa_status():
    s = settings_collection.find_one({"setting_type": "2fa_status"})
    if not s:
        return True 
    return s.get("is_active", True)

def set_2fa_status(status: bool):
    settings_collection.update_one({"setting_type": "2fa_status"}, {"$set": {"is_active": status}}, upsert=True)

def get_prizes():
    s = settings_collection.find_one({"setting_type": "prizes"})
    if not s:
        default_prizes = {"1": 50.0, "2": 30.0, "3": 20.0}
        settings_collection.update_one({"setting_type": "prizes"}, {"$set": default_prizes}, upsert=True)
        return default_prizes
    return {"1": float(s.get("1", 50.0)), "2": float(s.get("2", 30.0)), "3": float(s.get("3", 20.0))}

def update_prize(position, amount):
    settings_collection.update_one(
        {"setting_type": "prizes"},
        {"$set": {str(position): float(amount)}},
        upsert=True
    )

def get_user_data(user_id, user_obj=None):
    try:
        query_filter = {"user_id": int(user_id)}
        user_doc = users_collection.find_one(query_filter)
        
        first_name = user_obj.first_name if (user_obj and user_obj.first_name) else "User"
        username = user_obj.username if (user_obj and user_obj.username) else "None"
        
        if not user_doc:
            new_user = {
                "user_id": int(user_id),
                "name": first_name,
                "username": username,
                "balance": 0.0,
                "ref_income": 0.0,
                "ref_count": 0,
                "referred_by": None,
                "state": None,
                "completed_tasks": 0,
                "pending_tasks": 0,
                "temp_uid": "",
                "temp_cookies": "",
                "temp_2fa_key": "",
                "task_type": "",
                "task_password": "",
                "withdraw_method": "",
                "operator": "",
                "withdraw_phone": "",
            }
            users_collection.insert_one(new_user)
            return new_user
        else:
            update_fields = {}
            if user_doc.get("name") != first_name:
                update_fields["name"] = first_name
                user_doc["name"] = first_name
            if user_doc.get("username") != username:
                update_fields["username"] = username
                user_doc["username"] = username
            if update_fields:
                users_collection.update_one(query_filter, {"$set": update_fields})
        return user_doc
    except Exception as e:
        print(f"Error getting user data: {e}")
        return {
            "user_id": int(user_id),
            "name": "User",
            "username": "None",
            "balance": 0.0,
            "ref_income": 0.0,
            "ref_count": 0,
            "referred_by": None,
            "state": None,
            "completed_tasks": 0,
            "pending_tasks": 0,
            "temp_uid": "",
            "temp_cookies": "",
            "temp_2fa_key": "",
            "task_type": "",
            "task_password": "",
            "withdraw_method": "",
            "operator": "",
            "withdraw_phone": "",
        }

def update_user_data(user_id, update_dict):
    try:
        users_collection.update_one(
            {"user_id": int(user_id)},
            {"$set": update_dict},
            upsert=True
        )
    except Exception as e:
        print(f"Error updating MongoDB: {e}")

submitted_uids = set()

ADMIN_ID = 8449043852  
ADMIN_USERNAME = "@Ruman_Hasan_45" 

FORCE_CHANNEL_USERNAME = "@R4_Work_Sapait"
FORCE_CHANNEL_LINK = "https://t.me/R4_Work_Sapait"

MIN_WITHDRAW = 100.0
MIN_RECHARGE = 20.0

def parse_bangla_number(text):
    bangla_to_eng = {'০':'0', '১':'1', '২':'2', '৩':'3', '৪':'4', '৫':'5', '৬':'6', '৭':'7', '৮':'8', '৯':'9'}
    for b, e in bangla_to_eng.items():
        text = text.replace(b, e)
    cleaned = re.sub(r'[^0-9.]', '', text)
    try:
        return float(cleaned)
    except ValueError:
        return None

# ---------------- FLASK SERVER ----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def check_user_subscription(user_id):
    try:
        member = bot.get_chat_member(FORCE_CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        print(f"Subscription check error: {e}")
    return False

# ---------------- START COMMAND ----------------
@bot.message_handler(commands=["start"])
def send_welcome(message):
    check_and_reset_leaderboard()
    user_id = message.from_user.id
    args = message.text.split()

    get_user_data(user_id, message.from_user)
    
    if len(args) > 1:
        try:
            ref_id = int(args[1])
            ref_doc = users_collection.find_one({"user_id": ref_id})
            user_doc = users_collection.find_one({"user_id": user_id})
            if ref_id != user_id and ref_doc and not user_doc.get("referred_by"):
                users_collection.update_one({"user_id": user_id}, {"$set": {"referred_by": ref_id}})
                users_collection.update_one({"user_id": ref_id}, {"$inc": {"ref_count": 1}})
        except ValueError:
            pass

    if not check_user_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ Verify (চেক করুন)", callback_data="verify_sub"))
        
        start_text = (
            "🤖 *স্বাগতম! এই বটে ছোট ছোট টাস্ক কমপ্লিট করেই আয় করা যায় - সহজ, দ্রুত, রিয়েল ইনকাম 💵*\n\n"
            "👉 *শুরু করতে নিচের চ্যানেলে জয়েন করুন, তারপর Verify চাপুন। 🤩*"
        )
        bot.send_message(message.chat.id, start_text, parse_mode="Markdown", reply_markup=markup)
        return

    main_menu(message.chat.id, "✨ *প্রধান মেনু:*")

def main_menu(chat_id, text_msg):
    update_user_data(chat_id, {"state": None})
    user_id = chat_id

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_balance = types.KeyboardButton("💰 ব্যালেন্স")
    btn_work = types.KeyboardButton("💼 কাজ")
    btn_withdraw = types.KeyboardButton("📤 উত্তোলন")
    btn_support = types.KeyboardButton("📌 সাপোর্ট")
    btn_refer = types.KeyboardButton("🎁 Refer & Earn")
    btn_leaderboard = types.KeyboardButton("🏆 Leader Board")
    
    markup.add(btn_balance, btn_work, btn_withdraw, btn_support, btn_refer, btn_leaderboard)
    
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("🛠️ অ্যাডমিন প্যানেল"))

    bot.send_message(chat_id, text_msg, parse_mode="Markdown", reply_markup=markup)

# ---------------- MESSAGE & ADMIN HANDLER ----------------
@bot.message_handler(func=lambda message: True, content_types=["text", "audio", "voice"])
def handle_message(message):
    check_and_reset_leaderboard()
    chat_id = message.chat.id
    user_id = message.from_user.id

    user_data = get_user_data(user_id, message.from_user)

    if not check_user_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ Verify (চেক করুন)", callback_data="verify_sub"))
        bot.send_message(
            chat_id,
            "⚠️ *বট ব্যবহার করতে হলে অবশ্যই নিচের চ্যানেলে জয়েন করতে হবে!*\nদয়া করে আগে জয়েন করুন.",
            parse_mode="Markdown",
            reply_markup=markup,
        )
        return

    if user_id == ADMIN_ID and message.content_type == "text":
        text = message.text.strip()

        if text.startswith("/setprize"):
            parts = text.split()
            if len(parts) == 3:
                pos = parts[1]
                if pos in ["1", "2", "3"]:
                    try:
                        amt = float(parts[2])
                        update_prize(pos, amt)
                        bot.send_message(chat_id, f"✅ সফলভাবে লিডারবোর্ডের {pos}ম পুরস্কারের পরিমাণ `{amt:.2f} BDT` সেট করা হয়েছে।", parse_mode="Markdown")
                    except ValueError:
                        bot.send_message(chat_id, "❌ সঠিক পরিমাণ সংখ্যা দিন। যেমন: `/setprize 1 60`", parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, "❌ পজিশন শুধু 1, 2 অথবা 3 হতে পারবে। যেমন: `/setprize 1 60`", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "❌ সঠিক ফরম্যাটে লিখুন। উদাহরণ: `/setprize 1 60`", parse_mode="Markdown")
            return

        if text.startswith("/setcookieprice"):
            parts = text.split()
            if len(parts) > 1:
                try:
                    new_p = float(parts[1])
                    update_cookie_task_price(new_p)
                    bot.send_message(chat_id, f"✅ কুকিজ টাস্কের নতুন মূল্য সফলভাবে সেট করা হয়েছে: `{new_p:.2f} BDT`", parse_mode="Markdown")
                except ValueError:
                    bot.send_message(chat_id, "❌ সঠিক সংখ্যা দিন। যেমন: `/setcookieprice 5.00`", parse_mode="Markdown")
            else:
                current_p = get_cookie_task_price()
                bot.send_message(chat_id, f"বর্তমান কুকিজ টাস্ক মূল্য: `{current_p:.2f} BDT`\nপরিবর্তন করতে এভাবে লিখুন: `/setcookieprice 5.00`", parse_mode="Markdown")
            return

        if text.startswith("/set2faprice"):
            parts = text.split()
            if len(parts) > 1:
                try:
                    new_p = float(parts[1])
                    update_2fa_task_price(new_p)
                    bot.send_message(chat_id, f"✅ 2FA টাস্কের নতুন মূল্য সফলভাবে সেট করা হয়েছে: `{new_p:.2f} BDT`", parse_mode="Markdown")
                except ValueError:
                    bot.send_message(chat_id, "❌ সঠিক সংখ্যা দিন। যেমন: `/set2faprice 6.00`", parse_mode="Markdown")
            else:
                current_p = get_2fa_task_price()
                bot.send_message(chat_id, f"বর্তমান 2FA টাস্ক মূল্য: `{current_p:.2f} BDT`\nপরিবর্তন করতে এভাবে লিখুন: `/set2faprice 6.00`", parse_mode="Markdown")
            return

        if text == "🛠️ অ্যাডমিন প্যানেল":
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
            markup.add(
                types.KeyboardButton("🔑 দৈনিক পাসওয়ার্ড সেট"),
                types.KeyboardButton("📤 উইথড্র পেন্ডিং"),
                types.KeyboardButton("🔙 মূল মেনু")
            )
            bot.send_message(chat_id, "অ্যাডমিন প্যানেলে স্বাগতম:", reply_markup=markup)
            return

        if text == "🔙 মূল মেনু":
            main_menu(chat_id, "🏢 *প্রধান মেনুতে ফিরিয়ে আনা হয়েছে।*")
            return

        if text == "📤 উইথড্র পেন্ডিং":
            pendings = list(withdraws_collection.find({"status": "pending"}))
            if not pendings:
                bot.send_message(chat_id, "📭 কোনো পেন্ডিং উইথড্র রিকোয়েস্ট নেই।", parse_mode="Markdown")
                return
            for p in pendings:
                p_text = (
                    f"📤 *পেন্ডিং উইথড্র রিকোয়েস্ট*\n\n"
                    f"👤 ইউজার ID: `{p['user_id']}`\n"
                    f"💰 পরিমাণ: `{p['amount']} BDT`\n"
                    f"📞 বিবরণ: `{p['details']}`\n"
                    f"🕒 সময়: `{p['created_at']}`"
                )
                m = types.InlineKeyboardMarkup()
                m.add(types.InlineKeyboardButton("✅ পেমেন্ট সম্পন্ন করুন", callback_data=f"paid_{p['user_id']}_{p['amount']}_{p['details'].split(' - ')[0]}"))
                bot.send_message(chat_id, p_text, parse_mode="Markdown", reply_markup=m)
            return

        if text == "🔑 দৈনিক পাসওয়ার্ড সেট":
            update_user_data(user_id, {"state": "setting_password"})
            bot.send_message(chat_id, f"বর্তমান পাসওয়ার্ড: `{get_current_password()}`\n\nআজকের নতুন পাসওয়ার্ডটি লিখে পাঠান, যা ইউজাররা কাজ জমা দেওয়ার সময় দেখতে পাবে:", parse_mode="Markdown")
            return

        if text == "/2faon":
            set_2fa_status(True)
            bot.send_message(chat_id, "✅ *Facebook 2FA কাজটি এখন চালু করা হয়েছে!*", parse_mode="Markdown")
            return

        if text == "/2faoff":
            set_2fa_status(False)
            bot.send_message(chat_id, "🚫 *Facebook 2FA কাজটি এখন বন্ধ করা হয়েছে!*", parse_mode="Markdown")
            return

        if user_data.get("state") == "setting_password":
            update_user_data(user_id, {"state": None})
            update_current_password(text)
            bot.send_message(chat_id, f"✅ আজকের নতুন পাসওয়ার্ড সফলভাবে আপডেট করা হয়েছে: `{text}`", parse_mode="Markdown")
            return

    if message.content_type != "text":
        return

    text = message.text.strip()
    user_state = user_data.get("state")

    if text == "❌ বাতিল" or text == "❌ ফিরে যান":
        update_user_data(user_id, {"state": None})
        main_menu(chat_id, "❌ *মেনুতে ফিরে আসা হয়েছে!*")
        return

    if text == "🏆 Leader Board":
        prizes = get_prizes()
        top_users = list(users_collection.find().sort("completed_tasks", -1).limit(10))
        
        lb_text = "🏆 *《 WEEKLY LEADER BOARD 》* 🏆\n📅 *(প্রতিশুক্রবার রাত ৯টা পর্যন্ত কার্যকর)*\n\n"
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        
        for idx, u in enumerate(top_users, 1):
            rank_icon = medals.get(idx, f"📌 {idx}.")
            uname = u.get("name", "User")
            tasks_done = u.get("completed_tasks", 0)
            lb_text += f"{rank_icon} *{uname}* ➔ `{tasks_done} Tasks`\n"
            
        lb_text += f"\n🎁 *এই সপ্তাহের পুরস্কারের তালিকা:*\n"
        lb_text += f"🥇 ১ম স্থান: `{prizes['1']} BDT`\n"
        lb_text += f"🥈 ২য় স্থান: `{prizes['2']} BDT`\n"
        lb_text += f"🥉 ৩য় স্থান: `{prizes['3']} BDT`\n\n"
        lb_text += f"💡 *লিডারবোর্ডে আপনার পজিশন জানতে নিচের বাটনে ক্লিক করুন!*"

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔍 আমার পজিশন চেক করুন", callback_data="check_my_rank"))
        bot.send_message(chat_id, lb_text, parse_mode="Markdown", reply_markup=markup)
        return

    # --- COOKIES TASK FLOW ---
    if user_state == "waiting_for_uid_cookie":
        uid = text
        if not uid.isdigit() or len(uid) < 5 or len(uid) > 20:
            bot.send_message(chat_id, "❌ *সঠিক ফেসবুক UID দিন অথবা '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        if uid in submitted_uids:
            bot.send_message(chat_id, "❌ *এই ফেসবুক UID টি ইতিমধ্যে জমা দেওয়া হয়েছে! অন্য UID দিন।*", parse_mode="Markdown")
        else:
            update_user_data(user_id, {"temp_uid": uid, "state": "waiting_for_cookies"})
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            bot.send_message(chat_id, "🛡️ *আপনার অ্যাকাউন্টের কুকিজ পেস্ট করুন 📍*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_cookies":
        update_user_data(user_id, {"temp_cookies": text, "state": "waiting_for_finish_cookie_button"})
        finish_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        finish_markup.add(types.KeyboardButton("অ্যাকাউন্ট খোলা শেষ"), types.KeyboardButton("❌ বাতিল"))
        bot.send_message(chat_id, "✅ *অ্যাকাউন্ট খোলা শেষ হলে নিচের বাটনে চাপ দিন:*", parse_mode="Markdown", reply_markup=finish_markup)
        return

    elif user_state == "waiting_for_finish_cookie_button":
        if text == "অ্যাকাউন্ট খোলা শেষ":
            current_data = get_user_data(user_id, message.from_user)
            uid = current_data.get("temp_uid")
            cookies = current_data.get("temp_cookies")
            uname = message.from_user.username or "None"
            current_cookie_price = get_cookie_task_price()

            submitted_uids.add(uid)
            
            task_doc = {
                "user_id": user_id,
                "username": uname,
                "task_type": "cookie",
                "uid": uid,
                "cookies": cookies,
                "2fa_key": "",
                "price": current_cookie_price,
                "status": "pending",
                "created_at": datetime.now(BD_TZ)
            }
            task_insert_res = tasks_collection.insert_one(task_doc)
            task_id = str(task_insert_res.inserted_id)

            update_user_data(user_id, {"pending_tasks": current_data.get("pending_tasks", 0) + 1, "state": None})

            admin_msg = (
                f"📥 *নতুন কুকিজ টাস্ক জমা পড়েছে!*\n\n"
                f"👤 ইউজার ID: `{user_id}`\n"
                f"🌐 ইউজারনেম: @{uname}\n"
                f"📌 UID: `{uid}`\n"
                f"💵 মূল্য: {current_cookie_price:.2f} BDT\n\n"
                f"🛡️ কুকিজ:\n`{cookies}`"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ সঠিক (Approve)", callback_data=f"approve_{task_id}"),
                types.InlineKeyboardButton("❌ ভুল (Reject)", callback_data=f"reject_{task_id}")
            )
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)
            
            bot.send_message(chat_id, "🎉 *আপনার কাজটি সফলভাবে জমা নেওয়া হয়েছে এবং গ্রহণ করা হয়েছে!*", parse_mode="Markdown")
            main_menu(chat_id, "✨ *প্রধান মেনু:*")
        return

    # --- 2FA TASK FLOW ---
    elif user_state == "waiting_for_uid_2fa":
        uid = text
        if not uid.isdigit() or len(uid) < 5 or len(uid) > 20:
            bot.send_message(chat_id, "❌ *সঠিক ফেসবুক UID দিন অথবা '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        if uid in submitted_uids:
            bot.send_message(chat_id, "❌ *এই ফেসবুক UID টি ইতিমধ্যে জমা দেওয়া হয়েছে! অন্য UID দিন।*", parse_mode="Markdown")
        else:
            update_user_data(user_id, {"temp_uid": uid, "state": "waiting_for_cookies_2fa"})
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            bot.send_message(chat_id, "🛡️ *আপনার অ্যাকাউন্টের কুকিজ পেস্ট করুন 📍*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_cookies_2fa":
        update_user_data(user_id, {"temp_cookies": text, "state": "waiting_for_2fa_key"})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        bot.send_message(chat_id, "🛡️ *এখন 2FA Key টি দিন: ⬇️*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_2fa_key":
        key_clean = text.replace(" ", "").upper()
        if not (re.match(r"^[A-Z2-7]+$", key_clean) and len(key_clean) in [16, 32]):
            bot.send_message(chat_id, "❌ *সঠিক 2FA Key দিন (অবশ্যই ১৬ বা ৩২ অক্ষরের এবং সব বড় হাতের হতে হবে)...*", parse_mode="Markdown")
            return

        try:
            totp = pyotp.TOTP(key_clean)
            otp_code = totp.now()
        except Exception:
            bot.send_message(chat_id, "❌ *অসঠিক 2FA Key! দয়া করে সঠিক Key দিন:*", parse_mode="Markdown")
            return

        update_user_data(user_id, {"temp_2fa_key": key_clean, "state": "waiting_for_finish_2fa_button"})

        markup_user = types.InlineKeyboardMarkup()
        markup_user.add(types.InlineKeyboardButton(f"📋 {otp_code}", callback_data=f"copy_code_{otp_code}"))

        finish_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        finish_markup.add(types.KeyboardButton("অ্যাকাউন্ট খোলা শেষ"), types.KeyboardButton("❌ বাতিল"))

        bot.send_message(chat_id, "🛡️ *নিচের বাটনে চাপ দিয়ে কোডটি কপি করুন এবং ফেসবুকে বসান:*", parse_mode="Markdown", reply_markup=markup_user)
        bot.send_message(chat_id, "✅ *ফেসবুকে কোড বসানো হয়ে গেলে নিচের 'অ্যাকাউন্ট খোলা শেষ' বাটনে চাপ দিন:*", parse_mode="Markdown", reply_markup=finish_markup)
        return

    elif user_state == "waiting_for_finish_2fa_button":
        if text == "অ্যাকাউন্ট খোলা শেষ":
            current_data = get_user_data(user_id, message.from_user)
            uid = current_data.get("temp_uid")
            cookies = current_data.get("temp_cookies")
            key_clean = current_data.get("temp_2fa_key")
            uname = message.from_user.username or "None"
            current_2fa_price = get_2fa_task_price()

            submitted_uids.add(uid)
            
            task_doc = {
                "user_id": user_id,
                "username": uname,
                "task_type": "2fa",
                "uid": uid,
                "cookies": cookies,
                "2fa_key": key_clean,
                "price": current_2fa_price,
                "status": "pending",
                "created_at": datetime.now(BD_TZ)
            }
            task_insert_res = tasks_collection.insert_one(task_doc)
            task_id = str(task_insert_res.inserted_id)

            update_user_data(user_id, {"pending_tasks": current_data.get("pending_tasks", 0) + 1, "state": None})

            admin_msg = (
                f"📥 *নতুন 2FA টাস্ক জমা পড়েছে!*\n\n"
                f"👤 ইউজার ID: `{user_id}`\n"
                f"🌐 ইউজারনেম: @{uname}\n"
                f"📌 UID: `{uid}`\n"
                f"🔑 2FA Key: `{key_clean}`\n"
                f"💵 মূল্য: {current_2fa_price:.2f} BDT\n\n"
                f"🛡️ কুকিজ:\n`{cookies}`"
            )
            
            markup_admin = types.InlineKeyboardMarkup()
            markup_admin.add(
                types.InlineKeyboardButton("✅ সঠিক (Approve)", callback_data=f"approve_{task_id}"),
                types.InlineKeyboardButton("❌ ভুল (Reject)", callback_data=f"reject_{task_id}")
            )
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup_admin)
            
            bot.send_message(chat_id, "🎉 *আপনার কাজটি সফলভাবে জমা নেওয়া হয়েছে এবং গ্রহণ করা হয়েছে!*", parse_mode="Markdown")
            main_menu(chat_id, "✨ *প্রধান মেনু:*")
        return

    # --- RECHARGE / WITHDRAW STATES ---
    elif user_state == "waiting_for_recharge_number":
        phone = text.strip()
        if not re.match(r"^01[3-9]\d{8}$", phone):
            bot.send_message(chat_id, "❌ *সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন (যেমন: 01934546320)।*", parse_mode="Markdown")
            return

        update_user_data(user_id, {"withdraw_phone": phone, "state": "waiting_for_recharge_amount"})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        
        operator = user_data.get("operator", "")
        bot.send_message(chat_id, f"💰 *কত টাকা রিচার্জ ({operator}) করতে চান? সংখ্যায় লিখুন:*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_recharge_amount":
        amount = parse_bangla_number(text)
        if amount is None:
            bot.send_message(chat_id, "❌ *দয়া করে সঠিক সংখ্যায় পরিমাণ লিখুন।*", parse_mode="Markdown")
            return

        current_data = get_user_data(user_id, message.from_user)
        balance = current_data["balance"]
        operator = current_data.get("operator", "")
        phone = current_data.get("withdraw_phone", "")

        if amount < MIN_RECHARGE:
            bot.send_message(chat_id, f"❌ *সর্বনিম্ন রিচার্জ পরিমাণ {MIN_RECHARGE} BDT।*", parse_mode="Markdown")
            return

        if amount > balance:
            bot.send_message(chat_id, f"❌ *পর্যাপ্ত ব্যালেন্স নেই! বর্তমান ব্যালেন্স: {balance:.2f} BDT*", parse_mode="Markdown")
            return

        new_balance = balance - amount
        update_user_data(user_id, {"state": None, "balance": new_balance})
        uname = message.from_user.username or "None"

        withdraws_collection.insert_one({
            "user_id": user_id,
            "amount": amount,
            "details": f"মোবাইল রিচার্জ ({operator}) - {phone}",
            "status": "pending",
            "created_at": datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
        })

        admin_msg = f"📱 *নতুন মোবাইল রিচার্জ রিকোয়েস্ট!*\n\n👤 ইউজার ID: `{user_id}`\n🌐 ইউজারনেম: @{uname}\n🌐 অপারেটর: *{operator}*\n📞 নম্বর: `{phone}`\n💰 পরিমাণ: {amount} BDT"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ সফল হয়েছে (পাঠানো হয়েছে)", callback_data=f"rechargepaid_{user_id}_{amount}"))

        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)

        user_success_msg = (
            f"✅ *আপনার রিকোয়েস্ট সফলভাবে সাবমিট হয়েছে!*\n\n"
            f"🌐 *অপারেটর:* মোবাইল রিচার্জ ({operator})\n"
            f"📱 *নম্বর:* {phone}\n"
            f"💵 *পরিমাণ:* {amount:.2f} BDT\n\n"
            f"💳 অবশিষ্ট ব্যালেন্স: *{new_balance:.2f} BDT*"
        )
        bot.send_message(chat_id, user_success_msg, parse_mode="Markdown")
        main_menu(chat_id, "✨ *প্রধান মেনু:*")
        return

    elif user_state == "waiting_for_withdraw_number":
        phone = text.strip()
        if not re.match(r"^01[3-9]\d{8}$", phone):
            bot.send_message(chat_id, "❌ *সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন।*", parse_mode="Markdown")
            return

        update_user_data(user_id, {"withdraw_phone": phone, "state": "waiting_for_withdraw_amount"})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        
        bot.send_message(chat_id, f"💰 *কত টাকা উত্তোলন করতে চান? সংখ্যায় লিখুন:*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_withdraw_amount":
        amount = parse_bangla_number(text)
        if amount is None:
            bot.send_message(chat_id, "❌ *দয়া করে সঠিক সংখ্যায় পরিমাণ লিখুন।*", parse_mode="Markdown")
            return

        current_data = get_user_data(user_id, message.from_user)
        balance = current_data["balance"]
        method = current_data.get("withdraw_method", "বিকাশ")
        phone = current_data.get("withdraw_phone", "")

        if amount < MIN_WITHDRAW:
            bot.send_message(chat_id, f"❌ *সর্বনিম্ন পরিমাণ {MIN_WITHDRAW} BDT।*", parse_mode="Markdown")
            return

        if amount > balance:
            bot.send_message(chat_id, f"❌ *পর্যাপ্ত ব্যালেন্স নেই! বর্তমান ব্যালেন্স: {balance:.2f} BDT*", parse_mode="Markdown")
            return

        new_balance = balance - amount
        update_user_data(user_id, {"state": None, "balance": new_balance})
        uname = message.from_user.username or "None"

        withdraws_collection.insert_one({
            "user_id": user_id,
            "amount": amount,
            "details": f"{method} - {phone}",
            "status": "pending",
            "created_at": datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
        })

        admin_msg = f"📤 *নতুন উইথড্র রিকোয়েস্ট!*\n\n👤 ইউজার ID: `{user_id}`\n🌐 ইউজারনেম: @{uname}\n💼 মাধ্যম: {method}\n📞 নম্বর: `{phone}`\n💰 পরিমাণ: {amount} BDT"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ সফল হয়েছে (পাঠানো হয়েছে)", callback_data=f"paid_{user_id}_{amount}_{method}"))

        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)

        user_success_msg = (
            f"✅ *আপনার রিকোয়েস্ট সফলভাবে সাবমিট হয়েছে!*\n\n"
            f"💼 *মাধ্যম:* {method}\n"
            f"📱 *নম্বর:* {phone}\n"
            f"💵 *পরিমাণ:* {amount:.2f} BDT\n\n"
            f"💳 অবশিষ্ট ব্যালেন্স: *{new_balance:.2f} BDT*"
        )
        bot.send_message(chat_id, user_success_msg, parse_mode="Markdown")
        main_menu(chat_id, "✨ *প্রধান মেনু:*")
        return

    # --- MENU BUTTONS & TASK KEYBOARD ---
    if text == "💰 ব্যালেন্স":
        data = get_user_data(user_id, message.from_user)
        uname_display = f"@{message.from_user.username}" if message.from_user.username else "নেই"
        reply_text = (
            f"👤 *আপনার একাউন্ট বিবরণী:*\n\n"
            f"📌 নাম: {data.get('name', 'User')}\n"
            f"🆔 ইউজার আইডি: `{user_id}`\n"
            f"🌐 ইউজারনেম: {uname_display}\n\n"
            f"🟢 ব্যালেন্স: {data['balance']:.2f} BDT\n"
            f"👥 রেফারেল ইনকাম: {data.get('ref_income', 0.0):.2f} BDT\n\n"
            f"✅ সম্পন্ন কাজ: {data['completed_tasks']} টি\n"
            f"🔄 রিভিউতে আছে: {data['pending_tasks']} টি"
        )
        bot.send_message(chat_id, reply_text, parse_mode="Markdown")

    elif text == "💼 কাজ":
        c_price = get_cookie_task_price()
        t_price = get_2fa_task_price()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(
            types.KeyboardButton(f"👥 ফেসবুক কুকিজ কাজ ({c_price:.2f} BDT)"),
            types.KeyboardButton(f"🔐 ফেসবুক 2FA কাজ ({t_price:.2f} BDT)"),
            types.KeyboardButton("❌ ফিরে যান")
        )
        bot.send_message(chat_id, "✅ *যেকোনো একটি কাজ সিলেক্ট করুন*:", parse_mode="Markdown", reply_markup=markup)

    elif text.startswith("👥 ফেসবুক কুকিজ কাজ"):
        current_pass = get_current_password()
        update_user_data(user_id, {"state": "waiting_for_uid_cookie", "task_type": "cookie", "task_password": current_pass})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        task_msg = (
            f"🔵 *Facebook Account Creation Info:*\n\n"
            f"• Password : `{current_pass}`\n\n"
            f"🟩 *অ্যাকাউন্ট তৈরি করা হয়ে গেলে, আপনার Facebook User ID (UID) লিখে পাঠান:*"
        )
        bot.send_message(chat_id, task_msg, parse_mode="Markdown", reply_markup=cancel_markup)

    elif text.startswith("🔐 ফেসবুক 2FA কাজ"):
        if not get_2fa_status():
            bot.send_message(chat_id, "🚫 *দুঃখিত, বর্তমানে ফেসবুক 2FA কাজ বন্ধ আছে। পরবর্তী আপডেটের জন্য অপেক্ষা করুন।*", parse_mode="Markdown")
            return

        current_pass = get_current_password()
        update_user_data(user_id, {"state": "waiting_for_uid_2fa", "task_type": "2fa", "task_password": current_pass})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        task_msg = (
            f"🔵 *Facebook Account Creation Info:*\n\n"
            f"• Password : `{current_pass}`\n\n"
            f"🟩 *অ্যাকাউন্ট তৈরি করা হয়ে গেলে, আপনার Facebook User ID (UID) লিখে পাঠান:*"
        )
        bot.send_message(chat_id, task_msg, parse_mode="Markdown", reply_markup=cancel_markup)

    elif text == "📤 উত্তোলন":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(
            types.KeyboardButton("💰 বিকাশ -> সর্বনিম্ন ১০০৳ (৫ টাকা চার্জ)"),
            types.KeyboardButton("💰 নগদ -> সর্বনিম্ন ১০০৳ (৫ টাকা চার্জ)"),
            types.KeyboardButton("📱 মোবাইল রিচার্জ -> সর্বনিম্ন ২০৳"),
            types.KeyboardButton("❌ ফিরে যান")
        )
        bot.send_message(chat_id, "💰 *পেমেন্ট বা রিচার্জ মাধ্যম সিলেক্ট করুন:*", parse_mode="Markdown", reply_markup=markup)

    elif "বিকাশ" in text:
        user_data = get_user_data(user_id, message.from_user)
        if user_data["balance"] < MIN_WITHDRAW:
            bot.send_message(chat_id, f"❌ *সর্বনিম্ন সীমা {MIN_WITHDRAW} BDT*", parse_mode="Markdown")
        else:
            update_user_data(user_id, {"withdraw_method": "বিকাশ", "operator": "", "state": "waiting_for_withdraw_number"})
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            bot.send_message(chat_id, "📱 *আপনার ১১ ডিজিটের বিকাশ নম্বরটি দিন:*", parse_mode="Markdown", reply_markup=cancel_markup)

    elif "নগদ" in text:
        user_data = get_user_data(user_id, message.from_user)
        if user_data["balance"] < MIN_WITHDRAW:
            bot.send_message(chat_id, f"❌ *সর্বনিম্ন সীমা {MIN_WITHDRAW} BDT*", parse_mode="Markdown")
        else:
            update_user_data(user_id, {"withdraw_method": "নগদ", "operator": "", "state": "waiting_for_withdraw_number"})
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            bot.send_message(chat_id, "📱 *আপনার ১১ ডিজিটের নগদ নম্বরটি দিন:*", parse_mode="Markdown", reply_markup=cancel_markup)

    elif "মোবাইল রিচার্জ" in text:
        user_data = get_user_data(user_id, message.from_user)
        if user_data["balance"] < MIN_RECHARGE:
            bot.send_message(chat_id, f"❌ *সর্বনিম্ন রিচার্জ সীমা {MIN_RECHARGE} BDT*", parse_mode="Markdown")
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(
                types.KeyboardButton("🔵 গ্রামীণফোন (GP)"),
                types.KeyboardButton("🔴 রবি (Robi)"),
                types.KeyboardButton("⭕ এয়ারটেল (Airtel)"),
                types.KeyboardButton("🟠 বাংলালিংক (Banglalink)"),
                types.KeyboardButton("🟢 টেলিটক (Teletalk)"),
                types.KeyboardButton("❌ ফিরে যান")
            )
            update_user_data(user_id, {"withdraw_method": "মোবাইল রিচার্জ"})
            bot.send_message(chat_id, "📱 *আপনার মোবাইল অপারেটর (সিম) সিলেক্ট করুন:*", parse_mode="Markdown", reply_markup=markup)

    elif text in ["🔵 গ্রামীণফোন (GP)", "🔴 রবি (Robi)", "⭕ এয়ারটেল (Airtel)", "🟠 বাংলালিংক (Banglalink)", "🟢 টেলিটক (Teletalk)"]:
        operator_name = text.split(" ")[1]
        update_user_data(user_id, {"operator": operator_name, "state": "waiting_for_recharge_number"})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        bot.send_message(chat_id, f"📱 *সিম সিলেক্ট করা হয়েছে: {operator_name}*\n\nআপনার **১১ ডিজিটের মোবাইল নম্বরটি** দিন:", parse_mode="Markdown", reply_markup=cancel_markup)

    elif text == "📌 সাপোর্ট":
        support_text = (
            "🟢 *গ্রাহক সেবা কেন্দ্র*\n\n"
            "সম্মানিত মেম্বার,\n"
            "আপনার যেকোনো সমস্যা বা জিজ্ঞাসার জন্য আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন। We are online 24 hours.\n\n"
            f"⚠️ *বিশেষ দ্রষ্টব্য:* আপনার ব্যালেন্স বা মোট ইনকাম **৫০০ টাকা** বা তার বেশি হলে সরাসরি এডমিনের সাথে যোগাযোগ করুন: {ADMIN_USERNAME}"
        )
        support_markup = types.InlineKeyboardMarkup()
        support_markup.add(types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK))
        support_markup.add(types.InlineKeyboardButton("💬 এডমিনের সাথে যোগাযোগ", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}"))
        bot.send_message(chat_id, support_text, parse_mode="Markdown", reply_markup=support_markup)

    elif text == "🎁 Refer & Earn":
        user_data = get_user_data(user_id, message.from_user)
        ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        text_ref = (
            f"🎁 *REFER AND EARN* 💵\n\n"
            f"👥 *TOTAL REFERS:* {user_data['ref_count']}\n"
            f"💲 *TOTAL REFER INCOME:* {user_data.get('ref_income', 0.0):.2f} BDT\n\n"
            f"🔗 *আপনার রেফার লিংক:*\n`{ref_link}`\n"
        )
        bot.send_message(chat_id, text_ref, parse_mode="Markdown")

# ---------------- CALLBACK QUERY HANDLER ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    check_and_reset_leaderboard()
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if data == "verify_sub":
        if check_user_subscription(user_id):
            bot.answer_callback_query(call.id, "✅ ভেরিফিকেশন সফল হয়েছে!", show_alert=True)
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            main_menu(chat_id, "✨ *স্বাগতম! সফলভাবে ভেরিফাই সম্পন্ন হয়েছে। প্রধান মেনু:*")
        else:
            bot.answer_callback_query(call.id, "আপনি এখনো চ্যানেলে জয়েন করেননি!", show_alert=True)
        return

    if data == "check_my_rank":
        all_top = list(users_collection.find().sort("completed_tasks", -1))
        my_rank = "তালিকাভুক্ত নন"
        my_tasks = 0
        for idx, u in enumerate(all_top, 1):
            if u.get("user_id") == user_id:
                my_rank = f"নম্বর #{idx}"
                my_tasks = u.get("completed_tasks", 0)
                break
        
        user_doc = users_collection.find_one({"user_id": user_id})
        if user_doc:
            my_tasks = user_doc.get("completed_tasks", 0)
            
        bot.answer_callback_query(call.id, f"আপনার পজিশন: {my_rank}\nসম্পন্ন কাজ: {my_tasks} টি", show_alert=True)
        return

    if not check_user_subscription(user_id):
        bot.answer_callback_query(call.id, "⚠️ কাজ করতে হলে চ্যানেলে জয়েন করতে হবে!", show_alert=True)
        return

    if data.startswith("copy_code_"):
        code_to_copy = data.replace("copy_code_", "")
        bot.answer_callback_query(call.id, f"কোড কপি হয়েছে: {code_to_copy}", show_alert=True)
        return

    if data.startswith("approve_") and user_id == ADMIN_ID:
        parts = data.split("_")
        task_id = parts[1]

        task = tasks_collection.find_one({"_id": ObjectId(task_id)})
        if task and task.get("status") == "pending":
            target_user_id = task["user_id"]
            amount = task["price"]

            target_data = users_collection.find_one({"user_id": target_user_id})
            if target_data:
                new_bal = target_data["balance"] + amount
                new_completed = target_data["completed_tasks"] + 1
                new_pending = max(0, target_data["pending_tasks"] - 1)
                
                update_user_data(target_user_id, {"balance": new_bal, "completed_tasks": new_completed, "pending_tasks": new_pending})
                tasks_collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "approved"}})
                
                bot.send_message(target_user_id, f"🎉 *আপনার কাজটি সঠিক বলে গৃহীত হয়েছে! ব্যালেন্সে {amount} টাকা যোগ হয়েছে।*", parse_mode="Markdown")

                referrer_id = target_data.get("referred_by")
                if referrer_id:
                    ref_doc = users_collection.find_one({"user_id": referrer_id})
                    if ref_doc:
                        commission = round(amount * 0.05, 2)
                        ref_bal = ref_doc["balance"] + commission
                        ref_inc = ref_doc.get("ref_income", 0.0) + commission
                        update_user_data(referrer_id, {"balance": ref_bal, "ref_income": ref_inc})
                        try:
                            bot.send_message(referrer_id, f"🎁 *রেফার কমিশন বাবদ {commission:.2f} টাকা যোগ হয়েছে!*", parse_mode="Markdown")
                        except Exception:
                            pass

                bot.edit_message_text("✅ কাজ অ্যাপ্রুভ করা হয়েছে এবং ইউজারের ব্যালেন্সে টাকা যোগ হয়েছে!", chat_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "এই কাজটি ইতিমধ্যে প্রসেস করা হয়েছে!", show_alert=True)

    elif data.startswith("reject_") and user_id == ADMIN_ID:
        parts = data.split("_")
        task_id = parts[1]

        task = tasks_collection.find_one({"_id": ObjectId(task_id)})
        if task and task.get("status") == "pending":
            target_user_id = task["user_id"]
            rejected_uid = task.get("uid", "N/A")

            tasks_collection.update_one({"_id": ObjectId(task_id)}, {"$set": {"status": "rejected"}})
            target_data = users_collection.find_one({"user_id": target_user_id})
            if target_data:
                if target_data.get("pending_tasks", 0) > 0:
                    update_user_data(target_user_id, {"pending_tasks": target_data["pending_tasks"] - 1})

            bot.send_message(target_user_id, f"❌ *আপনার ফেসবুক UID:* `{rejected_uid}` *সমেত কাজটি রিজেক্ট করা হয়েছে।*", parse_mode="Markdown")
            bot.edit_message_text("❌ কাজ রিজেক্ট করা হয়েছে।", chat_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "এই কাজটি ইতিমধ্যে প্রসেস করা হয়েছে!", show_alert=True)

    elif (data.startswith("paid_") or data.startswith("rechargepaid_")) and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[1])
        amount = float(parts[2])
        method = parts[3] if len(parts) > 3 and "paid_" in data else "মোবাইল রিচার্জ"

        target_data = users_collection.find_one({"user_id": target_user_id})
        if target_data:
            remaining_balance = target_data.get("balance", 0.0)
            operator = target_data.get("operator", "")
            phone = target_data.get("withdraw_phone", "")

            withdraws_collection.update_one({"user_id": target_user_id, "status": "pending"}, {"$set": {"status": "completed"}})

            if "rechargepaid_" in data:
                user_msg = (
                    f"🎉 *অভিনন্দন! আপনার মোবাইল রিচার্জ সফল হয়েছে।*\n\n"
                    f"🌐 *অপারেটর:* {operator}\n"
                    f"📱 *নম্বর:* `{phone}`\n"
                    f"💵 *পরিমাণ:* {amount:.2f} BDT\n"
                    f"✅ *আপনার নাম্বারে রিচার্জ সফলভাবে পাঠানো হয়েছে!*\n\n"
                    f"💳 বর্তমান অবশিষ্ট ব্যালেন্স: *{remaining_balance:.2f} BDT*"
                )
            else:
                user_msg = (
                    f"🎉 *অভিনন্দন! আপনার উইথড্র রিকোয়েস্ট সফল হয়েছে।*\n\n"
                    f"💵 *পরিমাণ:* {amount:.2f} BDT\n"
                    f"💼 *মাধ্যম:* {method}\n"
                    f"📱 *নম্বর:* `{phone}`\n"
                    f"✅ *আপনার অ্যাকাউন্টে টাকা পাঠিয়ে দেওয়া হয়েছে!*\n\n"
                    f"💳 বর্তমান অবশিষ্ট ব্যালেন্স: *{remaining_balance:.2f} BDT*"
                )

            try:
                bot.send_message(target_user_id, user_msg, parse_mode="Markdown")
            except Exception:
                pass

            try:
                bot.edit_message_text(f"✅ সফলভাবে পরিশোধ করা হয়েছে হিসেবে মার্ক করা হয়েছে!\n👤 UID: `{target_user_id}` | পরিমাণ: {amount} BDT", chat_id, call.message.message_id, parse_mode="Markdown")
            except Exception:
                pass

# ---------------- MAIN EXECUTION ----------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("Bot is running perfectly...")
    bot.infinity_polling()
