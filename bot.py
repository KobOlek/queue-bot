from telegram import Update, BotCommand, BotCommandScopeDefault, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.ext.filters import MessageFilter

from datetime import datetime, timedelta, time

from config import *
from database import Database
from exception import DatabaseException


class IsRegisteredUserFilter(MessageFilter):
    """ Custom filter: passes messages ONLY if the user is in the database. """
    def filter(self, message):
        if not message.from_user:
            return False
            
        user_id = message.from_user.id

        try:
            with Database(DB_NAME) as db:
                return db.is_user_registered(user_id)
        except DatabaseException:
            return False

# States for ConversationHandler
WAITING_FOR_NAME = 1
SELECTING_QUEUE = 2
TYPING_LAB_NUMBER = 3
SELECTING_POSITION = 4
SELECTING_QUEUE_FOR_LEAVING = 5
SELECTING_QUEUE_TO_REMOVE_USER = 6
SELECTING_USER_TO_REMOVE = 7
SELECTING_QUEUE_TO_CLOSE = 8
SELECTING_QUEUE_TO_SHOW = 9

# User and admin menus
USER_COMMANDS = [
    BotCommand("start", "Почати"),
    BotCommand("show_table", "Показати чергу"),
    BotCommand("get_in_queue", "Увійти в чергу"),
    BotCommand("leave_the_queue", "Покинути чергу")
]

ADMIN_COMMANDS = USER_COMMANDS + [
    BotCommand("close_queue", "Закрити чергу"),
    BotCommand("remove_user", "Видалити юзера з черги"),
    BotCommand("new_queue", "Нова черга"),
    BotCommand("reschedule", "Переназначити чергу"),
    BotCommand("broadcast", "Розіслати повідомлення"),
    BotCommand("toggle_registration", "Увімкнути/вимкнути реєстрацію")
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Command menu for admins
    if user_id in admin_ids:
        await context.bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=user_id))
        await update.message.reply_text("Привіт адміне!")
        return ConversationHandler.END

    try:
        with Database(DB_NAME) as db:
            # Check if registration is enabled
            is_registration_open = db.is_registration_enabled()
            if not is_registration_open:
                await update.message.reply_text("Наразі реєстрація нових користувачів закрита.")
                return ConversationHandler.END

            # Check if user is not already registred
            is_registered = db.is_user_registered(user_id)
            if is_registered:
                await update.message.reply_text("Ти вже зареєстрований! Обирай що робимо далі!")
                return ConversationHandler.END
    except DatabaseException:
        await update.message.reply_text("Помилка реєстрації.")
        return ConversationHandler.END

    if user_id in context.bot_data:
        await update.message.reply_text("Твоя заявка вже розглядається адміністратором. Будь ласка, зачекай.")
        return ConversationHandler.END
    
    await update.message.reply_text("Привіт! Для реєстрації введи своє ім'я та прізвище:")
    return WAITING_FOR_NAME

# Receiving name after registration (/start command)
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.message.text
    username = update.effective_user.username
    if username:
        user_link = f"@{username}"
    else:
        user_link = f"без юзернейму"

    context.bot_data[user_id] = {"name": full_name}

    keyboard = [
        [
            InlineKeyboardButton("✅ Прийняти", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ Відхилити", callback_data=f"reject_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Admin registration handling keyboard
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id, 
                text=f"Нова заявка на реєстрацію!\nІм'я: {full_name}\nUsername: {user_link}",
                reply_markup=reply_markup
            )
        except Exception:
            pass

    # Response for user
    await update.message.reply_text("Твої дані відправлено на перевірку адміністратору. Очікуй!")
    return ConversationHandler.END


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Реєстрацію скасовано.")
    return ConversationHandler.END

# Processing admin registration decision
async def admin_registration_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):    
    query = update.callback_query

    if update.effective_user.id not in admin_ids:
        await query.answer("У вас немає прав!", show_alert=True)
        return
    
    await query.answer()

    # Parsing query data
    action, user_id_str = query.data.split('_')
    target_user_id = int(user_id_str)

    if target_user_id not in context.bot_data:
        await query.edit_message_text("ℹ️ Цю заявку вже було оброблено іншим адміністратором.", reply_markup=None)
        return

    if action == "approve":
        user_info = context.bot_data.get(target_user_id)
        full_name = user_info["name"] if user_info else "Невідомий"
        try:
            with Database(DB_NAME) as db:
                db.register_user(target_user_id, full_name)
        except DatabaseException:
            await query.edit_message_text("❌ Помилка бази даних при додаванні користувача.", reply_markup=None)
            return

        await context.bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeChat(chat_id=target_user_id))
        
        await context.bot.send_message(chat_id=target_user_id, text="Твою заявку схвалено! Меню оновлено, можеш користуватися ботом.")
        await query.edit_message_text(f"✅ Користувача {target_user_id} прийнято.", reply_markup=None)
        
    elif action == "reject":
        await context.bot.send_message(chat_id=target_user_id, text="На жаль, твою заявку було відхилено.")
        await query.edit_message_text(f"❌ Користувача {target_user_id} відхилено.", reply_markup=None)

    if target_user_id in context.bot_data:
        del context.bot_data[target_user_id]
            
        
async def show_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with Database(DB_NAME) as db:
            active_queues = db.get_current_active_queues()
    except DatabaseException:
        await update.message.reply_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    if not active_queues:
        await update.message.reply_text("📭 Зараз немає активних черг.")
        return ConversationHandler.END

    keyboard = []
    for aq in active_queues:
        # aq[0]=id, aq[1]=subject, aq[2]=subgroup, aq[3]=date
        btn_text = f"{aq[1]} (Підгрупа: {aq[2]}) - {aq[3]}"
        btn_data = f"show_q_{aq[0]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

    keyboard.append([InlineKeyboardButton("🔙 Скасувати", callback_data="cancel_show")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Обери чергу для перегляду:",
        reply_markup=reply_markup
    )
    return SELECTING_QUEUE_TO_SHOW

async def queue_to_show_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    schedule_id = int(query.data.replace("show_q_", ""))

    try:
        with Database(DB_NAME) as db:
            schedule_info = db.get_schedule_info(schedule_id)
            queue_data = db.get_queue_for_schedule(schedule_id)
    except DatabaseException:
        await query.edit_message_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    if not schedule_info:
        await query.edit_message_text("❌ Розклад не знайдено.")
        return ConversationHandler.END

    subject, subgroup, defense_date = schedule_info

    text = (
        f"📚 *{subject}*\n"
        f"👥 Підгрупа {subgroup}\n"
        f"📅 Дата захисту: {defense_date}\n\n"
        f"Поточна черга:\n"
    )

    if not queue_data:
        text += "📭 Черга порожня.\n"
        total_students = 0
    else:
        for item in queue_data:
            pos, name, lab = item
            text += f"{pos}. {name} - Лаба {lab}\n"
        total_students = len(queue_data)

    text += f"\n📊 Всього у черзі студентів: {total_students}"

    await query.edit_message_text(text, parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Дію скасовано.")
    else:
        await update.message.reply_text("Дію скасовано.")
    return ConversationHandler.END

async def get_in_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    active_queues = []
    try:
        with Database(DB_NAME) as db:
            active_queues = db.get_current_active_queues()
    except DatabaseException:
        await update.message.reply_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    if not active_queues:
        await update.message.reply_text("Зараз немає активних черг.")
        return ConversationHandler.END

    keyboard = []

    for aq in active_queues:
        # aq[0]=id, aq[1]=subject, aq[2]=subgroup, aq[3]=date
        btn_text = f"{aq[1]} (Підгрупа: {aq[2]}) - {aq[3]}"
        btn_data = f"get_in_{aq[0]}"
        
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

    keyboard.append([InlineKeyboardButton("🔙 Скасувати", callback_data="cancel_queue")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=user_id, 
        text=f"Доступні для запису черги:",
        reply_markup=reply_markup
    )

    return SELECTING_QUEUE

async def queue_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    schedule_id_str = query.data.replace("get_in_", "")
    schedule_id = int(schedule_id_str)

    context.user_data['selected_schedule_id'] = schedule_id

    await query.edit_message_text(
        "✍️ Напиши номер лабораторної роботи, яку будеш здавати (тільки цифру):", 
        reply_markup=None
    )
    
    return TYPING_LAB_NUMBER

async def receive_lab_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lab_text = update.message.text

    if not lab_text.isdigit():
        await update.message.reply_text("Будь ласка, введи коректний номер (тільки цифру):")
        return TYPING_LAB_NUMBER
    
    lab_number = int(lab_text)
    schedule_id = context.user_data.get('selected_schedule_id')

    try:
        with Database(DB_NAME) as db:
            if db.is_same_user_in_queue(user_id, schedule_id, lab_number):
                await update.message.reply_text(f"⚠️ Ти вже стоїш у цій черзі з лабою №{lab_number}!")
                del context.user_data['selected_schedule_id']
                return ConversationHandler.END
            
            taken_positions = db.get_taken_positions(schedule_id)
            
    except DatabaseException:
        await update.message.reply_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    context.user_data['lab_number'] = lab_number

    MAX_POSITIONS = 25
    keyboard = []
    row = []
    
    for i in range(1, MAX_POSITIONS + 1):
        if i in taken_positions:
            row.append(InlineKeyboardButton("❌", callback_data="taken_pos"))
        else:
            row.append(InlineKeyboardButton(str(i), callback_data=f"pos_{i}"))
            
        if len(row) == 5:
            keyboard.append(row)
            row = []

    keyboard.append([InlineKeyboardButton("🔙 Скасувати", callback_data="cancel_queue")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Обери вільне місце в черзі:", 
        reply_markup=reply_markup
    )
    return SELECTING_POSITION

async def position_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    if query.data == "taken_pos":
        await query.answer("Це місце вже зайняте! Обери інше.", show_alert=True)
        return SELECTING_POSITION
        
    if query.data == "cancel_queue":
        await query.answer()
        await query.edit_message_text("Запис у чергу скасовано.")
        context.user_data.clear()
        return ConversationHandler.END

    await query.answer()

    position = int(query.data.replace("pos_", ""))
    
    schedule_id = context.user_data.get('selected_schedule_id')
    lab_number = context.user_data.get('lab_number')
    user_id = update.effective_user.id

    try:
        with Database(DB_NAME) as db:
            if db.is_position_taken(schedule_id, position):
                await query.edit_message_text("Ой! Хтось встиг зайняти це місце швидше за тебе. Спробуй /get_in_queue ще раз.")
                context.user_data.clear()
                return ConversationHandler.END

            db.add_user_to_queue(schedule_id, user_id, lab_number, position)
            
    except DatabaseException:
        await query.edit_message_text("❌ Помилка бази даних при записі.")
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data.clear()

    await query.edit_message_text(f"✅ Успіх! Тебе записано в чергу.\nТвоя позиція: **{position}**", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'selected_schedule_id' in context.user_data:
        del context.user_data['selected_schedule_id']
    await update.message.reply_text("Запис у чергу скасовано.")
    return ConversationHandler.END

async def leave_the_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    try:
        with Database(DB_NAME) as db:
            user_queues = db.get_user_queues(user_id)
    except DatabaseException:
        await update.message.reply_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    if not user_queues:
        await update.message.reply_text("Ви не зареєстровані в жодній черзі!")
        return ConversationHandler.END
    
    keyboard = []

    for q in user_queues:
        # q[0]=id, q[1]=subject, q[2]=subgroup, q[3]=date, q[4]=lab_number, q[5]=position
        btn_text = f"❌ {q[1]} ({q[2]}) - Лаба №{q[4]}, Поз: {q[5]}, {q[3]}"
        btn_data = f"leave_{q[0]}_{q[4]}" 
        
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

    keyboard.append([InlineKeyboardButton("🔙 Скасувати", callback_data="cancel_leave")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Ваші черги (натисніть, щоб покинути):",
        reply_markup=reply_markup
    )

    return SELECTING_QUEUE_FOR_LEAVING

async def queue_for_leaving_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    schedule_id = int(parts[1])
    lab_number = int(parts[2])

    user_id = update.effective_user.id

    try:
        with Database(DB_NAME) as db:
            db.remove_user_from_queue(schedule_id, user_id, lab_number)
    except DatabaseException:
        await query.edit_message_text("❌ Помилка бази даних. Вас не видалено з черги. Спробуйте ще.")
        return ConversationHandler.END
    
    await query.edit_message_text(f"✅ Вас успішно викреслено з черги (Лабораторна №{lab_number})!")
    return ConversationHandler.END

async def cancel_leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Дію скасовано.")
    else:
        await update.message.reply_text("Дію скасовано.")
    return ConversationHandler.END

async def close_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with Database(DB_NAME) as db:
            active_queues = db.get_current_active_queues()
    except DatabaseException:
        await update.message.reply_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    if not active_queues:
        await update.message.reply_text("Зараз немає активних черг.")
        return ConversationHandler.END

    keyboard = []
    for aq in active_queues:
        btn_text = f"{aq[1]} ({aq[2]}) - {aq[3]}"
        btn_data = f"close_q_{aq[0]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

    keyboard.append([InlineKeyboardButton("🔙 Скасувати", callback_data="cancel_close")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Обери чергу, яку хочеш закрити:",
        reply_markup=reply_markup
    )
    return SELECTING_QUEUE_TO_CLOSE

async def queue_to_close_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    schedule_id = int(query.data.replace("close_q_", ""))

    try:
        with Database(DB_NAME) as db:
            db.close_active_queue(schedule_id)
    except DatabaseException:
        await query.edit_message_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    await query.edit_message_text("✅ Чергу успішно закрито! (Користувачі більше не зможуть в неї записуватися)")
    return ConversationHandler.END

async def cancel_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Дію скасовано.")
    else:
        await update.message.reply_text("Дію скасовано.")
    return ConversationHandler.END

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with Database(DB_NAME) as db:
            active_queues = db.get_current_active_queues()
    except DatabaseException:
        await update.message.reply_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    if not active_queues:
        await update.message.reply_text("Зараз немає активних черг.")
        return ConversationHandler.END

    keyboard = []
    for aq in active_queues:
        btn_text = f"{aq[1]} ({aq[2]}) - {aq[3]}"
        btn_data = f"rm_q_{aq[0]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

    keyboard.append([InlineKeyboardButton("🔙 Скасувати", callback_data="cancel_rm")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Обери чергу, з якої хочеш видалити юзера:",
        reply_markup=reply_markup
    )
    return SELECTING_QUEUE_TO_REMOVE_USER

async def queue_to_remove_from_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    schedule_id = int(query.data.replace("rm_q_", ""))
    context.user_data['rm_schedule_id'] = schedule_id

    try:
        with Database(DB_NAME) as db:
            users_in_queue = db.get_queue_with_users(schedule_id)
    except DatabaseException:
        await query.edit_message_text("❌ Помилка бази даних.")
        return ConversationHandler.END

    if not users_in_queue:
        await query.edit_message_text("Ця черга наразі порожня.")
        return ConversationHandler.END

    keyboard = []
    for u in users_in_queue:
        # u[0]=user_id, u[1]=full_name, u[2]=position, u[3]=lab_number
        btn_text = f"Поз: {u[2]} | {u[1]} | Лаба: {u[3]}"
        btn_data = f"rm_usr_{u[0]}_{u[3]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=btn_data)])

    keyboard.append([InlineKeyboardButton("🔙 Скасувати", callback_data="cancel_rm")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "Обери користувача для видалення з черги:",
        reply_markup=reply_markup
    )
    return SELECTING_USER_TO_REMOVE

async def user_to_remove_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    user_id = int(parts[2])
    lab_number = int(parts[3])
    schedule_id = context.user_data.get('rm_schedule_id')

    try:
        with Database(DB_NAME) as db:
            db.remove_user_from_queue(schedule_id, user_id, lab_number)
    except DatabaseException:
        await query.edit_message_text("❌ Помилка бази даних.")
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data.clear()
    await query.edit_message_text(f"✅ Користувача успішно видалено з черги (Лаба №{lab_number}).")
    return ConversationHandler.END

async def cancel_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Дію скасовано.")
    else:
        await update.message.reply_text("Дію скасовано.")
    context.user_data.clear()
    return ConversationHandler.END

async def new_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Введіть дані для нової черги через вертикальну риску '|'.\n\n"
            "*Формат:* `/new_queue Предмет | Підгрупа | ДД.ММ.РР`\n"
            "*Приклад:* `/new_queue ТІМС | 1 | 25.10.24`",
            parse_mode="Markdown"  # Використовуємо Markdown для красивого форматування тексту
        )
        return

    raw_text = " ".join(context.args)
    parts = [part.strip() for part in raw_text.split("|")]

    if len(parts) != 3:
        await update.message.reply_text(
            "❌ Неправильний формат! Переконайтеся, що ви ввели рівно три параметри, розділені `|`."
        )
        return

    subject, subgroup, defense_date = parts

    try:
        with Database(DB_NAME) as db:
            db.insert_defense_dates(subject, subgroup, defense_date)

        await update.message.reply_text(
            f"Новий розклад успішно створено!\n\n"
            f"Предмет: {subject}\n"
            f"Підгрупа: {subgroup}\n"
            f"Дата: {defense_date}"
        )

    except ValueError:
        # Ця помилка виникне, якщо datetime.strptime не зможе розпізнати дату
        await update.message.reply_text(
            "❌ Помилка: неправильний формат дати. Використовуйте ДД.ММ.РР (наприклад, 25.10.24)."
        )
    except DatabaseException as e:
        await update.message.reply_text(f"❌ Помилка бази даних: {e.message}")

async def reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text(
            "❌ Неправильний формат.\n\n"
            "*Використання:* `/reschedule <ID_розкладу> <Нова_дата>`\n"
            "*Приклад:* `/reschedule 3 25.10.24`",
            parse_mode="Markdown"
        )
        return

    schedule_id_str, new_date = context.args

    if not schedule_id_str.isdigit():
        await update.message.reply_text("❌ ID розкладу має бути числом.")
        return

    schedule_id = int(schedule_id_str)

    try:
        with Database(DB_NAME) as db:
            db.reschedule_queue(schedule_id, new_date)

        await update.message.reply_text(
            f"✅ Дату для розкладу #{schedule_id} успішно змінено на {new_date}."
        )

    except ValueError:
        await update.message.reply_text(
            "❌ Помилка: неправильний формат дати. Використовуйте ДД.ММ.РР (наприклад, 25.10.24)."
        )
    except DatabaseException as e:
        await update.message.reply_text(f"❌ Помилка бази даних: {e.message}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Будь ласка, вкажіть текст для розсилки."
        )
        return

    text = " ".join(context.args)

    success_count = 0
    error_count = 0

    try:
        with Database(DB_NAME) as db:
            user_ids = db.get_user_ids()
    except DatabaseException:
        await update.message.reply_text("Помилка з отриманням ID користувачів.")
        return

    if not user_ids:
        await update.message.reply_text("У базі немає користувачів для розсилки.")
        return

    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            success_count += 1
        except Exception as e:
            print(f"Помилка відправки користувачу {user_id}: {e}")
            error_count += 1

    await update.message.reply_text(
        f"📢 Розсилку завершено!\n\n"
        f"✅ Успішно надіслано: {success_count}\n"
        f"❌ Помилок (заблокували бота тощо): {error_count}")

async def toggle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ""
    try:
        with Database(DB_NAME) as db:
            result = db.toggle_registration()
            match result:
                case 0:
                    text = "Реєстрацію вимкнено!"
                case 1:
                    text = "Реєстрацію увімкнено!"

    except DatabaseException as e:
        text = "Помилка з базою даних"

    await update.message.reply_text(text)

async def auto_archive_job(context: ContextTypes.DEFAULT_TYPE):
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    try:
        with Database(DB_NAME) as db:
            archived_count = db.archive_past_queues(yesterday)
            
            if archived_count > 0:
                print(f"🔄 Автоматично архівовано {archived_count} черг за {yesterday}.")
                
    except DatabaseException as e:
        print(f"❌ Помилка авто-архівування: {e}")
        
async def check_tomorrows_schedules(context: ContextTypes.DEFAULT_TYPE):
    tomorrow = datetime.now() + timedelta(days=1)
    formatted_tomorrow = tomorrow.strftime("%Y-%m-%d")

    messages_to_send = []
    user_ids = []

    try:
        with Database(DB_NAME) as db:
            schedule_ids = db.get_schedules_for_date(formatted_tomorrow)

            if not schedule_ids:
                return 

            user_ids = db.get_user_ids()

            for schedule_id in schedule_ids:
                db.update_active_queues(schedule_id)
                subject, subgroup = db.get_subject_name_and_subgroup(schedule_id)
                
                text = f"📢 Відкрито чергу на завтра:\n📚 Предмет: {subject}\n👥 Підгрупа: {subgroup}"
                messages_to_send.append(text)

    except DatabaseException as e:
        print(f"Помилка БД при перевірці черг на завтра: {e}")
        return

    if user_ids and messages_to_send:
        final_text = "\n\n".join(messages_to_send)
        
        for user_id in user_ids:
            try:
                await context.bot.send_message(chat_id=user_id, text=final_text)
            except Exception:
                pass

def main() -> None:
    # Creating database
    with Database(DB_NAME) as db:
        db.create_database()
        db.seed_initial_data()

    # Here bot runs
    app = (
            Application.builder()
            .token(TOKEN)
            .build()
        )

    # Schedule the daily job
    time_to_run = time(hour=3, minute=0)

    app.job_queue.run_daily(
        check_tomorrows_schedules,
        time=time_to_run,
        name="daily_schedule_check"
    )
    
    app.job_queue.run_daily(
        auto_archive_job,
        time=time_to_run,
        name="auto_archive_job"
    )
    

    # Filter for admins
    admin_filter = filters.User(user_id=admin_ids)  
    registered_filter = IsRegisteredUserFilter()

    # Here adding reaction to commands
    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)]
        },
        fallbacks=[CommandHandler("cancel", cancel_registration)],
        allow_reentry=True
    )
    app.add_handler(registration_conv)
    app.add_handler(CallbackQueryHandler(admin_registration_decision, pattern="^(approve|reject)_"))


    app.add_handler(CommandHandler("show_table", show_table, filters=registered_filter))

    queue_conv = ConversationHandler(
        entry_points=[CommandHandler("get_in_queue", get_in_queue, filters=registered_filter)],
        states={
            SELECTING_QUEUE: [
                CallbackQueryHandler(queue_selected, pattern="^get_in_"),
                CallbackQueryHandler(position_selected, pattern="^cancel_queue$")
            ],
            TYPING_LAB_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_lab_number)],
            SELECTING_POSITION: [CallbackQueryHandler(position_selected, pattern="^(pos_|taken_pos|cancel_queue)")]
        },
        fallbacks=[CommandHandler("cancel", cancel_queue)],
        allow_reentry=True
    )
    app.add_handler(queue_conv)

    leave_queue_conv = ConversationHandler(
        entry_points=[CommandHandler("leave_the_queue", leave_the_queue, filters=registered_filter)],
        states={
            SELECTING_QUEUE_FOR_LEAVING: [
                CallbackQueryHandler(queue_for_leaving_selected, pattern="^leave_"),
                CallbackQueryHandler(cancel_leave, pattern="^cancel_leave$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_leave)],
        allow_reentry=True
    )
    app.add_handler(leave_queue_conv)

    # Admin-only commands
    close_queue_conv = ConversationHandler(
        entry_points=[CommandHandler("close_queue", close_queue, filters=admin_filter & registered_filter)],
        states={
            SELECTING_QUEUE_TO_CLOSE: [
                CallbackQueryHandler(queue_to_close_selected, pattern="^close_q_"),
                CallbackQueryHandler(cancel_close, pattern="^cancel_close$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_close)],
        allow_reentry=True
    )
    app.add_handler(close_queue_conv)

    remove_user_conv = ConversationHandler(
        entry_points=[CommandHandler("remove_user", remove_user, filters=admin_filter & registered_filter)],
        states={
            SELECTING_QUEUE_TO_REMOVE_USER: [
                CallbackQueryHandler(queue_to_remove_from_selected, pattern="^rm_q_"),
                CallbackQueryHandler(cancel_remove, pattern="^cancel_rm$")
            ],
            SELECTING_USER_TO_REMOVE: [
                CallbackQueryHandler(user_to_remove_selected, pattern="^rm_usr_"),
                CallbackQueryHandler(cancel_remove, pattern="^cancel_rm$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_remove)],
        allow_reentry=True
    )
    app.add_handler(remove_user_conv)

    app.add_handler(CommandHandler("new_queue", new_queue, filters=admin_filter & registered_filter))
    
    app.add_handler(CommandHandler("reschedule", reschedule, filters=admin_filter & registered_filter))

    app.add_handler(CommandHandler("broadcast", broadcast, filters=admin_filter & registered_filter))

    app.add_handler(CommandHandler("toggle_registration", toggle_registration, filters=admin_filter & registered_filter))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()