import telebot
from telebot import types
import sqlite3
import os

# Настройки
BOT_TOKEN = '7282657185:AAELl9sSiawKcC_MsrssuvGD9dmztiZoj1k'  # Замените на ваш токен
ADMIN_ID = 1200223081  # Замените на ваш Telegram ID

bot = telebot.TeleBot(BOT_TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('uc_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
CREATE TABLE IF NOT EXISTS uc_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    uc_amount INTEGER NOT NULL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    uc_amount INTEGER NOT NULL,
    payment_method TEXT NOT NULL,
    screenshot TEXT,
    status TEXT DEFAULT 'pending'
)
''')
conn.commit()

# Команда /start с фото и меню
@bot.message_handler(commands=['start'])
def start(message):
    with open('navigation_photo.jpg', 'rb') as photo:
        bot.send_photo(message.chat.id, photo, caption="Добрый день! 🎉\n\nВыберите действие:", reply_markup=generate_main_menu())

# Генерация главного меню
def generate_main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("ПРОФИЛЬ 👑", callback_data='profile'))
    markup.add(types.InlineKeyboardButton("КУПИТЬ UC 🔥", callback_data='buy_uc'))
    markup.add(types.InlineKeyboardButton("СТАТИСТИКА 📈", callback_data='statistics'))
    markup.add(types.InlineKeyboardButton("РЕФЕРАЛЬНАЯ СИСТЕМА 🎁", callback_data='referral'))
    markup.add(types.InlineKeyboardButton("ТЕХ. ПОДД... ☎️", callback_data='support'))
    markup.add(types.InlineKeyboardButton("ОТЗЫВЫ 🌱", callback_data='reviews'))
    return markup

# Выбор "Купить UC"
@bot.callback_query_handler(func=lambda call: call.data == 'buy_uc')
def buy_uc(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("60 UC", callback_data='uc_60'))
    markup.add(types.InlineKeyboardButton("325 UC", callback_data='uc_325'))
    markup.add(types.InlineKeyboardButton("660 UC", callback_data='uc_660'))
    markup.add(types.InlineKeyboardButton("1800 UC", callback_data='uc_1800'))
    bot.send_message(call.message.chat.id, "Выберите количество UC:", reply_markup=markup)

# Выбор количества UC
@bot.callback_query_handler(func=lambda call: call.data.startswith('uc_'))
def select_payment_method(call):
    uc_amount = int(call.data.split('_')[1])
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Сбербанк", callback_data=f'pay_sber_{uc_amount}'))
    markup.add(types.InlineKeyboardButton("Тинькофф", callback_data=f'pay_tinkoff_{uc_amount}'))
    markup.add(types.InlineKeyboardButton("Озон Банк", callback_data=f'pay_ozon_{uc_amount}'))
    bot.send_message(call.message.chat.id, "Выберите способ оплаты:", reply_markup=markup)

# Инструкции по оплате
@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_'))
def instruct_payment(call):
    parts = call.data.split('_')
    payment_method = parts[1]
    uc_amount = int(parts[2])
    payment_details = {
        'sber': 'Реквизиты Сбербанка: [укажите ваши реквизиты]',
        'tinkoff': 'Реквизиты Тинькофф: [укажите ваши реквизиты]',
        'ozon': 'Реквизиты Озон Банка: [укажите ваши реквизиты]'
    }
    bot.send_message(call.message.chat.id, f"Переведите средства по реквизитам:\n{payment_details[payment_method]}\n\nПосле оплаты отправьте скриншот.")
    cursor.execute('INSERT INTO transactions (user_id, uc_amount, payment_method) VALUES (?, ?, ?)', (call.from_user.id, uc_amount, payment_method))
    conn.commit()

# Обработка скриншота
@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    cursor.execute('SELECT id FROM transactions WHERE user_id = ? AND status = "pending" ORDER BY id DESC LIMIT 1', (message.from_user.id,))
    transaction = cursor.fetchone()
    if transaction:
        transaction_id = transaction[0]
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        screenshot_path = f'screenshots/{transaction_id}.jpg'
        with open(screenshot_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        cursor.execute('UPDATE transactions SET screenshot = ? WHERE id = ?', (screenshot_path, transaction_id))
        conn.commit()
        bot.send_message(message.chat.id, "Скриншот получен. Ожидайте подтверждения.")
    else:
        bot.send_message(message.chat.id, "Нет активных транзакций.")

# Админ: загрузка кодов
@bot.message_handler(commands=['upload_codes'])
def upload_codes(message):
    if message.from_user.id == ADMIN_ID:
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(message.chat.id, "Использование: /upload_codes <uc_amount> <code1> <code2> ...")
            return
        uc_amount = int(parts[1])
        codes = parts[2:]
        for code in codes:
            cursor.execute('INSERT INTO uc_codes (code, uc_amount) VALUES (?, ?)', (code, uc_amount))
        conn.commit()
        bot.send_message(message.chat.id, f"Загружено {len(codes)} кодов для {uc_amount} UC.")
    else:
        bot.send_message(message.chat.id, "У вас нет прав для загрузки кодов.")

# Админ: просмотр ожидающих транзакций
@bot.message_handler(commands=['pending_transactions'])
def pending_transactions(message):
    if message.from_user.id == ADMIN_ID:
        cursor.execute('SELECT id, user_id, uc_amount, payment_method, screenshot FROM transactions WHERE status = "pending"')
        transactions = cursor.fetchall()
        if not transactions:
            bot.send_message(message.chat.id, "Нет ожидающих транзакций.")
            return
        for trans in transactions:
            trans_id, user_id, uc_amount, payment_method, screenshot = trans
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("Подтвердить", callback_data=f'confirm_{trans_id}'))
            markup.add(types.InlineKeyboardButton("Отменить", callback_data=f'cancel_{trans_id}'))
            msg = f"Транзакция {trans_id}: Пользователь {user_id}, {uc_amount} UC, {payment_method}"
            if screenshot:
                with open(screenshot, 'rb') as photo:
                    bot.send_photo(message.chat.id, photo, caption=msg, reply_markup=markup)
            else:
                bot.send_message(message.chat.id, msg, reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "У вас нет прав.")

# Админ: обработка действий с транзакциями
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_') or call.data.startswith('cancel_'))
def handle_transaction_action(call):
    if call.from_user.id == ADMIN_ID:
        action, trans_id = call.data.split('_')
        trans_id = int(trans_id)
        cursor.execute('SELECT user_id, uc_amount FROM transactions WHERE id = ?', (trans_id,))
        trans_data = cursor.fetchone()
        if not trans_data:
            bot.send_message(call.message.chat.id, "Транзакция не найдена.")
            return
        user_id, uc_amount = trans_data

        if action == 'confirm':
            cursor.execute('SELECT code FROM uc_codes WHERE uc_amount = ? LIMIT 1', (uc_amount,))
            code = cursor.fetchone()
            if code:
                code = code[0]
                bot.send_message(user_id, f"Ваш код для {uc_amount} UC: {code}\nАктивируйте его на сайте игры.")
                cursor.execute('DELETE FROM uc_codes WHERE code = ?', (code,))
                cursor.execute('UPDATE transactions SET status = "confirmed" WHERE id = ?', (trans_id,))
            else:
                bot.send_message(call.message.chat.id, f"Нет доступных кодов для {uc_amount} UC.")
                return
        elif action == 'cancel':
            cursor.execute('UPDATE transactions SET status = "cancelled" WHERE id = ?', (trans_id,))
            bot.send_message(user_id, "Ваша транзакция была отменена.")

        conn.commit()
        bot.send_message(call.message.chat.id, f"Транзакция {trans_id} {'подтверждена' if action == 'confirm' else 'отменена'}.")
    else:
        bot.send_message(call.message.chat.id, "У вас нет прав.")

# Запуск бота
if __name__ == "__main__":
    if not os.path.exists('screenshots'):
        os.makedirs('screenshots')
    bot.polling(none_stop=True)
