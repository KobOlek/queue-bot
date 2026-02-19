import sqlite3

class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()

        self.execute("PRAGMA foreign_keys = ON;")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

    def create_database(self):
        """Creates database with all needed tables"""
        self.create_table("Users", """user_id INTEGER PRIMARY KEY, -- Telegram ID
                        full_name TEXT NOT NULL""")

        self.create_table("Schedules", """id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subject TEXT NOT NULL,
                        subgroup TEXT,
                        defense_date DATE NOT NULL""")

        self.create_table("Active_Queues", """schedule_id INTEGER PRIMARY KEY,
                        is_open INTEGER DEFAULT 0, -- 0 for False, 1 for True
                        FOREIGN KEY (schedule_id) REFERENCES Schedules (id) ON DELETE CASCADE""")

        self.create_table("Queues", """id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        lab_number INTEGER NOT NULL,
                        join_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        position INTEGER,
                        FOREIGN KEY (schedule_id) REFERENCES Schedules (id) ON DELETE CASCADE,
                        FOREIGN KEY (user_id) REFERENCES Users (user_id) ON DELETE CASCADE""")

        self.create_table("Archive", """id INTEGER PRIMARY KEY AUTOINCREMENT,
                        schedule_id INTEGER NOT NULL,
                        user_id INTEGER NOT NULL,
                        lab_number INTEGER NOT NULL,
                        position INTEGER,
                        archived_at DATETIME DEFAULT CURRENT_TIMESTAMP""")

        self.create_table("Settings", """registration_enabled INTEGER DEFAULT 1""")


    def create_table(self, table_name: str, fields: str):
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
        """Rertuns next free position in a queue"""
        query = "SELECT MAX(position) FROM Queues WHERE schedule_id = ?"
        result = self.fetch(query, (schedule_id,))
        current_max = result[0][0] if result and result[0][0] is not None else 0
        return current_max + 1