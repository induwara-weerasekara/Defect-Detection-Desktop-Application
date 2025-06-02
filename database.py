import sqlite3
import os
from datetime import datetime

class Database:
    def __init__(self, db_name="QualiScanDB.db", db_directory=None):
        if db_directory:
            if not os.path.exists(db_directory):
                os.makedirs(db_directory)
            self.db_path = os.path.join(db_directory, db_name)
        else:
            self.db_path = db_name

        self.conn = sqlite3.connect(self.db_path)
        self.create_tables()
        print(f"Database initialized. File path: {self.db_path}")

    def create_tables(self):
        create_queries = [
            """
            CREATE TABLE IF NOT EXISTS detection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                week TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS defect_summary (
                date TEXT PRIMARY KEY,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                week TEXT NOT NULL,
                total_count INTEGER NOT NULL,
                intact_count INTEGER NOT NULL,
                damaged_deformed_count INTEGER NOT NULL,
                damaged_open_count INTEGER NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS defect_trends (
                period TEXT PRIMARY KEY,
                year TEXT NOT NULL,
                month TEXT NOT NULL,
                week TEXT NOT NULL,
                total_defects INTEGER NOT NULL,
                intact_count INTEGER NOT NULL,
                damaged_deformed_count INTEGER NOT NULL,
                damaged_open_count INTEGER NOT NULL
            );
            """
        ]

        try:
            for query in create_queries:
                self.conn.execute(query)
            self.conn.commit()
            print("Tables created or updated with missing columns.")
        except sqlite3.Error as e:
            print(f"Error creating or altering tables: {e}")

    def insert_result(self, timestamp, status, details):
        date_obj = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        year = date_obj.strftime("%Y")
        month = date_obj.strftime("%B")
        week = date_obj.strftime("%Y-%W")

        query = """
        INSERT INTO detection_results (timestamp, year, month, week, status, details)
        VALUES (?, ?, ?, ?, ?, ?);
        """
        try:
            self.conn.execute(query, (timestamp, year, month, week, status, details))
            self.conn.commit()
            print(f"Inserted result: {timestamp}, {status}, {details}")

            date = date_obj.strftime("%Y-%m-%d")
            self.update_defect_summary(date, year, month, week)
            self.update_defect_trends(date, year, month, week)
        except sqlite3.Error as e:
            print(f"Error inserting result: {e}")

    def update_defect_summary(self, date, year, month, week):
        query = """
        INSERT INTO defect_summary (date, year, month, week, total_count, intact_count, damaged_deformed_count, damaged_open_count)
        SELECT
            DATE(timestamp) AS date,
            ? AS year,
            ? AS month,
            ? AS week,
            COUNT(*) AS total_count,
            SUM(CASE WHEN status = 'Intact' THEN 1 ELSE 0 END) AS intact_count,
            SUM(CASE WHEN status = 'Damaged-Deformed' THEN 1 ELSE 0 END) AS damaged_deformed_count,
            SUM(CASE WHEN status = 'Damaged-Open' THEN 1 ELSE 0 END) AS damaged_open_count
        FROM detection_results
        WHERE DATE(timestamp) = ?
        GROUP BY DATE(timestamp)
        ON CONFLICT(date) DO UPDATE SET
            total_count = excluded.total_count,
            intact_count = excluded.intact_count,
            damaged_deformed_count = excluded.damaged_deformed_count,
            damaged_open_count = excluded.damaged_open_count;
        """
        try:
            self.conn.execute(query, (year, month, week, date))
            self.conn.commit()
            print(f"Updated defect_summary for date: {date}")
        except sqlite3.Error as e:
            print(f"Error updating defect_summary: {e}")

    def update_defect_trends(self, date, year, month, week):
        query = """
        INSERT INTO defect_trends (period, year, month, week, total_defects, intact_count, damaged_deformed_count, damaged_open_count)
        SELECT
            ? AS period,
            ? AS year,
            ? AS month,
            ? AS week,
            COUNT(*) AS total_defects,
            SUM(CASE WHEN status = 'Intact' THEN 1 ELSE 0 END) AS intact_count,
            SUM(CASE WHEN status = 'Damaged-Deformed' THEN 1 ELSE 0 END) AS damaged_deformed_count,
            SUM(CASE WHEN status = 'Damaged-Open' THEN 1 ELSE 0 END) AS damaged_open_count
        FROM detection_results
        WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', ?)
        ON CONFLICT(period) DO UPDATE SET
            total_defects = excluded.total_defects,
            intact_count = excluded.intact_count,
            damaged_deformed_count = excluded.damaged_deformed_count,
            damaged_open_count = excluded.damaged_open_count;
        """
        try:
            self.conn.execute(query, (month, year, month, week, date))
            self.conn.commit()
            print(f"Updated defect_trends for period: {month}")
        except sqlite3.Error as e:
            print(f"Error updating defect_trends: {e}")

    def fetch_all_results(self):
        query = """
        SELECT timestamp, status, details
        FROM detection_results
        ORDER BY timestamp DESC;
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            return results
        except sqlite3.Error as e:
            print(f"Error fetching results: {e}")
            return []

    def close(self):
        try:
            self.conn.close()
            print("Database connection closed.")
        except sqlite3.Error as e:
            print(f"Error closing database: {e}")