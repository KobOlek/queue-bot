import sqlite3

from datetime import datetime
from schedule_parser import parse_json
from config import admins

from exception import DatabaseException

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
                        schedule_id INTEGER,
                        user_id INTEGER,
                        lab_number INTEGER NOT NULL,
                        position INTEGER,
                        archived_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (schedule_id) REFERENCES Schedules (id) ON DELETE SET NULL,
                        FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE SET NULL""")

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
            raise DatabaseException(f"Query failed: {e}")

    def fetch(self, query: str, parameters: tuple = ()) -> list[tuple]:
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
        data = parse_json("schedules.json")

        for subject, subgroup, defense_date in data:
            self.insert_defense_dates(subject, subgroup, defense_date)

        for name, user_id in admins.items():
            self.execute("INSERT OR IGNORE INTO Users (user_id, full_name) VALUES (?, ?)", (user_id, name,))

        settings_count = self.fetch("SELECT COUNT(*) FROM Settings")
        if settings_count and settings_count[0][0] == 0:
            self.execute("INSERT INTO Settings (registration_enabled) VALUES (1)")

    def insert_defense_dates(self, subject: str, subgroup: str, defense_date: str):
        parsed_date = datetime.strptime(defense_date, "%d.%m.%y")
        formatted_date = parsed_date.strftime("%Y-%m-%d")

        query = """INSERT OR IGNORE INTO Schedules (subject, subgroup, defense_date) 
               VALUES (?, ?, ?)"""

        self.execute(query, (subject, subgroup, formatted_date))

    def is_registration_enabled(self) -> bool:
        query = "SELECT registration_enabled FROM Settings"
        response = self.fetch(query)
        if not response:
            return True
        return response[0][0] == 1
    
    def is_user_registered(self, user_id: int) -> bool:
        query = "SELECT 1 FROM Users WHERE user_id = ?"
        result = self.fetch(query, (user_id,))
        return bool(result)
    
    def register_user(self, user_id, full_name):
        query = """INSERT INTO Users (user_id, full_name) 
                        VALUES (?, ?)"""
        self.execute(query, (user_id, full_name,))

    def get_user_ids(self) -> list[int]:
        query = "SELECT user_id FROM Users"
        query_result = self.fetch(query)
        result = []
        for v in query_result:
            result.append(v[0])

        return result

    def toggle_registration(self) -> int:
        if self.is_registration_enabled():
            query = """UPDATE Settings SET registration_enabled = ?"""
            self.execute(query, (0,))
            return 0
        else:
            query = """UPDATE Settings SET registration_enabled = ?"""
            self.execute(query, (1,))
            return 1
        
    def archive_past_queues(self, target_date: str) -> int:
        """
        Finds open queues for the specified date, moves them to Archive, 
        deletes them from Queues, and closes them (is_open = 0).
        """
        # Reading: Looking for schedules from yesterday that are still open
        query_find = """
            SELECT s.id 
            FROM Schedules s
            JOIN Active_Queues aq ON s.id = aq.schedule_id
            WHERE s.defense_date = ? AND aq.is_open = 1
        """
        schedules_to_archive = self.fetch(query_find, (target_date,))
        
        if not schedules_to_archive:
            return 0
            
        count = 0
        for row in schedules_to_archive:
            schedule_id = row[0]
            try:
                # Data Migration: Copy to archive
                query_migrate = """
                    INSERT INTO Archive (schedule_id, user_id, lab_number, position)
                    SELECT schedule_id, user_id, lab_number, position
                    FROM Queues
                    WHERE schedule_id = ?
                """
                self.cursor.execute(query_migrate, (schedule_id,))
                
                # Cleaning: Delete from the worksheet
                query_clean = "DELETE FROM Queues WHERE schedule_id = ?"
                self.cursor.execute(query_clean, (schedule_id,))
                
                # Closing: Change the status to closed
                query_close = "UPDATE Active_Queues SET is_open = 0 WHERE schedule_id = ?"
                self.cursor.execute(query_close, (schedule_id,))
                
                # Commit a transaction for a specific queue
                self.conn.commit()
                count += 1
                
            except sqlite3.Error as e:
                self.conn.rollback() # We cancel changes if there was an error
                raise DatabaseException(f"Помилка архівування черги {schedule_id}: {e}")
                
        return count

    def get_schedules_for_date(self, target_date: str) -> list[int]:
        """
        Retrieves schedule IDs for a specific date.
        target_date should be in 'YYYY-MM-DD' format.
        """
        query = "SELECT id FROM Schedules WHERE defense_date = ?"
        results = self.fetch(query, (target_date,))

        return [row[0] for row in results]

    def update_active_queues(self, schedule_id: int) -> None:
        if schedule_id:
            query = """SELECT COUNT(*) FROM Active_Queues WHERE schedule_id = ?"""
            res = self.fetch(query, (schedule_id,))
            if res[0][0] != 0:
                query = """UPDATE Active_Queues SET is_open = ? WHERE schedule_id = ?"""
                self.execute(query, (1, schedule_id))
            else:
                query = """INSERT INTO Active_Queues (schedule_id, is_open) VALUES (?, ?)"""
                self.execute(query, (schedule_id, 1))

    def get_subject_name_and_subgroup(self, schedule_id: int) -> tuple[str, int]:
        subject_query = """SELECT subject FROM Schedules WHERE schedule_id = ?"""
        subject_res = self.fetch(subject_query, (schedule_id,))

        subgroup_query = """SELECT subgroup FROM Schedules WHERE schedule_id = ?"""
        subgroup_res = self.fetch(subgroup_query, (schedule_id,))
        return subject_res[0][0], subgroup_res[0][0]
