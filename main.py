from flask import Flask
import os
import re
import telebot
from telebot import types
import threading
from pymongo import MongoClient

# ---------------- CONFIGURATION ----------------
TOKEN = "8965009856:AAGhnMhMFcKOogNC_Hepq7ZlPamuKJ2vHWw"
bot = telebot.TeleBot(TOKEN)

# MongoDB Connection & Collections Setup
MONGO_URI = "mongodb+srv://js3262481_db_user:ruman%4045@cluster0.p7mypr2.mongodb.net/?appName=Cluster0"
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["telegram_bot_db"]
    users_collection = db["users"]
    print("Connected to MongoDB successfully!")
except Exception as e:
    print(f"MongoDB connection error: {e}")

def load_data():
    data = {}
    try:
        for doc in users_collection.find():
            user_id = doc.get("user_id")
            if user_id:
                data[int(user_id)] = doc
    except Exception as e:
        print(f"Error loading from MongoDB: {e}")
    return data

def get_user_data(user_id):
    try:
        user_doc = users_collection.find_one({"user_id": int(user_id)})
        if not user_doc:
            new_user = {
                "user_id": int(user_id),
                "balance": 0.0,
                "ref_income": 0.0,
                "ref_count": 0,
                "referred_by": None,
                "state": None,
                "completed_tasks": 0,
                "pending_tasks": 0,
                "temp_uid": "",
                "temp_cookies": "",
                "task_password": "",
                "withdraw_method": "",
                "operator": "",
                "withdraw_phone": "",
            }
            users_collection.insert_one(new_user)
            return new_user
        return user_doc
    except Exception as e:
        print(f"Error getting user data: {e}")
        return {
            "user_id": int(user_id),
            "balance": 0.0,
            "ref_income": 0.0,
            "ref_count": 0,
            "referred_by": None,
            "state": None,
            "completed_tasks": 0,
            "pending_tasks": 0,
            "temp_uid": "",
            "temp_cookies": "",
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

users = load_data()
submitted_uids = set()

ADMIN_ID = 8449043852  # আপনার অ্যাডমিন আইডি

FORCE_CHANNEL_USERNAME = "@R4_Work_Sapait"
FORCE_CHANNEL_LINK = "https://t.me/R4_Work_Sapait"

CURRENT_PASSWORD = "Sakil@31"
TASK_PRICE = 5.00
PRICE_TEXT = "5.00 BDT"
WITHDRAW_FEE = 5.00
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
    global users
    user_id = message.from_user.id
    args = message.text.split()

    user_doc = users_collection.find_one({"user_id": int(user_id)})
    if not user_doc:
        new_user = {
            "user_id": int(user_id),
            "balance": 0.0,
            "ref_income": 0.0,
            "ref_count": 0,
            "referred_by": None,
            "state": None,
            "completed_tasks": 0,
            "pending_tasks": 0,
            "temp_uid": "",
            "temp_cookies": "",
            "task_password": "",
            "withdraw_method": "",
            "operator": "",
            "withdraw_phone": "",
        }
        
        if len(args) > 1:
            try:
                ref_id = int(args[1])
                ref_doc = users_collection.find_one({"user_id": ref_id})
                if ref_id != user_id and ref_doc:
                    new_user["referred_by"] = ref_id
                    users_collection.update_one({"user_id": ref_id}, {"$inc": {"ref_count": 1}})
            except ValueError:
                pass
        users_collection.insert_one(new_user)
        users = load_data()

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

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_balance = types.KeyboardButton("💰 ব্যালেন্স")
    btn_work = types.KeyboardButton("💼 কাজ")
    btn_withdraw = types.KeyboardButton("📤 উত্তোলন")
    btn_support = types.KeyboardButton("📌 সাপোর্ট")
    btn_refer = types.KeyboardButton("🎁 Refer & Earn")
    
    markup.add(btn_balance, btn_work, btn_withdraw, btn_support, btn_refer)
    bot.send_message(chat_id, text_msg, parse_mode="Markdown", reply_markup=markup)

# ---------------- MESSAGE & ADMIN HANDLER ----------------
@bot.message_handler(func=lambda message: True, content_types=["text", "audio", "voice"])
def handle_message(message):
    global CURRENT_PASSWORD, TASK_PRICE, PRICE_TEXT, users
    chat_id = message.chat.id
    user_id = message.from_user.id

    get_user_data(user_id)

    if not check_user_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ Verify (চেক করুন)", callback_data="verify_sub"))
        bot.send_message(
            chat_id,
            "⚠️ *বট ব্যবহার করতে হলে অবশ্যই নিচের চ্যানেলে জয়েন করতে হবে!*\nদয়া করে আগে জয়েন করুন।",
            parse_mode="Markdown",
            reply_markup=markup,
        )
        return

    if user_id == ADMIN_ID and message.content_type == "text":
        text = message.text.strip()
        if text.startswith("/setpass "):
            new_pass = text.replace("/setpass ", "").strip()
            if new_pass:
                CURRENT_PASSWORD = new_pass
                bot.send_message(chat_id, f"✅ নতুন পাসওয়ার্ড: `{CURRENT_PASSWORD}`", parse_mode="Markdown")
            return

        if text.startswith("/setprice "):
            new_price_str = text.replace("/setprice ", "").strip()
            try:
                TASK_PRICE = float(new_price_str)
                PRICE_TEXT = f"{TASK_PRICE:.2f} BDT"
                bot.send_message(chat_id, f"✅ নতুন প্রাইস: `{PRICE_TEXT}`", parse_mode="Markdown")
            except ValueError:
                pass
            return

        if text.startswith("/notice "):
            notice_text = text.replace("/notice ", "").strip()
            if notice_text:
                all_users = users_collection.find()
                for u in all_users:
                    try:
                        bot.send_message(int(u["user_id"]), f"📢 *বিশেষ ঘোষণা / নোটিশ*\n\n{notice_text}", parse_mode="Markdown")
                    except Exception:
                        pass
                bot.send_message(chat_id, "✅ নোটিশ পাঠানো সম্পন্ন!", parse_mode="Markdown")
            return

    if message.content_type != "text":
        return

    text = message.text.strip()
    user_data = get_user_data(user_id)

    if text == "❌ বাতিল":
        update_user_data(user_id, {"state": None})
        main_menu(chat_id, "🏢 *প্রধান মেনুতে ফিরিয়ে আনা হয়েছে।*")
        return

    user_state = user_data.get("state")

    if user_state == "waiting_for_uid":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট", "🎁 Refer & Earn"]:
            bot.send_message(chat_id, "⚠️ *কাজের ভেতরে আছেন! বাতিল করতে '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        uid = text
        if not uid.isdigit() or len(uid) < 5 or len(uid) > 20:
            bot.send_message(chat_id, "❌ *সঠিক ফেসবুক UID দিন অথবা '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        if uid in submitted_uids:
            bot.send_message(chat_id, "❌ *এই ফেসবুক UID টি ইতিমধ্যে জমা দেওয়া হয়েছে!*", parse_mode="Markdown")
        else:
            update_user_data(user_id, {"temp_uid": uid, "state": "waiting_for_cookies"})
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            bot.send_message(chat_id, "🛡️ *আপনার অ্যাকাউন্টের কুকিজ পেস্ট করুন 📍*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_cookies":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট", "🎁 Refer & Earn"]:
            bot.send_message(chat_id, "⚠️ *কুকিজ দিন অথবা বাতিল করুন।*", parse_mode="Markdown")
            return

        update_user_data(user_id, {"temp_cookies": text, "state": "waiting_for_finish_button"})
        finish_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        finish_markup.add(types.KeyboardButton("অ্যাকাউন্ট খোলা শেষ"), types.KeyboardButton("❌ বাতিল"))
        bot.send_message(chat_id, "✅ *অ্যাকাউন্ট খোলা শেষ হলে নিচের বাটনে চাপ দিন:*", parse_mode="Markdown", reply_markup=finish_markup)
        return

    elif user_state == "waiting_for_finish_button":
        if text == "অ্যাকাউন্ট খোলা শেষ":
            current_data = get_user_data(user_id)
            uid = current_data.get("temp_uid")
            cookies = current_data.get("temp_cookies")

            submitted_uids.add(uid)
            update_user_data(user_id, {"pending_tasks": current_data.get("pending_tasks", 0) + 1, "state": None})

            admin_msg = f"📥 *নতুন কাজ জমা পড়েছে!*\n\n👤 ইউজার ID: `{user_id}`\n📌 UID: `{uid}`\n🍪 কুকিজ:\n`{cookies}`\n\n💵 মূল্য: {PRICE_TEXT}"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ সঠিক (Approve)", callback_data=f"approve_{user_id}_{TASK_PRICE}_{uid}"),
                types.InlineKeyboardButton("❌ ভুল (Reject)", callback_data=f"reject_{user_id}_{uid}")
            )
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)
            bot.send_message(chat_id, "🎉 *টাস্ক সফলভাবে জমা হয়েছে!*", parse_mode="Markdown")
            main_menu(chat_id, "⏳ *রিভিউতে পাঠানো হয়েছে।*")
        return

    # FIXED: রিমোট রিচার্জের ক্ষেত্রে স্টেপ ঠিক করা হয়েছে (প্রথমে নম্বর, পরে অ্যামাউন্ট)
    elif user_state == "waiting_for_recharge_number":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট", "🎁 Refer & Earn"]:
            bot.send_message(chat_id, "⚠️ *উইথড্র প্রক্রিয়ায় আছেন! বাতিল করতে '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        phone = text.strip()
        if not re.match(r"^01[3-9]\d{8}$", phone):
            bot.send_message(chat_id, "❌ *সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন (যেমন: 01934546320)।*", parse_mode="Markdown")
            return

        update_user_data(user_id, {"withdraw_phone": phone, "state": "waiting_for_recharge_amount"})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        
        operator = user_data.get("operator", "")
        bot.send_message(chat_id, f"💰 *কত টাকা রিচার্জ ({operator}) করতে চান? (যেমন: ২০, ৫০, ১০০) সংখ্যায় লিখুন:*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_recharge_amount":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট", "🎁 Refer & Earn"]:
            bot.send_message(chat_id, "⚠️ *প্রক্রিয়াধীন আছে! বাতিল করতে '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        amount = parse_bangla_number(text)
        if amount is None:
            bot.send_message(chat_id, "❌ *দয়া করে সঠিক সংখ্যায় পরিমাণ লিখুন (যেমন: 50 বা ৫০)।*", parse_mode="Markdown")
            return

        current_data = get_user_data(user_id)
        balance = current_data["balance"]
        operator = current_data.get("operator", "")
        phone = current_data.get("withdraw_phone", "")

        if amount < MIN_RECHARGE:
            bot.send_message(chat_id, f"❌ *সর্বনিম্ন রিচার্জ পরিমাণ {MIN_RECHARGE} BDT। আবার সঠিক পরিমাণ লিখুন:*", parse_mode="Markdown")
            return

        if amount > balance:
            bot.send_message(chat_id, f"❌ *পর্যাপ্ত ব্যালেন্স নেই! বর্তমান ব্যালেন্স: {balance:.2f} BDT*", parse_mode="Markdown")
            return

        new_balance = balance - amount
        update_user_data(user_id, {"state": None, "balance": new_balance})

        admin_msg = f"📱 *নতুন মোবাইল রিচার্জ রিকোয়েস্ট!*\n\n👤 ইউজার ID: `{user_id}`\n🌐 অপারেটর: *{operator}*\n📞 নম্বর: `{phone}`\n💰 পরিমাণ: {amount} BDT"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ সফল হয়েছে (পাঠানো হয়েছে)", callback_data=f"rechargepaid_{user_id}_{amount}"))

        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)

        user_success_msg = (
            f"✅ *আপনার রিকোয়েস্ট সফলভাবে সাবমিট হয়েছে!*\n\n"
            f"🌐 *অপারেটর:* মোবাইল রিচার্জ ({operator})\n"
            f"📱 *নম্বর:* {phone}\n"
            f"💵 *পরিমাণ:* {amount:.2f} BDT\n"
            f"🔄 *অ্যাডমিন প্যানেলে পাঠানো হয়েছে, শীঘ্রই পাঠানো হবে!*\n\n"
            f"💳 অবশিষ্ট ব্যালেন্স: *{new_balance:.2f} BDT*"
        )
        bot.send_message(chat_id, user_success_msg, parse_mode="Markdown")
        main_menu(chat_id, "✨ *প্রধান মেনু:*")
        return

    elif user_state == "waiting_for_withdraw_number":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট", "🎁 Refer & Earn"]:
            bot.send_message(chat_id, "⚠️ *উইথড্র প্রক্রিয়ায় আছেন! বাতিল করতে '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        phone = text.strip()
        if not re.match(r"^01[3-9]\d{8}$", phone):
            bot.send_message(chat_id, "❌ *সঠিক ১১ ডিজিটের মোবাইল নম্বর দিন (যেমন: 01934546320)।*", parse_mode="Markdown")
            return

        update_user_data(user_id, {"withdraw_phone": phone, "state": "waiting_for_withdraw_amount"})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        
        method = user_data.get("withdraw_method", "বিকাশ")
        bot.send_message(chat_id, f"💰 *কত টাকা উত্তোলন করতে চান? (যেমন: ১০০, ২০০) সংখ্যায় লিখুন:*", parse_mode="Markdown", reply_markup=cancel_markup)
        return

    elif user_state == "waiting_for_withdraw_amount":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট", "🎁 Refer & Earn"]:
            bot.send_message(chat_id, "⚠️ *প্রক্রিয়াধীন আছে! বাতিল করতে '❌ বাতিল' চাপুন।*", parse_mode="Markdown")
            return

        amount = parse_bangla_number(text)
        if amount is None:
            bot.send_message(chat_id, "❌ *দয়া করে সঠিক সংখ্যায় পরিমাণ লিখুন (যেমন: 100 বা ১০০)।*", parse_mode="Markdown")
            return

        current_data = get_user_data(user_id)
        balance = current_data["balance"]
        method = current_data.get("withdraw_method", "বিকাশ")
        phone = current_data.get("withdraw_phone", "")

        if amount < MIN_WITHDRAW:
            bot.send_message(chat_id, f"❌ *সর্বনিম্ন পরিমাণ {MIN_WITHDRAW} BDT। আবার সঠিক পরিমাণ লিখুন:*", parse_mode="Markdown")
            return

        if amount > balance:
            bot.send_message(chat_id, f"❌ *পর্যাপ্ত ব্যালেন্স নেই! বর্তমান ব্যালেন্স: {balance:.2f} BDT*", parse_mode="Markdown")
            return

        new_balance = balance - amount
        update_user_data(user_id, {"state": None, "balance": new_balance})

        admin_msg = f"📤 *নতুন উইথড্র রিকোয়েস্ট!*\n\n👤 ইউজার ID: `{user_id}`\n💼 মাধ্যম: {method}\n📞 নম্বর: `{phone}`\n💰 পরিমাণ: {amount} BDT\n✂️ চার্জ: {WITHDRAW_FEE} BDT"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ সফল হয়েছে (পাঠানো হয়েছে)", callback_data=f"paid_{user_id}_{amount}_{method}"))

        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)

        user_success_msg = (
            f"✅ *আপনার রিকোয়েস্ট সফলভাবে সাবমিট হয়েছে!*\n\n"
            f"💼 *মাধ্যম:* {method}\n"
            f"📱 *নম্বর:* {phone}\n"
            f"💵 *পরিমাণ:* {amount:.2f} BDT\n"
            f"🔄 *অ্যাডমিন প্যানেলে পাঠানো হয়েছে, শীঘ্রই পাঠানো হবে!*\n\n"
            f"💳 অবশিষ্ট ব্যালেন্স: *{new_balance:.2f} BDT*"
        )
        bot.send_message(chat_id, user_success_msg, parse_mode="Markdown")
        main_menu(chat_id, "✨ *প্রধান মেনু:*")
        return

    if text == "💰 ব্যালেন্স":
        data = get_user_data(user_id)
        reply_text = (
            f"👤 *আপনার একাউন্ট ব্যালেন্স:*\n\n"
            f"🟢 ব্যালেন্স: {data['balance']:.2f} BDT\n"
            f"👥 রেফারেল ইনকাম: {data.get('ref_income', 0.0):.2f} BDT\n\n"
            f"✅ সম্পন্ন কাজ: {data['completed_tasks']} টি\n"
            f"🔄 রিভিউতে আছে: {data['pending_tasks']} টি"
        )
        bot.send_message(chat_id, reply_text, parse_mode="Markdown")

    elif text == "💼 কাজ":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"Facebook কাজ ({PRICE_TEXT})", callback_data="fb_task"))
        bot.send_message(chat_id, "✏️ *যেকোনো একটি কাজ সিলেক্ট করুন নিচে:*\n👇", parse_mode="Markdown", reply_markup=markup)

    elif text == "📤 উত্তোলন":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("বিকাশ -> সর্বনিম্ন ১০০টাকা (৫ টাকা চার্জ)", callback_data="withdraw_bkash"))
        markup.add(types.InlineKeyboardButton("নগদ -> সর্বনিম্ন ১০০টাকা (৫ টাকা চার্জ)", callback_data="withdraw_nagad"))
        markup.add(types.InlineKeyboardButton("📱 মোবাইল রিচার্জ -> সর্বনিম্ন ২০টাকা", callback_data="withdraw_recharge"))
        bot.send_message(chat_id, "💰 *পেমেন্ট বা রিচার্জ মাধ্যম সিলেক্ট করুন:*", parse_mode="Markdown", reply_markup=markup)

    elif text == "📌 সাপোর্ট":
        support_text = "👤 *গ্রাহক সেবা কেন্দ্র*\n\nআপনার যেকোনো সমস্যায় আমাদের অফিসিয়াল চ্যানেলে যোগাযোগ করুন।"
        support_markup = types.InlineKeyboardMarkup()
        support_markup.add(types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK))
        bot.send_message(chat_id, support_text, parse_mode="Markdown", reply_markup=support_markup)

    elif text == "🎁 Refer & Earn":
        user_data = get_user_data(user_id)
        ref_link = f"https://t.me/{bot.get_me().username}?start={user_id}"
        text_ref = (
            f"🎁 *REFER AND EARN* 💵\n\n"
            f"👥 *TOTAL REFERS:* {user_data['ref_count']}\n"
            f"💲 *TOTAL REFER INCOME:* {user_data.get('ref_income', 0.0):.2f} BDT\n\n"
            f"🔗 *আপনার রেফার লিংক:*\n`{ref_link}`\n\n"
            f"💰 *আপনার রেফার করা ব্যক্তি যত টাকা ইনকাম করবে, আপনি তার ৫% কমিশন পাবেন।*"
        )
        bot.send_message(chat_id, text_ref, parse_mode="Markdown")

# ---------------- CALLBACK QUERY HANDLER ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    global users
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

    if not check_user_subscription(user_id):
        bot.answer_callback_query(call.id, "⚠️ কাজ করতে হলে চ্যানেলে জয়েন করতে হবে!", show_alert=True)
        return

    if data == "fb_task":
        update_user_data(user_id, {"state": "waiting_for_uid", "task_password": CURRENT_PASSWORD})
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        task_msg = f"🔵 *Facebook Account Creation Info (মূল্য: {PRICE_TEXT}):*\n\n✔ Password : `{CURRENT_PASSWORD}`\n\n💬 *একউন্ট তৈরি করে আপনার Facebook User ID (UID) দিন:*"
        bot.send_message(chat_id, task_msg, parse_mode="Markdown", reply_markup=cancel_markup)

    elif data == "withdraw_recharge":
        user_data = get_user_data(user_id)
        if user_data["balance"] < MIN_RECHARGE:
            bot.answer_callback_query(call.id, "পর্যাপ্ত ব্যালেন্স নেই!", show_alert=True)
            bot.send_message(chat_id, f"❌ *আপনার ব্যালেন্স পর্যাপ্ত নয়! সর্বনিম্ন রিচার্জ সীমা {MIN_RECHARGE} BDT*", parse_mode="Markdown")
        else:
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔵 গ্রামীণফোন (GP)", callback_data="op_Grameenphone"),
                types.InlineKeyboardButton("🔴 রবি (Robi)", callback_data="op_Robi"),
                types.InlineKeyboardButton("⭕ এয়ারটেল (Airtel)", callback_data="op_Airtel"),
                types.InlineKeyboardButton("🟠 বাংলালিংক (Banglalink)", callback_data="op_Banglalink"),
                types.InlineKeyboardButton("🟢 টেলিটক (Teletalk)", callback_data="op_Teletalk")
            )
            update_user_data(user_id, {"withdraw_method": "মোবাইল রিচার্জ"})
            bot.send_message(chat_id, "📱 *আপনার মোবাইল অপারেটর (সিম) সিলেক্ট করুন:*", parse_mode="Markdown", reply_markup=markup)

    elif data in ["withdraw_bkash", "withdraw_nagad"]:
        method = "বিকাশ" if "bkash" in data else "নগদ"
        user_data = get_user_data(user_id)
        if user_data["balance"] < MIN_WITHDRAW:
            bot.answer_callback_query(call.id, "পর্যাপ্ত ব্যালেন্স নেই!", show_alert=True)
            bot.send_message(chat_id, f"❌ *আপনার ব্যালেন্স পর্যাপ্ত নয়! সর্বনিম্ন সীমা {MIN_WITHDRAW} BDT*", parse_mode="Markdown")
        else:
            update_user_data(user_id, {"withdraw_method": method, "operator": "", "state": "waiting_for_withdraw_number"})
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            bot.send_message(chat_id, f"📱 *আপনার ১১ ডিজিটের {method} নম্বরটি দিন:*", parse_mode="Markdown", reply_markup=cancel_markup)

    elif data.startswith("op_"):
        operator_name = data.replace("op_", "")
        # সিম সিলেক্ট করার পর প্রথমে নম্বর চাওয়া হবে (স্টেপ অনুযায়ী)
        update_user_data(user_id, {"operator": operator_name, "state": "waiting_for_recharge_number"})
        
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        bot.send_message(chat_id, f"📱 *সিম সিলেক্ট করা হয়েছে: {operator_name}*\n\nএখন আপনার **১১ ডিজিটের মোবাইল নম্বরটি** দিন:", parse_mode="Markdown", reply_markup=cancel_markup)

    elif data.startswith("approve_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[1])
        amount = float(parts[2])

        target_data = get_user_data(target_user_id)
        if target_data:
            new_bal = target_data["balance"] + amount
            new_completed = target_data["completed_tasks"] + 1
            new_pending = max(0, target_data["pending_tasks"] - 1)
            
            update_user_data(target_user_id, {"balance": new_bal, "completed_tasks": new_completed, "pending_tasks": new_pending})
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

            bot.edit_message_text("✅ কাজ অ্যাপ্রুভ করা হয়েছে!", chat_id, call.message.message_id)

    elif data.startswith("reject_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[1])
        rejected_uid = parts[2] if len(parts) > 2 else "N/A"

        target_data = get_user_data(target_user_id)
        if target_data:
            if target_data.get("pending_tasks", 0) > 0:
                update_user_data(target_user_id, {"pending_tasks": target_data["pending_tasks"] - 1})

            bot.send_message(target_user_id, f"❌ *আপনার ফেসবুক UID:* `{rejected_uid}` *সমেত কাজটি রিজেক্ট করা হয়েছে।*", parse_mode="Markdown")
            bot.edit_message_text("❌ কাজ রিজেক্ট করা হয়েছে।", chat_id, call.message.message_id)

    elif (data.startswith("paid_") or data.startswith("rechargepaid_")) and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[1])
        amount = float(parts[2])
        method = parts[3] if len(parts) > 3 and "paid_" in data else "মোবাইল রিচার্জ"

        target_data = get_user_data(target_user_id)
        if target_data:
            remaining_balance = target_data.get("balance", 0.0)
            operator = target_data.get("operator", "")
            phone = target_data.get("withdraw_phone", "")

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

    print("Bot and Flask server are running perfectly with exact steps...")
    bot.infinity_polling()
