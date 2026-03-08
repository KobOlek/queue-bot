# 🤖 Queue Bot

A Python-based bot designed to manage queues and parse schedules automatically. Perfect for organizing student lab queues, managing daily tasks, or keeping track of schedules in your community group.

## ✨ Features

* **Queue Management**: Easily create, join, leave, and manage queues.
* **Schedule Parsing**: Automatically fetches and parses schedules using the built-in `schedule_parser.py`.
* **Database Integration**: Persistent data storage to ensure queue and schedule data isn't lost during restarts (`database.py`).
* **Custom Error Handling**: Graceful error management to keep the bot running smoothly (`exception.py`).
* **Easy Configuration**: Simple setup using centralized configuration parameters (`config.py`).

## 📂 Repository Structure

* `bot.py` — The main entry point and bot logic.
* `schedule_parser.py` — Module responsible for scraping/parsing schedule data.
* `database.py` — Handles all database interactions (e.g., SQLite/PostgreSQL).
* `config.py` — Stores environment variables and bot configuration.
* `exception.py` — Custom exception classes for predictable error handling.
* `requirements.txt` — Python dependencies required to run the bot.

## 🚀 Getting Started

Follow these instructions to get a copy of the bot up and running on your local machine or server.

### Prerequisites

* **Python 3.8+** installed on your system.
* A Bot Token (from [BotFather](https://t.me/botfather) for Telegram, or the Discord Developer Portal).
* (Optional) A database server if not using SQLite.

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/KobOlek/queue-bot.git](https://github.com/KobOlek/queue-bot.git)
   cd queue-bot

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt

Configuration:
Open config.py or create a .env file (depending on your setup).
Insert your Bot API Token, database URI, and other necessary credentials.
Run the bot:
```bash
python bot.py
```

🛠️ Usage
Once the bot is running, you can interact with it using the predefined commands.

🤝 Contributing
Contributions, issues, and feature requests are welcome!
Feel free to check the issues page if you want to contribute.

📜 License
Distributed under the MIT License.

👤 Authors:
@KobOlek
@OlekBliter
