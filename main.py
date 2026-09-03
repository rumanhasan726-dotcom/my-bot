import os
import threading
from flask import Flask
from pymongo import MongoClient
import telebot
from telebot import types
import re

# -------------------- CONFIGURATION --------------------
TOKEN = os.environ.get('BOT_TOKEN', '8965009856:AAEBsRHiuXA-jUGXMZLXika2mt2rsLdlcus')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb+srv://rumanhasan726_db_user:sakil1234@cluster0.dacgq2fngtc73ds8c6fg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')

bot = telebot.TeleBot(TOKEN)

# -------------------- MONGODB SETUP --------------------
client = MongoClient(MONGO_URL)
db = client['telegram_earning_bot_db']
users_collection = db['users']
globals_collection = db['globals']
submitted_uids_collection = db['submitted_uids']
withdraw_requests_collection = db['withdraw_requests']

ADMIN_ID = 8449043852  # আপনার অ্যাডমিন আইডি

# টেম্পোরারি স্টেট স্টোর করার জন্য ডিকশনারি
user_states = {}

# ডিফল্ট সেটিংস ফাংশন
def get_global_setting(key, default_val):
    res = globals_collection.find_one({"key": key})
    if res:
        return res["value"]
    globals_collection.insert_one({"key": key, "value": default_val})
    return default_val

def set_global_setting(key, value):
    globals_collection.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

# ডিফল্ট ডেটা সেটআপ
get_global_setting('min_withdraw', 50)
get_global_setting('per_ref_bonus', 5)
get_global_setting('per_task_bonus', 10)
get_global_setting('channel_link', 'https://t.me/your_channel')

# -------------------- BOT HANDLERS --------------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    
    args = message.text.split()
    referred_by = None
    if len(args) > 1:
        try:
            referred_by = int(args[1])
        except ValueError:
            pass

    user = users_collection.find_one({"user_id": user_id})
    if not user:
        users_collection.insert_one({
            "user_id": user_id,
            "name": name,
            "balance": 0.0,
            "ref_count": 0,
            "referred_by": referred_by
        })
        if referred_by and referred_by != user_id:
            ref_user = users_collection.find_one({"user_id": referred_by})
            if ref_user:
                bonus = get_global_setting('per_ref_bonus', 5)
                users_collection.update_one({"user_id": referred_by}, {"$inc": {"balance": bonus, "ref_count": 1}})
                try:
                    bot.send_message(referred_by, f"🎉 অভিনন্দন! আপনার রেফার লিংকের মাধ্যমে একজন নতুন ইউজার জয়েন করেছে। আপনি বোনাস পেয়েছেন: {bonus} টাকা।")
                except:
                    pass

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('💰 আমার ব্যালেন্স', '👥 রেফার করুন')
    markup.row('📝 কাজ করুন', '💳 উইথড্র করুন')
    markup.row('ℹ️ হেল্প ও নিয়ম')

    if user_id == ADMIN_ID:
        markup.row('👑অ্যাডমিন প্যানেল')

    bot.send_message(message.chat.id, f"স্বাগতম {name}!\nআমাদের আর্নিং বটে আপনাকে স্বাগতম। নিচের মেনু থেকে কাজ শুরু করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "submit_task":
        user_states[user_id] = "waiting_for_uid"
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📝 দয়া করে আপনার গেম/টেলিগ্রাম UID এখানে লিখে পাঠান:")

    elif call.data.startswith("approve_"):
        if user_id != ADMIN_ID:
            return
        target_uid = int(call.data.split("_")[1])
        bonus = get_global_setting('per_task_bonus', 10)
        
        users_collection.update_one({"user_id": target_uid}, {"$inc": {"balance": bonus}})
        bot.answer_callback_query(call.id, "টাস্ক অ্যাপ্রুভ করা হয়েছে!")
        bot.edit_message_text(f"✅ টাস্কটি অ্যাপ্রুভ করা হয়েছে। ইউজারকে {bonus} টাকা প্রদান করা হয়েছে।", call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(target_uid, f"🎉 অভিনন্দন! আপনার টাস্কটি অ্যাডমিন কর্তৃক গৃহিত হয়েছে। আপনি পেয়েছেন: {bonus} টাকা।")
        except:
            pass

    elif call.data.startswith("reject_"):
        if user_id != ADMIN_ID:
            return
        target_uid = int(call.data.split("_")[1])
        bot.answer_callback_query(call.id, "টাস্ক রিজেক্ট করা হয়েছে।")
        bot.edit_message_text("❌ টাস্কটি রিজেক্ট করা হয়েছে।", call.message.chat.id, call.message.message_id)
        try:
            bot.send_message(target_uid, "❌ দুঃখিত! আপনার টাস্কের তথ্য সঠিক না থাকায় এটি রিজেক্ট করা হয়েছে।")
        except:
            pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text
    user_id = message.from_user.id
    user = users_collection.find_one({"user_id": user_id})

    if not user and text != '/start':
        bot.send_message(message.chat.id, "দয়া করে প্রথমে /start কমান্ড দিন।")
        return

    # UID সাবমিট করার প্রসেস
    if user_id in user_states and user_states[user_id] == "waiting_for_uid":
        del user_states[user_id]
        
        # অ্যাডমিনকে নোটিফিকেশন পাঠানো
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ অ্যাপ্রুভ", callback_data=f"approve_{user_id}"),
            types.InlineKeyboardButton("❌ রিজেক্ট", callback_data=f"reject_{user_id}")
        )
        
        bot.send_message(ADMIN_ID, f"🔔 নতুন কাজ জমা পড়েছে!\n\n👤 ইউজার আইডি: `{user_id}`\n📝 UID/তথ্য: {text}", parse_mode="Markdown", reply_markup=markup)
        bot.send_message(message.chat.id, "✅ আপনার UID সফলভাবে জমা হয়েছে। অ্যাডমিন চেক করে ব্যালেন্স যুক্ত করে দেবেন।")
        return

    if text == '💰 আমার ব্যালেন্স':
        bal = user.get('balance', 0.0)
        refs = user.get('ref_count', 0)
        bot.send_message(message.chat.id, f"👤 ইউজার আইডি: `{user_id}`\n💵 বর্তমান ব্যালেন্স: {bal} টাকা\n👥 মোট রেফার: {refs} জন", parse_mode="Markdown")

    elif text == '👥 রেফার করুন':
        bot_info = bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start={user_id}"
        per_ref = get_global_setting('per_ref_bonus', 5)
        bot.send_message(message.chat.id, f"🔗 আপনার রেফার লিংক:\n`{ref_link}`\n\nপ্রতি রেফারে আপনি পাবেন: {per_ref} টাকা!", parse_mode="Markdown")

    elif text == '📝 কাজ করুন':
        channel = get_global_setting('channel_link', 'https://t.me/your_channel')
        bonus = get_global_setting('per_task_bonus', 10)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 চ্যানেল ভিজিট করুন", url=channel))
        markup.add(types.InlineKeyboardButton("✅ কাজ জমা দিন (UID দিন)", callback_data="submit_task"))
        bot.send_message(message.chat.id, f"নিয়ম:\n১. নিচের লিংকে ক্লিক করে আমাদের চ্যানেলে জয়েন করুন।\n২. কাজ শেষ করে নিচে 'কাজ জমা দিন' বাটনে ক্লিক করে আপনার গেম/টেলিগ্রাম UID দিন।\n\nপ্রতি টাস্ক বোনাস: {bonus} টাকা", reply_markup=markup)

    elif text == '💳 উইথড্র করুন':
        min_w = get_global_setting('min_withdraw', 50)
        bal = user.get('balance', 0.0)
        if bal < min_w:
            bot.send_message(message.chat.id, f"❌ আপনার পর্যাপ্ত ব্যালেন্স নেই!\nন্যূনতম উইথড্র পরিমাণ: {min_w} টাকা। আপনার আছে: {bal} টাকা।")
        else:
            bot.send_message(message.chat.id, "দয়া করে আপনার বিকাশ/নগদ নম্বর এবং অ্যামাউন্ট লিখে পাঠান। যেমন: `017XXXXXXXX 50`", parse_mode="Markdown")

    elif text == 'ℹ️ হেল্প ও নিয়ম':
        bot.send_message(message.chat.id, "যেকোনো সমস্যায় অ্যাডমিনের সাথে যোগাযোগ করুন। সঠিক নিয়মে কাজ করলে ১০০% পেমেন্ট পাবেন।")

    elif text == '👑অ্যাডমিন প্যানেল' and user_id == ADMIN_ID:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('📊 মোট ইউজার', '📢 ব্রডকাস্ট মেসেজ')
        markup.row('⚙️ সেটিংস পরিবর্তন', '🔙 মেইন মেনু')
        bot.send_message(message.chat.id, "অ্যাডমিন প্যানেলে স্বাগতম:", reply_markup=markup)

    elif text == '📊 মোট ইউজার' and user_id == ADMIN_ID:
        count = users_collection.count_documents({})
        bot.send_message(message.chat.id, f"👥 মোট রেজিস্টার্ড ইউজার: {count} জন")

    elif text == '🔙 মেইন মেনু':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('💰 আমার ব্যালেন্স', '👥 রেফার করুন')
        markup.row('📝 কাজ করুন', '💳 উইথড্র করুন')
        markup.row('ℹ️ হেল্প ও নিয়ম')
        if user_id == ADMIN_ID:
            markup.row('👑অ্যাডমিন প্যানেল')
        bot.send_message(message.chat.id, "মেইন মেনুতে ফিরে এসেছেন।", reply_markup=markup)

# -------------------- FLASK SERVER FOR RENDER --------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is running smoothly!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
