from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, Updater, filters, ContextTypes, CallbackContext

from config import *
from database import Database

async def start(update: Update, context: CallbackContext):
    pass

def main() -> None:
    # Here bot runs
    app = Application.builder().token(TOKEN).build()

    # Here adding reaction to /start
    app.add_handler(CommandHandler("start", start))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
