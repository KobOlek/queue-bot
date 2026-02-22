from telegram import Update, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import *
from database import Database

# Handler functions
# User handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def change_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def show_table(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def get_in_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def leave_the_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

# Admin handlers
async def close_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def new_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def reschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def toggle_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def admin_registration_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin registration handler
    pass

# Init function
async def post_init(application: Application):
    user_commands = [
        BotCommand("start", "Почати"),
        BotCommand("change_name", "Змінити ім'я"),
        BotCommand("show_table", "Показати чергу"),
        BotCommand("get_in_queue", "Увійти в чергу"),
        BotCommand("leave_the_queue", "Покинути чергу")
    ]

    await application.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    admin_commands = [
        BotCommand("start", "Почати"),
        BotCommand("change_name", "Змінити ім'я"),
        BotCommand("show_table", "Показати чергу"),
        BotCommand("get_in_queue", "Увійти в чергу"),
        BotCommand("leave_the_queue", "Покинути чергу"),
        BotCommand("close_queue", "Закрити чергу"),
        BotCommand("remove_user", "Видалити користувача з черги"),
        BotCommand("new_queue", "Нова черга"),
        BotCommand("reschedule", "Переназначити чергу"),
        BotCommand("broadcast", "Розіслати повідомлення"),
        BotCommand("toggle_registration", "Увімкнути/вимкнути реєстрацію")
    ]

    for admin_id in admin_ids:
        await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))

def main() -> None:
    # Creating database
    with Database(DB_NAME) as db:
        db.create_database()
        db.seed_initial_data()

    # Here bot runs
    app = (
            Application.builder()
            .token(TOKEN)
            .post_init(post_init)
            .build()
        )
    
    # Filter for admins
    admin_filter = filters.User(user_id=admin_ids)

    # Here adding reaction to commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("change_name", change_name))
    app.add_handler(CommandHandler("show_table", show_table))
    app.add_handler(CommandHandler("get_in_queue", get_in_queue))
    app.add_handler(CommandHandler("leave_the_queue", leave_the_queue))

    # Admin-only commands
    app.add_handler(CommandHandler("close_queue", close_queue, filters=admin_filter))
    app.add_handler(CommandHandler("remove_user", remove_user, filters=admin_filter))
    app.add_handler(CommandHandler("new_queue", new_queue, filters=admin_filter))
    app.add_handler(CommandHandler("reschedule", reschedule, filters=admin_filter))
    app.add_handler(CommandHandler("broadcast", broadcast, filters=admin_filter))
    app.add_handler(CommandHandler("toggle_registration", toggle_registration, filters=admin_filter))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
