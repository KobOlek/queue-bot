from telegram import Update, BotCommand, BotCommandScopeDefault, BotCommandScopeChat, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from telegram.ext.filters import MessageFilter

from datetime import datetime, timedelta

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

# State for ConversationHandler
WAITING_FOR_NAME = 1

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
                text=f"Нова заявка на реєстрацію!\nІм'я: {full_name}\nID: {user_id}",
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
    pass

async def get_in_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def leave_the_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def close_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def new_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

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
    formatted_tomorrow = tomorrow.strftime("%y%m%d")

    try:
        with Database(DB_NAME) as db:
            schedule_ids = db.get_tomorrows_schedules(formatted_tomorrow)

            if not schedule_ids:
                return

            for schedule_id in schedule_ids:
                db.update_active_queues(schedule_id)

            user_ids = db.get_user_ids()
            subject, subgroup = db.get_subject_name_and_subgroup(schedule_id)
            text = f"Черга відкрита для запису для предмету {subject} для підгрупи {subgroup} на завтра"
            for user_id in user_ids:
                try:
                    await context.bot.send_message(chat_id=user_id, text=text)
                except Exception as e:
                    pass

    except DatabaseException as e:
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
    time_to_run = datetime.time(hour=3, minute=0)

    app.job_queue.run_daily(
        check_tomorrows_schedules,
        time=time_to_run,
        name="daily_schedule_check"
    )
    
    app.job_queue.run_daily(
        check_tomorrows_schedules,
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
    app.add_handler(CommandHandler("get_in_queue", get_in_queue, filters=registered_filter))
    app.add_handler(CommandHandler("leave_the_queue", leave_the_queue, filters=registered_filter))

    # Admin-only commands
    app.add_handler(CommandHandler("close_queue", close_queue, filters=admin_filter & registered_filter))
    app.add_handler(CommandHandler("remove_user", remove_user, filters=admin_filter & registered_filter))
    app.add_handler(CommandHandler("new_queue", new_queue, filters=admin_filter & registered_filter))
    app.add_handler(CommandHandler("reschedule", reschedule, filters=admin_filter & registered_filter))
    app.add_handler(CommandHandler("broadcast", broadcast, filters=admin_filter & registered_filter))
    app.add_handler(CommandHandler("toggle_registration", toggle_registration, filters=admin_filter & registered_filter))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()