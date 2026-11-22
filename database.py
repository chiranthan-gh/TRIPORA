
import sqlite3
from pathlib import Path


# ==========================================
# DATABASE CONFIGURATION
# ==========================================

DATABASE = Path(__file__).with_name("tripora.db")


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_connection():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # FLIGHTS TABLE

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flights (

                id INTEGER PRIMARY KEY AUTOINCREMENT,
                airline TEXT NOT NULL,
                flight_number TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                travel_date TEXT NOT NULL,
                departure_time TEXT NOT NULL,
                arrival_time TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                seats_available INTEGER NOT NULL
                    CHECK(seats_available >= 0),

                UNIQUE(flight_number, travel_date)
            )
        """)


        # BOOKINGS TABLE

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (

                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_reference TEXT UNIQUE NOT NULL,
                flight_id INTEGER NOT NULL,
                passenger_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,

                passengers INTEGER NOT NULL
                    CHECK(passengers BETWEEN 1 AND 4),

                total_amount REAL NOT NULL
                    CHECK(total_amount >= 0),

                booking_status TEXT NOT NULL
                    DEFAULT 'CONFIRMED',

                payment_status TEXT NOT NULL
                    DEFAULT 'PENDING',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (flight_id)
                    REFERENCES flights(id)
            )
        """)


        # USERS TABLE - NEW

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                full_name TEXT NOT NULL,

                email TEXT NOT NULL UNIQUE COLLATE NOCASE,

                password_hash TEXT NOT NULL,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


        # SAMPLE FLIGHTS

        sample_flights = [

            (
                "IndiGo", "6E-201",
                "Bengaluru", "Mumbai",
                "2026-12-05",
                "06:30", "08:15",
                4500, 45
            ),

            (
                "Air India", "AI-501",
                "Bengaluru", "Mumbai",
                "2026-12-05",
                "09:00", "10:50",
                5200, 32
            ),

            (
                "Akasa Air", "QP-132",
                "Bengaluru", "Delhi",
                "2026-12-05",
                "07:15", "10:00",
                6100, 28
            ),

            (
                "IndiGo", "6E-305",
                "Mumbai", "Delhi",
                "2026-12-05",
                "12:00", "14:10",
                4800, 40
            ),

            (
                "Air India", "AI-601",
                "Delhi", "Bengaluru",
                "2026-12-05",
                "16:30", "19:15",
                6500, 35
            ),

            (
                "Akasa Air", "QP-220",
                "Bengaluru", "Hyderabad",
                "2026-12-05",
                "11:00", "12:10",
                3200, 25
            )

        ]


        cursor.executemany("""
            INSERT OR IGNORE INTO flights (
                airline,
                flight_number,
                origin,
                destination,
                travel_date,
                departure_time,
                arrival_time,
                price,
                seats_available
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_flights)


        connection.commit()

        print("TRIPORA database initialized successfully!")
        print("Flights table: Ready")
        print("Bookings table: Ready")
        print("Users table: Ready")
        print("Sample flights: Ready")


    except sqlite3.Error as error:

        connection.rollback()

        print("Database initialization failed:", error)

        raise

    finally:

        connection.close()


# ==========================================
# RUN INITIALIZATION
# ==========================================

if __name__ == "__main__":

    initialize_database()
