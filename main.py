import os
import threading
from flask import Flask
from pymongo import MongoClient
import telebot
from telebot import types
import re

# ---------------- CONFIGURATION ----------------
TOKEN = os.environ.get('BOT_TOKEN', '8965009856:AAEBSRHIuXA-jUGXMZLXiKa2mt2rsLdlcus')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb+srv://rumanhasan112233:Sakil%4031@cluster0.z2s37.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')

bot = telebot.TeleBot(TOKEN)

# ---------------- MONGODB SETUP ----------------
client = MongoClient(MONGO_URL)
db = client['telegram_earning_bot_db']
users_collection = db['users']
globals_collection = db['globals']
submitted_uids_collection = db['submitted_uids']

ADMIN_ID = 8449043852   # আপনার অ্যাডমিন আইডি

# ডিফল্ট সেটিংস ফাংশন (ডাটাবেজ থেকে লোড করার জন্য)
def get_global_setting(key, default_val):
    res = globals_collection.find_one({"key": key})
    if res:
        return res["value"]
    globals_collection.insert_one({"key": key, "value": default_val})
    return default_val

def set_global_setting(key, value):
    globals_collection.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

# ইনিশিয়াল সেটিংস চেক বা সেট
if globals_collection.find_one({"key": "current_password"}) is None:
    set_global_setting("current_password", "Sakil@31")
if globals_collection.find_one({"key": "task_price"}) is None:
    set_global_setting("task_price", 5.00)

MIN_WITHDRAW = 100.0    # সর্বনিম্ন উত্তোলন পরিমাণ
WITHDRAW_FEE = 5.00     # উইথড্র চার্জ (৫ টাকা)

# ---------------- FLASK SERVER (24/7 UPTIME) ----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7 successfully!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()


# ---------------- HELPER FUNCTIONS FOR DB ----------------
def get_user(user_id):
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "balance": 0.0,  # নতুন ইউজারের ডিফল্ট ব্যালেন্স ০ করা হলো
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
            "withdraw_phone": ""
        }
        users_collection.insert_one(user)
    return user

def update_user(user_id, update_data):
    users_collection.update_one({"user_id": user_id}, {"$set": update_data})


# ---------------- START COMMAND & MAIN MENU ----------------
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    args = message.text.split()
    
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "balance": 0.0,  # নতুন ইউজারের ডিফল্ট ব্যালেন্স ০ করা হলো
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
            "withdraw_phone": ""
        }
        users_collection.insert_one(user)
        
        if len(args) > 1:
            try:
                ref_id = int(args[1])
                if ref_id != user_id:
                    ref_user = users_collection.find_one({"user_id": ref_id})
                    if ref_user:
                        users_collection.update_one({"user_id": user_id}, {"$set": {"referred_by": ref_id}})
                        users_collection.update_one({"user_id": ref_id}, {"$inc": {"ref_count": 1}})
            except ValueError:
                pass

    main_menu(message.chat.id, "প্রধান মেনু:")

def main_menu(chat_id, text_msg):
    users_collection.update_one({"user_id": chat_id}, {"$set": {"state": None}})
        
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_balance = types.KeyboardButton("💰 ব্যালেন্স")
    btn_work = types.KeyboardButton("💼 কাজ")
    btn_withdraw = types.KeyboardButton("📤 উত্তোলন")
    btn_support = types.KeyboardButton("📌 সাপোর্ট")
    markup.add(btn_balance, btn_work, btn_withdraw, btn_support)
    
    bot.send_message(chat_id, text_msg, reply_markup=markup)


# ---------------- MAIN MESSAGE & ADMIN COMMAND HANDLER ----------------
@bot.message_handler(func=lambda message: True, content_types=['text', 'audio', 'voice'])
def handle_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    user = get_user(user_id)
    current_pass = get_global_setting("current_password", "Sakil@31")
    task_price = get_global_setting("task_price", 5.00)
    price_text = f"{task_price:.2f} BDT"

    # পাসওয়ার্ড পরিবর্তনের কমান্ড (শুধু অ্যাডমিন)
    if user_id == ADMIN_ID and message.content_type == 'text':
        text = message.text.strip()
        if text.startswith("/setpass "):
            new_pass = text.replace("/setpass ", "").strip()
            if new_pass:
                set_global_setting("current_password", new_pass)
                bot.send_message(chat_id, f"✅ সফলভাবে ফেসবুক কাজের পাসওয়ার্ড পরিবর্তন করা হয়েছে!\nনতুন পাসওয়ার্ড: `{new_pass}`", parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "⚠️ দয়া করে পাসওয়ার্ড সহ লিখুন। যেমন: `/setpass Abc@1234`", parse_mode="Markdown")
            return

        # প্রাইস পরিবর্তনের কমান্ড (শুধু অ্যাডমিন)
        if text.startswith("/setprice "):
            new_price_str = text.replace("/setprice ", "").strip()
            try:
                new_price = float(new_price_str)
                set_global_setting("task_price", new_price)
                bot.send_message(chat_id, f"✅ সফলভাবে ফেসবুক কাজের প্রাইস পরিবর্তন করা হয়েছে!\nনতুন প্রাইস: `{new_price:.2f} BDT`", parse_mode="Markdown")
            except ValueError:
                bot.send_message(chat_id, "⚠️ সঠিক সংখ্যা দিয়ে প্রাইস লিখুন। যেমন: `/setprice 6` অথবা `/setprice 5.50`", parse_mode="Markdown")
            return

        # টেক্সট নোটিশ পাঠানোর কমান্ড (শুধু অ্যাডমিন)
        if text.startswith("/notice "):
            notice_text = text.replace("/notice ", "").strip()
            if notice_text:
                success_count = 0
                fail_count = 0
                all_users = users_collection.find({})
                for u in all_users:
                    try:
                        bot.send_message(u["user_id"], f"📢 **বিশেষ ঘোষণা / নোটিশ**\n\n{notice_text}", parse_mode="Markdown")
                        success_count += 1
                    except Exception:
                        fail_count += 1
                bot.send_message(chat_id, f"✅ নোটিশ পাঠানো সম্পন্ন!\nসফলভাবে গেছে: {success_count} জনের কাছে\nব্যর্থ হয়েছে: {fail_count} জনের কাছে")
            else:
                bot.send_message(chat_id, "⚠️ দয়া করে নোটিশের লেখা সহ দিন।")
            return

    # ভয়েস বা অডিও নোটিশ পাঠানোর নিয়ম (শুধু অ্যাডমিন)
    if user_id == ADMIN_ID and message.content_type in ['audio', 'voice']:
        file_id = message.voice.file_id if message.content_type == 'voice' else message.audio.file_id
        success_count = 0
        fail_count = 0
        
        all_users = users_collection.find({})
        for u in all_users:
            try:
                if message.content_type == 'voice':
                    bot.send_voice(u["user_id"], file_id, caption="🎙️ নতুন ভয়েস নোটিশ")
                else:
                    bot.send_audio(u["user_id"], file_id, caption="🎵 নতুন অডিও নোটিশ")
                success_count += 1
            except Exception:
                fail_count += 1
                
        bot.send_message(chat_id, f"✅ ভয়েস নোটিশ পাঠানো সম্পন্ন!\nসফলভাবে গেছে: {success_count} জনের কাছে\nব্যর্থ হয়েছে: {fail_count} জনের কাছে")
        return

    if message.content_type != 'text':
        return

    text = message.text.strip()

    if text == "❌ বাতিল":
        update_user(user_id, {"state": None})
        main_menu(chat_id, "🏢 আপনাকে প্রধান মেনুতে ফিরিয়ে আনা হয়েছে! কাজ বাতিল করা হয়েছে।")
        return

    user_state = user.get("state")
    
    # ১. টাস্ক সাবমিশন প্রসেস: UID গ্রহণ
    if user_state == "waiting_for_uid":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
            bot.send_message(chat_id, "⚠️ আপনি বর্তমানে কাজের ভেতরে আছেন! কাজ করতে না চাইলে নিচের '❌ বাতিল' বাটনে চাপুন।")
            return
            
        if user.get("task_password") != current_pass:
            update_user(user_id, {"state": None})
            main_menu(chat_id, "⚠️ এই পাসওয়ার্ডের মেয়াদ শেষ বা পরিবর্তিত হয়েছে! দয়া করে '💼 কাজ' মেনু থেকে নতুন করে কাজ শুরু করুন।")
            return

        uid = text
        if not uid.isdigit() or len(uid) < 5 or len(uid) > 20:
            bot.send_message(chat_id, "❌ এটি কোনো সঠিক ফেসবুক UID নয়! সঠিক ফেসবুক UID দিন অথবা '❌ বাতিল' বাটনে চাপুন।")
            return

        is_submitted = submitted_uids_collection.find_one({"uid": uid})
        if is_submitted:
            bot.send_message(chat_id, "❌ এই ফেসবুক UID টি ইতিমধ্যে একবার জমা দেওয়া হয়েছে!")
        else:
            update_user(user_id, {"temp_uid": uid, "state": "waiting_for_cookies"})
            
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            
            bot.send_message(chat_id, "🛡️ নিচে আপনার অ্যাকাউন্টের কুকিজ পেস্ট করুন 📍", reply_markup=cancel_markup)
        return

    # ২. টাস্ক সাবমিশন প্রসেস: কুকিজ গ্রহণ
    elif user_state == "waiting_for_cookies":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
            bot.send_message(chat_id, "⚠️ কুকিজ দিন অথবা কাজ বাতিল করতে নিচের '❌ বাতিল' বাটনে চাপুন।")
            return

        update_user(user_id, {"temp_cookies": text, "state": "waiting_for_finish_button"})
        
        finish_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        finish_markup.add(types.KeyboardButton("অ্যাকাউন্ট খোলা শেষ"), types.KeyboardButton("❌ বাতিল"))
        
        bot.send_message(chat_id, "✅ অ্যাকাউন্ট খোলা শেষ হলে নিচের বাটনে চাপ দিন:", reply_markup=finish_markup)
        return

    # ৩. টাস্ক সাবমিশন প্রসেস: অ্যাকাউন্ট খোলা শেষ বাটন
    elif user_state == "waiting_for_finish_button":
        if text == "অ্যাকাউন্ট খোলা শেষ":
            fresh_user = get_user(user_id)
            uid = fresh_user["temp_uid"]
            cookies = fresh_user["temp_cookies"]
            
            submitted_uids_collection.insert_one({"uid": uid})
            users_collection.update_one({"user_id": user_id}, {"$inc": {"pending_tasks": 1}, "$set": {"state": None}})
            
            admin_msg = (
                f"📥 **নতুন কাজ জমা পড়েছে!**\n\n"
                f"👤 ইউজার আইডি: `{user_id}`\n"
                f"📌 ফেসবুক UID: `{uid}`\n"
                f"🍪 কুকিজ:\n`{cookies}`\n\n"
                f"💵 কাজের মূল্য: {price_text}"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ সঠিক (Approve)", callback_data=f"approve_{user_id}_{task_price}_{uid}"),
                types.InlineKeyboardButton("❌ ভুল (Reject)", callback_data=f"reject_{user_id}_{uid}")
            )
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup)
            
            bot.send_message(chat_id, "🎉 টাস্ক সফলভাবে জমা হয়েছে!")
            main_menu(chat_id, "⏳ আপনার কাজটি রিভিউতে পাঠানো হয়েছে। প্রধান মেনুতে স্বাগতম!")
        else:
            bot.send_message(chat_id, "দয়া করে নিচের **'অ্যাকাউন্ট খোলা শেষ'** অথবা **'❌ বাতিল'** বাটনে ক্লিক করুন।")
        return

    # ৪. উইথড্র স্টেপ ১: সঠিক বাংলাদেশি বিকাশ/নগদ নম্বর ভ্যালিডেশন
    elif user_state == "waiting_for_withdraw_number":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
            bot.send_message(chat_id, "⚠️ উইথড্র প্রক্রিয়ায় আছেন! বাতিল করতে চাইলে '❌ বাতিল' বাটনে চাপুন।")
            return
            
        phone = text.strip()
        if not re.match(r"^01[3-9]\d{8}$", phone):
            bot.send_message(chat_id, "❌ এটি কোনো সঠিক বিকাশ বা নগদ নম্বর নয়! সঠিক ১১ ডিজিটের নম্বর দিন (যেমন: 01934546320)।")
            return

        update_user(user_id, {"withdraw_phone": phone, "state": "waiting_for_withdraw_amount"})
        
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
        
        bot.send_message(
            chat_id, 
            "💰 আপনি কত টাকা উত্তোলন করতে চান? শুধু সংখ্যায় লিখুন:\nযেমন: ১০০ বা ২৫০ বা ৫০০", 
            reply_markup=cancel_markup
        )
        return

    # ৫. উইথড্র স্টেপ ২: টাকার পরিমাণ গ্রহণ ও যাচাই করা
    elif user_state == "waiting_for_withdraw_amount":
        if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
            bot.send_message(chat_id, "⚠️ উইথড্র প্রক্রিয়ায় আছেন! বাতিল করতে চাইলে '❌ বাতিল' বাটনে চাপুন।")
            return

        try:
            amount = float(text)
        except ValueError:
            bot.send_message(chat_id, "❌ দয়া করে শুধুমাত্র সংখ্যায় টাকার পরিমাণ লিখুন (যেমন: 100)।")
            return

        balance = user["balance"]
        method = user.get("withdraw_method", "বিকাশ")
        phone = user.get("withdraw_phone", "")

        if amount < MIN_WITHDRAW:
            bot.send_message(chat_id, f"❌ সর্বনিম্ন উত্তোলনের পরিমাণ {MIN_WITHDRAW} BDT। আবার সঠিক পরিমাণ লিখুন:")
            return

        if amount > balance:
            bot.send_message(chat_id, f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই! বর্তমান ব্যালেন্স: {balance:.2f} BDT\nপুনরায় সঠিক পরিমাণ লিখুন:")
            return

        # ইউজারের ব্যালেন্স সাথে সাথে কেটে নেওয়া
        users_collection.update_one({"user_id": user_id}, {"$inc": {"balance": -amount}, "$set": {"state": None}})
        updated_user = get_user(user_id)
        remaining_balance = updated_user["balance"]

        admin_withdraw_msg = (
            f"📤 **নতুন উইথড্র রিকোয়েস্ট!**\n\n"
            f"👤 ইউজার আইডি: `{user_id}`\n"
            f"💼 মাধ্যম: {method}\n"
            f"📞 নম্বর/ডিটেইলস: `{phone}`\n"
            f"💰 উত্তোলনের পরিমাণ: {amount} BDT\n"
            f"✂️ চার্জ কাটা হয়েছে: {WITHDRAW_FEE} BDT"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ সফল হয়েছে (টাকা পাঠানো হয়েছে)", callback_data=f"paid_{user_id}_{amount}_{method}"))
        
        bot.send_message(ADMIN_ID, admin_withdraw_msg, parse_mode="Markdown", reply_markup=markup)
        
        user_success_msg = (
            f"✅ **আপনার উইথড্র রিকোয়েস্ট সফল হয়েছে!**\n\n"
            f"💼 **মেথড:** {method}\n"
            f"📱 **Number/Details:** {phone}\n"
            f"💵 **উত্তোলনের পরিমাণ:** {amount:.2f} BDT\n"
            f"🔄 **অ্যাডমিন প্যানেলে এটি পাঠানো হয়েছে!**\n\n"
            f"💳 অবশিষ্ট ব্যালেন্স: *{remaining_balance:.2f} BDT*"
        )
        bot.send_message(chat_id, user_success_msg, parse_mode="Markdown")
        main_menu(chat_id, "প্রধান মেনু:")
        return

    # প্রধান মেনু বাটন হ্যান্ডলিং
    if text == "💰 ব্যালেন্স":
        balance = user["balance"]
        ref_income = user.get("ref_income", 0.0)
        completed = user["completed_tasks"]
        pending = user["pending_tasks"]
        
        reply_text = (
            f"👤 **আপনার একাউন্ট ব্যালেন্স:**\n\n"
            f"🟢 ব্যালেন্স: {balance:.2f} BDT\n"
            f"👥 রেফারেল ইনকাম: {ref_income:.2f} BDT\n\n"
            f"✅ সম্পন্ন কাজ: {completed} টি\n"
            f"🔄 রিভিউতে আছে: {pending} টি"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎁 REFER AND EARN", callback_data="refer_info"))
        bot.send_message(chat_id, reply_text, parse_mode="Markdown", reply_markup=markup)

    elif text == "💼 কাজ":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"Facebook কাজ ({price_text})", callback_data="fb_task"))
        bot.send_message(chat_id, "✏️ যেকোনো একটি কাজ সিলেক্ট করুন নিচে:", reply_markup=markup)

    elif text == "📤 উত্তোলন":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("বিকাশ -> সর্বনিম্ন ১০০টাকা (৫ টাকা চার্জ)", callback_data="withdraw_bkash"))
        markup.add(types.InlineKeyboardButton("নগদ -> সর্বনিম্ন ১০০টাকা (৫ টাকা চার্জ)", callback_data="withdraw_nagad"))
        bot.send_message(chat_id, "💰 টাকা তোলার মাধ্যম সিলেক্ট করুন:", reply_markup=markup)

    elif text == "📌 সাপোর্ট":
        support_text = (
            "👤 **গ্রাহক সেবা কেন্দ্র**\n\n"
            "সম্মানিত মেম্বার,\n"
            "আপনার যেকোনো সমস্যা বা জিজ্ঞাসার জন্য আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন। we are online 24 hours.\n\n"
            "👷‍♂️ **অ্যাডমিন সাপোর্ট:** অ্যাডমিনের সাথে সরাসরি কথা বলতে চাইলে আপনাকে বট থেকে সর্বনিম্ন ৫০০ টাকা ইনকাম করতে হবে।\n\n"
            "🆙 **আপডেট:** নিয়মিত কাজের আপডেট পেতে নিচের লিংকে ক্লিক করে আমাদের অফিসিয়াল চ্যানেলে জয়েন থাকুন।"
        )
        support_markup = types.InlineKeyboardMarkup()
        support_markup.add(types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url="https://t.me/R4_Work_Sapait"))
        
        bot.send_message(chat_id, support_text, parse_mode="Markdown", reply_markup=support_markup)


# ---------------- CALLBACK QUERY HANDLER ----------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    user = get_user(user_id)
    current_pass = get_global_setting("current_password", "Sakil@31")
    task_price = get_global_setting("task_price", 5.00)
    price_text = f"{task_price:.2f} BDT"

    if data == "refer_info":
        ref_count = user["ref_count"]
        ref_income = user.get("ref_income", 0.0)
        bot_username = bot.get_me().username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"
        
        text = (
            f"🎁 **REFER AND EARN** 💵\n\n"
            f"👥 **TOTAL REFERS:** {ref_count}\n"
            f"💲 **TOTAL REFER INCOME:** {ref_income:.2f} BDT\n\n"
            f"🔗 **আপনার রেফার লিংক:**\n`{ref_link}`\n\n"
            f"💰 **আপনার রেফার করা ব্যক্তি যত টাকা ইনকাম করবে, আপনি তার ৫% কমিশন পাবেন।**"
        )
        bot.send_message(chat_id, text, parse_mode="Markdown")

    elif data == "fb_task":
        update_user(user_id, {"state": "waiting_for_uid", "task_password": current_pass})
        
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_markup.add(types.KeyboardButton("❌ বাতিল"))

        task_msg = f"🔵 **Facebook Account Creation Info (মূল্য: {price_text}):**\n\n✔ Password : `{current_pass}`\n\n💬 একাউন্ট তৈরি করা হয়ে গেলে, আপনার সঠিক Facebook User ID (UID) লিখে পাঠান:"
        bot.send_message(chat_id, task_msg, parse_mode="Markdown", reply_markup=cancel_markup)

    elif data in ["withdraw_bkash", "withdraw_nagad"]:
        method = "বিকাশ" if "bkash" in data else "নগদ"
        balance = user["balance"]
        
        if balance < MIN_WITHDRAW:
            bot.answer_callback_query(call.id, "আপনার পর্যাপ্ত ব্যালেন্স নেই!", show_alert=True)
            bot.send_message(chat_id, f"❌ আপনার ব্যালেন্স পর্যাপ্ত নয়! {method} মিনিমাম উইথড্র {MIN_WITHDRAW} BDT")
        else:
            update_user(user_id, {"state": "waiting_for_withdraw_number", "withdraw_method": method})
            cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
            bot.send_message(chat_id, f"আপনার {method} পার্সোনাল নম্বরটি দিন:", reply_markup=cancel_markup)

    # কাজ অ্যাপ্রুভ করার লজিক (অ্যাডমিন)
    elif data.startswith("approve_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[1])
        amount = float(parts[2])
        
        target_user = users_collection.find_one({"user_id": target_user_id})
        if target_user:
            new_pending = max(0, target_user["pending_tasks"] - 1)
            users_collection.update_one(
                {"user_id": target_user_id}, 
                {
                    "$inc": {"balance": amount, "completed_tasks": 1},
                    "$set": {"pending_tasks": new_pending}
                }
            )
            
            bot.send_message(target_user_id, f"🎉 আপনার কাজটি সঠিক বলে গৃহীত হয়েছে! আপনার ব্যালেন্সে {amount} টাকা যোগ করা হয়েছে।")
            
            # ৫% রেফারেল কমিশন এবং টোটাল রেফার ইনকাম আপডেট লজিক
            referrer_id = target_user.get("referred_by")
            if referrer_id:
                referrer_user = users_collection.find_one({"user_id": referrer_id})
                if referrer_user:
                    commission = round(amount * 0.05, 2)  
                    users_collection.update_one(
                        {"user_id": referrer_id},
                        {
                            "$inc": {"balance": commission, "ref_income": commission}
                        }
                    )
                    
                    notif_text = f"🎁 আপনার রেফার করা একজন ইউজারের সঠিক কাজের জন্য আপনি ({commission:.2f} টাকা) রেফার কমিশন পেয়েছেন!"
                    try:
                        bot.send_message(referrer_id, notif_text)
                    except Exception:
                        pass

            bot.edit_message_text("✅ কাজ সফলভাবে অ্যাপ্রুভ করা হয়েছে!", chat_id, call.message.message_id)

    # কাজ রিজেক্ট করার লজিক (অ্যাডমিন)
    elif data.startswith("reject_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[1])
        rejected_uid = parts[2] if len(parts) > 2 else "N/A"
        
        target_user = users_collection.find_one({"user_id": target_user_id})
        if target_user:
            new_pending = max(0, target_user["pending_tasks"] - 1)
            users_collection.update_one({"user_id": target_user_id}, {"$set": {"pending_tasks": new_pending}})
            
            bot.send_message(target_user_id, f"❌ আপনার ফেসবুক UID: `{rejected_uid}` সমেত কাজটি ভুল বা নিয়ম অনুযায়ী হয়নি বিধায় রিজেক্ট করা হয়েছে।", parse_mode="Markdown")
            bot.edit_message_text("❌ কাজ রিজেক্ট করা হয়েছে।", chat_id, call.message.message_id)

    # অ্যাডমিন যখন 'পেমেন্ট সফল হয়েছে' বাটনে ক্লিক করবেন
    elif data.startswith("paid_") and user_id == ADMIN_ID:
        parts = data.split("_")
        target_user_id = int(parts[1])
        amount = float(parts[2])
        method = parts[3] if len(parts) > 3 else "বিকাশ/নগদ"
        
        target_user = users_collection.find_one({"user_id": target_user_id})
        if target_user:
            remaining_balance = target_user.get("balance", 0.0)
            
            user_msg = (
                f"🎉 **অভিনন্দন! আপনার উইথড্র রিকোয়েস্ট সফল হয়েছে।**\n\n"
                f"💵 **পরিমাণ:** {amount:.2f} BDT\n"
                f"💼 **মাধ্যম:** {method}\n"
                f"✅ আপনার দেওয়া নম্বরে পেমেন্ট সফলভাবে পাঠিয়ে দেওয়া হয়েছে। চেক করুন!\n\n"
                f"💳 বর্তমান অবশিষ্ট ব্যালেন্স: *{remaining_balance:.2f} BDT*"
            )
            try:
                bot.send_message(target_user_id, user_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Error sending message to user: {e}")

            try:
                bot.edit_message_text(
                    f"✅ সফলভাবে পেমেন্ট পরিশোধ করা হয়েছে বলে মার্ক করা হয়েছে।\n👤 ইউজার ID: `{target_user_id}` | পরিমাণ: {amount:.2f} BDT ({method})",
                    chat_id,
                    call.message.message_id,
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Error updating admin message: {e}")


if __name__ == "__main__":
    keep_alive()  # ফ্লাস্ক সার্ভার ব্যাকগ্রাউন্ডে চালু করা
    print("Bot is running with MongoDB & Flask...")
    bot.infinity_polling()
