import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()

        self.cursor.execute("PRAGMA foreign_keys = ON;")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def create_database(self):
        """Creates database with all needed tables"""
        self.__create_table("Users", """user_id INTEGER PRIMARY KEY, -- Telegram ID
                        full_name TEXT NOT NULL""")

        self.__create_table("Schedules", """id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subject TEXT NOT NULL,
                        subgroup TEXT,
                        defense_date DATE NOT NULL,
                        UNIQUE(subject, subgroup, defense_date)
                        """)

        self.__create_table("Active_Queues", """schedule_id INTEGER PRIMARY KEY,
                        is_open INTEGER DEFAULT 0, -- 0 for False, 1 for True
                        FOREIGN KEY (schedule_id) REFERENCES Schedules (id) ON DELETE CASCADE""")

        self.__create_table("Queues", """id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        lab_number INTEGER NOT NULL,
                        join_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        position INTEGER,
                        FOREIGN KEY (schedule_id) REFERENCES Schedules (id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE CASCADE""")

        self.__create_table("Archive", """id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        lab_number INTEGER NOT NULL,
                        position INTEGER,
                        archived_at DATETIME DEFAULT CURRENT_TIMESTAMP""")

        self.__create_table("Settings", """registration_enabled INTEGER DEFAULT 1""")

    def __create_table(self, table_name: str, fields: str):
        """Creates table"""
        query = f"""CREATE TABLE IF NOT EXISTS {table_name} ({fields})"""
        self.execute(query)

    def execute(self, query: str, parameters: tuple = ()):
        """Executes query"""
        try:
            self.cursor.execute(query, parameters)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Query failed: {e}")
            self.conn.rollback()

    def fetch(self, query: str, parameters: tuple = ()):
        """Returns a list of query result"""
        self.cursor.execute(query, parameters)
        return self.cursor.fetchall()

    def get_queue_for_schedule(self, schedule_id: int):
        """
        Returns a list of users in the queue for a specific schedule.
        Format of the result: [(position, full_name, lab_number), ...]
        """
        query = """
                SELECT q.position, 
                       u.full_name, 
                       q.lab_number
                FROM Queues q
                         JOIN Users u ON q.user_id = u.user_id
                WHERE q.schedule_id = ?
                ORDER BY q.position ASC 
                """
        return self.fetch(query, (schedule_id,))

    def add_user_to_queue(self, schedule_id: int, user_id: int, lab_number: int, position: int):
        query = """
                INSERT INTO Queues (schedule_id, user_id, lab_number, position)
                VALUES (?, ?, ?, ?)
                """
        self.execute(query, (schedule_id, user_id, lab_number, position))

    def get_next_position(self, schedule_id: int) -> int:
        """Returns next free position in a queue"""
        query = "SELECT MAX(position) FROM Queues WHERE schedule_id = ?"
        result = self.fetch(query, (schedule_id,))
        current_max = result[0][0] if result and result[0][0] is not None else 0
        return current_max + 1

    def seed_initial_data(self):
        subgroup = 1
        defense_dates = {
            "OOP": ["20.02.26", "27.02.26", "06.03.26", "13.03.26", "20.03.26","27.03.26", "03.04.26",
                    "10.04.26", "17.04.26","24.04.26", "01.05.26", "08.05.26", "15.05.26", "22.05.26"],
            "ACOS": ["24.02.26", "03.03.26", "10.03.26", "17.03.26", "24.03.26", "31.03.26", "07.04.26",
                     "14.04.26", "21.04.26", "28.04.26", "05.05.26", "12.05.26", "19.05.26"],
            "Algorithms": ["24.02.26", "03.03.26", "10.03.26", "17.03.26", "24.03.26", "31.03.26", "07.04.26",
                     "14.04.26", "21.04.26", "28.04.26", "05.05.26", "12.05.26", "19.05.26"]
        }
        self.insert_defense_dates(subgroup, defense_dates)

        subgroup = 2
        defense_dates = {
            "OOP": ["20.02.26", "27.02.26", "06.03.26", "13.03.26", "20.03.26", "27.03.26", "03.04.26",
                    "10.04.26", "17.04.26", "24.04.26", "01.05.26", "08.05.26", "15.05.26", "22.05.26"],
            "ACOS": ["20.02.26", "27.02.26", "06.03.26", "13.03.26", "20.03.26", "27.03.26", "03.04.26",
                    "10.04.26", "17.04.26", "24.04.26", "01.05.26", "08.05.26", "15.05.26", "22.05.26"],
            "Algorithms": ["24.02.26", "03.03.26", "10.03.26", "17.03.26", "24.03.26", "31.03.26", "07.04.26",
                           "14.04.26", "21.04.26", "28.04.26", "05.05.26", "12.05.26", "19.05.26"]
        }
        self.insert_defense_dates(subgroup, defense_dates)

    def insert_defense_dates(self, subgroup: int, defense_dates: dict):
        def format_date_for_db(date_str: str) -> str:
            parsed_date = datetime.strptime(date_str, "%d.%m.%y")
            return parsed_date.strftime("%Y-%m-%d")

        query = """INSERT OR IGNORE INTO Schedules (subject, subgroup, defense_date) 
               VALUES (?, ?, ?)"""

        for subject, dates in defense_dates.items():
            for date in dates:
                self.execute(query, (subject, str(subgroup), format_date_for_db(date)))