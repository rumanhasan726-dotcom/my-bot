from flask import Flask
import os
import re
import json
import telebot
from telebot import types
import threading

# ---------------- CONFIGURATION ----------------
TOKEN = "8965009856:AAGhnMhMFcKOogNC_Hepq7ZlPamuKJ2vHWw"
bot = telebot.TeleBot(TOKEN)

DATA_FILE = "users.json"

# ইউজার ডেটা লোড করার ফাংশন
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                data = json.loads(content)
                # স্ট্রিং কি (key)-গুলোকে ইন্টিজার (integer) ইউজার আইডিতে রূপান্তর করা
                return {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"Error loading data: {e}")
            return {}
    return {}

# ইউজার ডেটা সেভ করার ফাংশন
def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")

users = load_data()
submitted_uids = set()

ADMIN_ID = 8449043852  # আপনার অ্যাডমিন আইডি

# ফোর্স সাবস্ক্রিপশন চ্যানেল ইউজারনেম ও লিংক
FORCE_CHANNEL_USERNAME = "@R4_Work_Sapait"
FORCE_CHANNEL_LINK = "https://t.me/R4_Work_Sapait"

# ডিফল্ট সেটিংস
CURRENT_PASSWORD = "Sakil@31"
TASK_PRICE = 5.00
PRICE_TEXT = "5.00 BDT"
WITHDRAW_FEE = 5.00  # উইথড্র চার্জ (৫ টাকা)
MIN_WITHDRAW = 100.0  # সর্বনিম্ন উত্তোলন পরিমাণ


# ---------------- FLASK SERVER (RENDER PORT FIX) ----------------
app = Flask(__name__)


@app.route("/")
def home():
  return "Bot is running with JSON File Database!"


def run_flask():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


# ---------------- CHECK MEMBERSHIP FUNCTION ----------------
def check_user_subscription(user_id):
  try:
    member = bot.get_chat_member(FORCE_CHANNEL_USERNAME, user_id)
    if member.status in ["member", "administrator", "creator"]:
      return True
  except Exception as e:
    print(f"Subscription check error: {e}")
  return False


# হেল্পার ফাংশন: ইউজারের ডেটা ফেচ বা ক্রিয়েট করার জন্য
def get_user_data(user_id):
  global users
  if user_id not in users:
    users[user_id] = {
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
        "withdraw_phone": "",
    }
    save_data(users)
  return users[user_id]


def update_user_data(user_id, update_dict):
  global users
  if user_id not in users:
    get_user_data(user_id)
  for key, value in update_dict.items():
    users[user_id][key] = value
  save_data(users)


# ---------------- START COMMAND & MAIN MENU ----------------
@bot.message_handler(commands=["start"])
def send_welcome(message):
  global users
  user_id = message.from_user.id
  args = message.text.split()

  if user_id not in users:
    users[user_id] = {
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
        "withdraw_phone": "",
    }
    
    if len(args) > 1:
      try:
        ref_id = int(args[1])
        if ref_id != user_id and ref_id in users:
          users[user_id]["referred_by"] = ref_id
          users[ref_id]["ref_count"] = users[ref_id].get("ref_count", 0) + 1
      except ValueError:
        pass
    save_data(users)

  # ফোর্স সাবস্ক্রিপশন চেক করা (শুধু অফিসিয়াল চ্যানেল)
  if not check_user_subscription(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK)
    )
    markup.add(
        types.InlineKeyboardButton("✅ Verify (চেক করুন)", callback_data="verify_sub")
    )
    
    start_text = (
        "🤖 *স্বাগতম! এই বটে ছোট ছোট টাস্ক কমপ্লিট করেই আয় করা যায় - সহজ, দ্রুত, রিয়েল ইনকাম 💵*\n\n"
        "👉 *শুরু করতে নিচের চ্যানেলে জয়েন করুন, তারপর Verify চাপুন। 🤩*"
    )
    bot.send_message(
        message.chat.id,
        start_text,
        parse_mode="Markdown",
        reply_markup=markup,
    )
    return

  main_menu(message.chat.id, "✨ *প্রধান মেনু:*")


def main_menu(chat_id, text_msg):
  update_user_data(chat_id, {"state": None})

  markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
  btn_balance = types.KeyboardButton("💰 ব্যালেন্স")
  btn_work = types.KeyboardButton("💼 কাজ")
  btn_withdraw = types.KeyboardButton("📤 উত্তোলন")
  btn_support = types.KeyboardButton("📌 সাপোর্ট")
  markup.add(btn_balance, btn_work, btn_withdraw, btn_support)

  bot.send_message(chat_id, text_msg, parse_mode="Markdown", reply_markup=markup)


# ---------------- MAIN MESSAGE & ADMIN COMMAND HANDLER ----------------
@bot.message_handler(
    func=lambda message: True, content_types=["text", "audio", "voice"]
)
def handle_message(message):
  global CURRENT_PASSWORD, TASK_PRICE, PRICE_TEXT, users
  chat_id = message.chat.id
  user_id = message.from_user.id

  get_user_data(user_id)

  if not check_user_subscription(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK)
    )
    markup.add(
        types.InlineKeyboardButton("✅ Verify (চেক করুন)", callback_data="verify_sub")
    )
    bot.send_message(
        chat_id,
        "⚠️ *বট ব্যবহার করতে হলে অবশ্যই নিচের চ্যানেলে জয়েন করতে হবে!*\nদয়া করে আগে জয়েন করুন।",
        parse_mode="Markdown",
        reply_markup=markup,
    )
    return

  # পাসওয়ার্ড পরিবর্তনের কমান্ড (শুধু অ্যাডমিন)
  if user_id == ADMIN_ID and message.content_type == "text":
    text = message.text.strip()
    if text.startswith("/setpass "):
      new_pass = text.replace("/setpass ", "").strip()
      if new_pass:
        CURRENT_PASSWORD = new_pass
        bot.send_message(
            chat_id,
            f"✅ *সফলভাবে ফেসবুক কাজের পাসওয়ার্ড পরিবর্তন করা হয়েছে!*\nনতুন পাসওয়ার্ড:"
            f" `{CURRENT_PASSWORD}`",
            parse_mode="Markdown",
        )
      else:
        bot.send_message(
            chat_id,
            "⚠️ *দয়া করে পাসওয়ার্ড সহ লিখুন। যেমন:* `/setpass Abc@1234`",
            parse_mode="Markdown",
        )
      return

    if text.startswith("/setprice "):
      new_price_str = text.replace("/setprice ", "").strip()
      try:
        TASK_PRICE = float(new_price_str)
        PRICE_TEXT = f"{TASK_PRICE:.2f} BDT"
        bot.send_message(
            chat_id,
            f"✅ *সফলভাবে ফেসবুক কাজের প্রাইস পরিবর্তন করা হয়েছে!*\nনতুন প্রাইস:"
            f" `{PRICE_TEXT}`",
            parse_mode="Markdown",
        )
      except ValueError:
        bot.send_message(
            chat_id,
            "⚠️ *সঠিক সংখ্যা দিয়ে প্রাইস লিখুন। যেমন:* `/setprice 6` অথবা"
            " `/setprice 5.50`",
            parse_mode="Markdown",
        )
      return

    if text.startswith("/notice "):
      notice_text = text.replace("/notice ", "").strip()
      if notice_text:
        success_count = 0
        fail_count = 0
        for uid_key in users:
          try:
            bot.send_message(
                int(uid_key),
                f"📢 *বিশেষ ঘোষণা / নোটিশ*\n\n{notice_text}",
                parse_mode="Markdown",
            )
            success_count += 1
          except Exception:
            fail_count += 1
        bot.send_message(
            chat_id,
            f"✅ *নোটিশ পাঠানো সম্পন্ন!*\nসফলভাবে গেছে: {success_count} জনের"
            f" কাছে\nব্যর্থ হয়েছে: {fail_count} জনের কাছে",
            parse_mode="Markdown",
        )
      else:
        bot.send_message(chat_id, "⚠️ *দয়া করে নোটিশের লেখা সহ দিন।*")
      return

  if user_id == ADMIN_ID and message.content_type in ["audio", "voice"]:
    file_id = (
        message.voice.file_id
        if message.content_type == "voice"
        else message.audio.file_id
    )
    success_count = 0
    fail_count = 0

    for uid_key in users:
      try:
        if message.content_type == "voice":
          bot.send_voice(int(uid_key), file_id, caption="🎙️ *নতুন ভয়েস নোটিশ*")
        else:
          bot.send_audio(int(uid_key), file_id, caption="🎵 *নতুন অডিও নোটিশ*")
        success_count += 1
      except Exception:
        fail_count += 1

    bot.send_message(
        chat_id,
        f"✅ *ভয়েস নোটিশ পাঠানো সম্পন্ন!*\nসফলভাবে গেছে: {success_count} জনের"
        f" কাছে\nব্যর্থ হয়েছে: {fail_count} জনের কাছে",
        parse_mode="Markdown",
    )
    return

  if message.content_type != "text":
    return

  text = message.text.strip()
  user_data = get_user_data(user_id)

  if text == "❌ বাতিল":
    update_user_data(user_id, {"state": None})
    main_menu(
        chat_id,
        "🏢 *আপনাকে প্রধান মেনুতে ফিরিয়ে আনা হয়েছে! কাজ বাতিল করা হয়েছে।*",
    )
    return

  user_state = user_data.get("state")

  # ১. টাস্ক সাবমিশন প্রসেস: UID গ্রহণ
  if user_state == "waiting_for_uid":
    if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
      bot.send_message(
          chat_id,
          "⚠️ *আপনি বর্তমানে কাজের ভেতরে আছেন! কাজ করতে না চাইলে নিচের '❌ বাতিল'"
          " বাটনে চাপুন।*",
          parse_mode="Markdown",
      )
      return

    if user_data.get("task_password") != CURRENT_PASSWORD:
      update_user_data(user_id, {"state": None})
      main_menu(
          chat_id,
          "⚠️ *এই পাসওয়ার্ডের মেয়াদ শেষ বা পরিবর্তিত হয়েছে! দয়া করে '💼 কাজ'"
          " মেনু থেকে নতুন করে কাজ শুরু করুন।*",
      )
      return

    uid = text
    if not uid.isdigit() or len(uid) < 5 or len(uid) > 20:
      bot.send_message(
          chat_id,
          "❌ *এটি কোনো সঠিক ফেসবুক UID নয়! সঠিক ফেসবুক UID দিন অথবা '❌ বাতিল'"
          " বাটনে চাপুন।*",
          parse_mode="Markdown",
      )
      return

    if uid in submitted_uids:
      bot.send_message(
          chat_id, "❌ *এই ফেসবুক UID টি ইতিমধ্যে একবার জমা দেওয়া হয়েছে!*", parse_mode="Markdown"
      )
    else:
      update_user_data(user_id, {"temp_uid": uid, "state": "waiting_for_cookies"})

      cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
      cancel_markup.add(types.KeyboardButton("❌ বাতিল"))

      bot.send_message(
          chat_id,
          "🛡️ *নিচে আপনার অ্যাকাউন্টের কুকিজ পেস্ট করুন 📍*",
          parse_mode="Markdown",
          reply_markup=cancel_markup,
      )
    return

  # ২. টাস্ক সাবমিশন প্রসেস: কুকিজ গ্রহণ
  elif user_state == "waiting_for_cookies":
    if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
      bot.send_message(
          chat_id,
          "⚠️ *কুকিজ দিন অথবা কাজ বাতিল করতে নিচের '❌ বাতিল' বাটনে চাপুন।*",
          parse_mode="Markdown",
      )
      return

    update_user_data(user_id, {"temp_cookies": text, "state": "waiting_for_finish_button"})

    finish_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    finish_markup.add(
        types.KeyboardButton("অ্যাকাউন্ট খোলা শেষ"),
        types.KeyboardButton("❌ বাতিল"),
    )

    bot.send_message(
        chat_id,
        "✅ *অ্যাকাউন্ট খোলা শেষ হলে নিচের বাটনে চাপ দিন:*",
        parse_mode="Markdown",
        reply_markup=finish_markup,
    )
    return

  # ৩. টাস্ক সাবমিশন প্রসেস: অ্যাকাউন্ট খোলা শেষ বাটন
  elif user_state == "waiting_for_finish_button":
    if text == "অ্যাকাউন্ট খোলা শেষ":
      current_data = get_user_data(user_id)
      uid = current_data.get("temp_uid")
      cookies = current_data.get("temp_cookies")

      submitted_uids.add(uid)
      update_user_data(user_id, {"pending_tasks": current_data.get("pending_tasks", 0) + 1, "state": None})

      admin_msg = (
          f"📥 *নতুন কাজ জমা পড়েছে!*\n\n👤 ইউজার আইডি: `{user_id}`\n📌 ফেসবুক"
          f" UID: `{uid}`\n🍪 কুকিজ:\n`{cookies}`\n\n💵 কাজের মূল্য: {PRICE_TEXT}"
      )
      markup = types.InlineKeyboardMarkup()
      markup.add(
          types.InlineKeyboardButton(
              "✅ সঠিক (Approve)",
              callback_data=f"approve_{user_id}_{TASK_PRICE}_{uid}",
          ),
          types.InlineKeyboardButton(
              "❌ ভুল (Reject)", callback_data=f"reject_{user_id}_{uid}"
          ),
      )
      bot.send_message(
          ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=markup
      )

      bot.send_message(chat_id, "🎉 *টাস্ক সফলভাবে জমা হয়েছে!*", parse_mode="Markdown")
      main_menu(
          chat_id,
          "⏳ *আপনার কাজটি রিভিউতে পাঠানো হয়েছে। প্রধান মেনুতে স্বাগতম!*",
      )
    else:
      bot.send_message(
          chat_id,
          "⚠️ *দয়া করে নিচের* **'অ্যাকাউন্ট খোলা শেষ'** *অথবা* **'❌ বাতিল'** *বাটনে"
          " ক্লিক করুন।*",
          parse_mode="Markdown",
      )
    return

  # ৪. উইথড্র স্টেপ ১: সঠিক বিকাশ/নগদ নম্বর ভ্যালিডেশন
  elif user_state == "waiting_for_withdraw_number":
    if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
      bot.send_message(
          chat_id,
          "⚠️ *উইথড্র প্রক্রিয়ায় আছেন! বাতিল করতে চাইলে '❌ বাতিল' বাটনে চাপুন।*",
          parse_mode="Markdown",
      )
      return

    phone = text.strip()
    if not re.match(r"^01[3-9]\d{8}$", phone):
      bot.send_message(
          chat_id,
          "❌ *এটি কোনো সঠিক বিকাশ বা নগদ নম্বর নয়! সঠিক ১১ ডিজিটের নম্বর দিন"
          " (যেমন: 01934546320)।*",
          parse_mode="Markdown",
      )
      return

    update_user_data(user_id, {"withdraw_phone": phone, "state": "waiting_for_withdraw_amount"})

    cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel_markup.add(types.KeyboardButton("❌ বাতিল"))

    bot.send_message(
        chat_id,
        "💰 *আপনি কত টাকা উত্তোলন করতে চান? শুধু সংখ্যায় লিখুন:\nযেমন: ১০০ বা"
        " ২৫০ বা ৫০০*",
        parse_mode="Markdown",
        reply_markup=cancel_markup,
    )
    return

  # ৫. উইথড্র স্টেপ ২: টাকার পরিমাণ গ্রহণ ও যাচাই করা
  elif user_state == "waiting_for_withdraw_amount":
    if text in ["💰 ব্যালেন্স", "💼 কাজ", "📤 উত্তোলন", "📌 সাপোর্ট"]:
      bot.send_message(
          chat_id,
          "⚠️ *উইথড্র প্রক্রিয়ায় আছেন! বাতিল করতে চাইলে '❌ বাতিল' বাটনে চাপুন।*",
          parse_mode="Markdown",
      )
      return

    try:
      amount = float(text)
    except ValueError:
      bot.send_message(
          chat_id,
          "❌ *দয়া করে শুধুমাত্র সংখ্যায় টাকার পরিমাণ লিখুন (যেমন: 100)।*",
          parse_mode="Markdown",
      )
      return

    current_data = get_user_data(user_id)
    balance = current_data["balance"]
    method = current_data.get("withdraw_method", "বিকাশ")
    phone = current_data.get("withdraw_phone", "")

    if amount < MIN_WITHDRAW:
      bot.send_message(
          chat_id,
          f"❌ *সর্বনিম্ন উত্তোলনের পরিমাণ {MIN_WITHDRAW} BDT। আবার সঠিক পরিমাণ"
          " লিখুন:*",
          parse_mode="Markdown",
      )
      return

    if amount > balance:
      bot.send_message(
          chat_id,
          f"❌ *আপনার পর্যাপ্ত ব্যালেন্স নেই! বর্তমান ব্যালেন্স: {balance:.2f}"
          f" BDT\nপুনরায় সঠিক পরিমাণ লিখুন:*",
          parse_mode="Markdown",
      )
      return

    new_balance = balance - amount
    update_user_data(user_id, {"state": None, "balance": new_balance})

    admin_withdraw_msg = (
        f"📤 *নতুন উইথড্র রিকোয়েস্ট!*\n\n👤 ইউজার আইডি: `{user_id}`\n💼 মাধ্যম:"
        f" {method}\n📞 নম্বর/ডিটেইলস: `{phone}`\n💰 উত্তোলনের পরিমাণ: {amount}"
        f" BDT\n✂️ চার্জ কাটা হয়েছে: {WITHDRAW_FEE} BDT"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ সফল হয়েছে (টাকা পাঠানো হয়েছে)",
            callback_data=f"paid_{user_id}_{amount}_{method}",
        )
    )

    bot.send_message(
        ADMIN_ID, admin_withdraw_msg, parse_mode="Markdown", reply_markup=markup
    )

    user_success_msg = (
        f"✅ *আপনার উইথড্র রিকোয়েস্ট সফল হয়েছে!*\n\n💼 *মেথড:*"
        f" {method}\n📱 *Number/Details:* {phone}\n💵 *উত্তোলনের পরিমাণ:*"
        f" {amount:.2f} BDT\n🔄 *অ্যাডমিন প্যানেলে এটি পাঠানো হয়েছে!*\n\n💳"
        f" অবশিষ্ট ব্যালেন্স: *{new_balance:.2f} BDT*"
    )
    bot.send_message(chat_id, user_success_msg, parse_mode="Markdown")
    main_menu(chat_id, "✨ *প্রধান মেনু:*")
    return

  # প্রধান মেনু বাটন হ্যান্ডলিং
  if text == "💰 ব্যালেন্স":
    data = get_user_data(user_id)
    balance = data["balance"]
    ref_income = data.get("ref_income", 0.0)
    completed = data["completed_tasks"]
    pending = data["pending_tasks"]

    reply_text = (
        f"👤 *আপনার একাউন্ট ব্যালেন্স:*\n\n"
        f"🟢 ব্যালেন্স: {balance:.2f} BDT\n"
        f"👥 রেফারেল ইনকাম: {ref_income:.2f} BDT\n\n"
        f"✅ সম্পন্ন কাজ: {completed} টি\n"
        f"🔄 রিভিউতে আছে: {pending} টি"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎁 REFER AND EARN", callback_data="refer_info")
    )
    bot.send_message(
        chat_id, reply_text, parse_mode="Markdown", reply_markup=markup
    )

  elif text == "💼 কাজ":
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            f"Facebook কাজ ({PRICE_TEXT})", callback_data="fb_task"
        )
    )
    work_text = "✏️ *যেকোনো একটি কাজ সিলেক্ট করুন নিচে:*\n👇"
    bot.send_message(
        chat_id, work_text, parse_mode="Markdown", reply_markup=markup
    )

  elif text == "📤 উত্তোলন":
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "বিকাশ -> সর্বনিম্ন ১০০টাকা (৫ টাকা চার্জ)",
            callback_data="withdraw_bkash",
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            "নগদ -> সর্বনিম্ন ১০০টাকা (৫ টাকা চার্জ)",
            callback_data="withdraw_nagad",
        )
    )
    bot.send_message(chat_id, "💰 *টাকা তোলার মাধ্যম সিলেক্ট করুন:*", parse_mode="Markdown", reply_markup=markup)

  elif text == "📌 সাপোর্ট":
    support_text = (
        "👤 *গ্রাহক সেবা কেন্দ্র*\n\nসম্মানিত মেম্বার,\nআপনার যেকোনো সমস্যা বা"
        " জিজ্ঞাসার জন্য আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন। we are online"
        " 24 hours.\n\n👷‍♂️ *অ্যাডমিন সাপোর্ট:* অ্যাডমিনের সাথে সরাসরি কথা বলতে"
        " চাইলে আপনাকে বট থেকে সর্বনিম্ন ৫০০ টাকা ইনকাম করতে হবে।"
        "\n\n🆙 *আপডেট:* নিয়মিত কাজের আপডেট পেতে নিচের লিংকে ক্লিক করে আমাদের"
        " অফিসিয়াল চ্যানেলে জয়েন থাকুন।"
    )
    support_markup = types.InlineKeyboardMarkup()
    support_markup.add(
        types.InlineKeyboardButton(
            "📢 অফিসিয়াল চ্যানেল", url=FORCE_CHANNEL_LINK
        )
    )

    bot.send_message(
        chat_id, support_text, parse_mode="Markdown", reply_markup=support_markup
    )


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
      bot.answer_callback_query(
          call.id,
          "আপনি এখনো চ্যানেলে জয়েন করেননি! দয়া করে আগে জয়েন করুন.",
          show_alert=True,
      )
    return

  if not check_user_subscription(user_id):
    bot.answer_callback_query(
        call.id,
        "⚠️ কাজ করতে হলে আগে আমাদের চ্যানেলে জয়েন করতে হবে!",
        show_alert=True,
    )
    return

  if data == "refer_info":
    user_data = get_user_data(user_id)
    ref_count = user_data["ref_count"]
    ref_income = user_data.get("ref_income", 0.0)
    ref_link = f"https://t.me/R4_OTP_bot?start={user_id}"

    text = (
        f"🎁 *REFER AND EARN* 💵\n\n👥 *TOTAL REFERS:* {ref_count}\n💲 *TOTAL"
        f" REFER INCOME:* {ref_income:.2f} BDT\n\n🔗 *আপনার রেফার"
        f" লিংক:*\n`{ref_link}`\n\n💰 *আপনার রেফার করা ব্যক্তি যত টাকা ইনকাম"
        " করবে, আপনি তার ৫% কমিশন পাবেন।*"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")

  elif data == "fb_task":
    update_user_data(user_id, {"state": "waiting_for_uid", "task_password": CURRENT_PASSWORD})

    cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cancel_markup.add(types.KeyboardButton("❌ বাতিল"))

    task_msg = (
        f"🔵 *Facebook Account Creation Info (মূল্য: {PRICE_TEXT}):*\n\n✔"
        f" Password : `{CURRENT_PASSWORD}`\n\n💬 *একউন্ট তৈরি করা হয়ে গেলে,"
        " আপনার সঠিক Facebook User ID (UID) লিখে পাঠান:*"
    )
    bot.send_message(
        chat_id, task_msg, parse_mode="Markdown", reply_markup=cancel_markup
    )

  elif data in ["withdraw_bkash", "withdraw_nagad"]:
    method = "বিকাশ" if "bkash" in data else "নগদ"
    user_data = get_user_data(user_id)
    balance = user_data["balance"]

    if balance < MIN_WITHDRAW:
      bot.answer_callback_query(
          call.id, "আপনার পর্যাপ্ত ব্যালেন্স নেই!", show_alert=True
      )
      bot.send_message(
          chat_id,
          f"❌ *আপনার ব্যালেন্স পর্যাপ্ত নয়! {method} মিনিমাম উইথড্র"
          f" {MIN_WITHDRAW} BDT*",
          parse_mode="Markdown",
      )
    else:
      update_user_data(user_id, {"state": "waiting_for_withdraw_number", "withdraw_method": method})
      cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
      cancel_markup.add(types.KeyboardButton("❌ বাতিল"))
      bot.send_message(
          chat_id,
          f"📱 *আপনার {method} পার্সোনাল নম্বরটি দিন:*",
          parse_mode="Markdown",
          reply_markup=cancel_markup,
      )

  # কাজ অ্যাপ্রুভ করার লজিক (অ্যাডমিন)
  elif data.startswith("approve_") and user_id == ADMIN_ID:
    parts = data.split("_")
    target_user_id = int(parts[1])
    amount = float(parts[2])

    target_data = get_user_data(target_user_id)
    if target_data:
      new_bal = target_data["balance"] + amount
      new_completed = target_data["completed_tasks"] + 1
      new_pending = max(0, target_data["pending_tasks"] - 1)
      
      update_user_data(target_user_id, {
          "balance": new_bal,
          "completed_tasks": new_completed,
          "pending_tasks": new_pending
      })

      bot.send_message(
          target_user_id,
          "🎉 *আপনার কাজটি সঠিক বলে গৃহীত হয়েছে! আপনার ব্যালেন্সে"
          f" {amount} টাকা যোগ করা হয়েছে।*",
          parse_mode="Markdown",
      )

      referrer_id = target_data.get("referred_by")
      if referrer_id and referrer_id in users:
        commission = round(amount * 0.05, 2)
        ref_bal = users[referrer_id]["balance"] + commission
        ref_inc = users[referrer_id].get("ref_income", 0.0) + commission
        
        update_user_data(referrer_id, {
            "balance": ref_bal,
            "ref_income": ref_inc
        })

        notif_text = (
            "🎁 *আপনার রেফার করা একজন ইউজারের সঠিক কাজের জন্য আপনি"
            f" ({commission:.2f} টাকা) রেফার কমিশন পেয়েছেন!*"
        )
        try:
          bot.send_message(referrer_id, notif_text, parse_mode="Markdown")
        except Exception:
          pass

      bot.edit_message_text(
          "✅ কাজ সফলভাবে অ্যাপ্রুভ করা হয়েছে!", chat_id, call.message.message_id
      )

  # কাজ রিজেক্ট করার লজিক (অ্যাডমিন)
  elif data.startswith("reject_") and user_id == ADMIN_ID:
    parts = data.split("_")
    target_user_id = int(parts[1])
    rejected_uid = parts[2] if len(parts) > 2 else "N/A"

    target_data = get_user_data(target_user_id)
    if target_data:
      if target_data.get("pending_tasks", 0) > 0:
        update_user_data(target_user_id, {"pending_tasks": target_data["pending_tasks"] - 1})

      bot.send_message(
          target_user_id,
          f"❌ *আপনার ফেসবুক UID:* `{rejected_uid}` *সমেত কাজটি ভুল বা নিয়ম অনুযায়ী"
          " হয়নি বিধায় রিজেক্ট করা হয়েছে।*",
          parse_mode="Markdown",
      )
      bot.edit_message_text(
          "❌ কাজ রিজেক্ট করা হয়েছে।", chat_id, call.message.message_id
      )

  elif data.startswith("paid_") and user_id == ADMIN_ID:
    parts = data.split("_")
    target_user_id = int(parts[1])
    amount = float(parts[2])
    method = parts[3] if len(parts) > 3 else "বিকাশ/নগদ"

    target_data = get_user_data(target_user_id)
    if target_data:
      remaining_balance = target_data.get("balance", 0.0)

      user_msg = (
          f"🎉 *অভিনন্দন! আপনার উইথড্র রিকোয়েস্ট সফল হয়েছে।*\n\n💵 *পরিমাণ:*"
          f" {amount:.2f} BDT\n💼 *মাধ্যম:* {method}\n✅ *আপনার দেওয়া নম্বরে"
          f" পেমেন্ট সফলভাবে পাঠিয়ে দেওয়া হয়েছে। চেক করুন!*\n\n💳 *বর্তমান অবশিষ্ট"
          f" ব্যালেন্স:* *{remaining_balance:.2f} BDT*"
      )
      try:
        bot.send_message(target_user_id, user_msg, parse_mode="Markdown")
      except Exception as e:
        print(f"Error sending message to user: {e}")

      try:
        bot.edit_message_text(
            "✅ *সফলভাবে পেমেন্ট পরিশোধ করা হয়েছে বলে মার্ক করা হয়েছে।* \n👤 ইউজার"
            f" ID: `{target_user_id}` | পরিমাণ: {amount:.2f} BDT ({method})",
            chat_id,
            call.message.message_id,
            parse_mode="Markdown",
        )
      except Exception as e:
        print(f"Error updating admin message: {e}")


# ---------------- MAIN EXECUTION ----------------
if __name__ == "__main__":
  flask_thread = threading.Thread(target=run_flask)
  flask_thread.daemon = True
  flask_thread.start()

  print("Bot and Flask server are running with JSON database...")
  bot.infinity_polling()

