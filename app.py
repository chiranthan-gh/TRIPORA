
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from database import get_connection, initialize_database

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from datetime import date
import secrets
import re
import sqlite3
import os


# ==========================================
# APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "TRIPORA_SECRET_KEY",
    "tripora-development-key-change-before-deployment"
)

initialize_database()


# ==========================================
# REGISTRATION
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if session.get("user_id"):
        return redirect(url_for("home"))

    error = None

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        if not full_name or not email or not password:

            error = "Please complete all fields."

        elif len(full_name) > 100:

            error = "Name must not exceed 100 characters."

        elif not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email
        ):

            error = "Enter a valid email address."

        elif len(email) > 254:

            error = "Email address is too long."

        elif len(password) < 8:

            error = "Password must contain at least 8 characters."

        else:

            connection = get_connection()

            try:

                password_hash = generate_password_hash(password)

                cursor = connection.execute("""
                    INSERT INTO users (
                        full_name,
                        email,
                        password_hash
                    )
                    VALUES (?, ?, ?)
                """, (
                    full_name,
                    email,
                    password_hash
                ))

                connection.commit()

                session.clear()

                session["user_id"] = cursor.lastrowid
                session["user_name"] = full_name
                session["user_email"] = email

                return redirect(url_for("home"))

            except sqlite3.IntegrityError:

                connection.rollback()

                error = "An account with this email already exists."

            finally:

                connection.close()

    return render_template("register.html", error=error)


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user_id"):
        return redirect(url_for("home"))

    error = None

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        password = request.form.get("password", "")

        connection = get_connection()

        try:

            user = connection.execute("""
                SELECT *
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

        finally:

            connection.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            session["user_email"] = user["email"]

            return redirect(url_for("home"))

        error = "Invalid email address or password."

    return render_template("login.html", error=error)


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return redirect(url_for("home"))


# ==========================================
# HOME AND FLIGHT SEARCH
# ==========================================

@app.route("/", methods=["GET", "POST"])
def home():

    flights = []
    error = None

    if request.method == "POST":

        origin = request.form.get("origin", "").strip()

        destination = request.form.get("destination", "").strip()

        travel_date = request.form.get("travel_date", "").strip()

        passengers = request.form.get("passengers", "").strip()

        if not all([origin, destination, travel_date, passengers]):

            error = "Please complete all search fields."

        elif origin.casefold() == destination.casefold():

            error = "Origin and destination cannot be the same."

        else:

            try:

                passenger_count = int(passengers)

                selected_date = date.fromisoformat(travel_date)

                if not 1 <= passenger_count <= 4:

                    error = "Select between 1 and 4 passengers."

                elif selected_date < date.today():

                    error = "Please select a future travel date."

            except ValueError:

                error = "Please enter valid search details."

        if error is None:

            connection = get_connection()

            try:

                flights = connection.execute("""
                    SELECT *
                    FROM flights
                    WHERE LOWER(origin) = LOWER(?)
                    AND LOWER(destination) = LOWER(?)
                    AND travel_date = ?
                    AND seats_available >= ?
                    ORDER BY price ASC
                """, (
                    origin,
                    destination,
                    travel_date,
                    passenger_count
                )).fetchall()

            finally:

                connection.close()

            if not flights:

                error = "No matching flights found. Try another search."

    return render_template(
        "index.html",
        flights=flights,
        error=error,
        current_date=date.today().isoformat(),
        user_name=session.get("user_name")
    )


# ==========================================
# FLIGHT BOOKING
# ==========================================

@app.route("/book/<int:flight_id>", methods=["GET", "POST"])
def book_flight(flight_id):

    connection = get_connection()

    try:

        flight = connection.execute(
            "SELECT * FROM flights WHERE id = ?",
            (flight_id,)
        ).fetchone()

    finally:

        connection.close()

    if flight is None:

        return "Flight not found.", 404

    error = None

    if request.method == "POST":

        passenger_name = request.form.get(
            "passenger_name", ""
        ).strip()

        email = request.form.get("email", "").strip().lower()

        phone = request.form.get("phone", "").strip()

        try:

            passengers = int(request.form.get("passengers", "0"))

        except ValueError:

            passengers = 0

        if not passenger_name or not email or not phone:

            error = "Please complete all passenger details."

        elif not 1 <= passengers <= 4:

            error = "Passenger count must be between 1 and 4."

        elif len(passenger_name) > 100:

            error = "Passenger name is too long."

        elif not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+",
            email
        ):

            error = "Please enter a valid email address."

        elif not re.fullmatch(r"[0-9]{10,15}", phone):

            error = "Enter a valid phone number (10–15 digits)."

        elif (
            session.get("user_email")
            and email != session["user_email"].lower()
        ):

            error = "Use your registered account email for this booking."

        else:

            total_amount = flight["price"] * passengers

            booking_reference = (
                "TRP-" + secrets.token_hex(4).upper()
            )

            connection = get_connection()

            try:

                connection.execute("BEGIN IMMEDIATE")

                current_flight = connection.execute("""
                    SELECT *
                    FROM flights
                    WHERE id = ?
                """, (flight_id,)).fetchone()

                if current_flight is None:

                    raise ValueError("Flight is no longer available.")

                if current_flight["seats_available"] < passengers:

                    raise ValueError(
                        "Not enough seats are currently available."
                    )

                cursor = connection.execute("""
                    UPDATE flights
                    SET seats_available = seats_available - ?
                    WHERE id = ?
                    AND seats_available >= ?
                """, (
                    passengers,
                    flight_id,
                    passengers
                ))

                if cursor.rowcount != 1:

                    raise ValueError(
                        "Unable to reserve the requested seats."
                    )

                connection.execute("""
                    INSERT INTO bookings (
                        booking_reference,
                        flight_id,
                        passenger_name,
                        email,
                        phone,
                        passengers,
                        total_amount,
                        booking_status,
                        payment_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    booking_reference,
                    flight_id,
                    passenger_name,
                    email,
                    phone,
                    passengers,
                    total_amount,
                    "CONFIRMED",
                    "SIMULATED_SUCCESS"
                ))

                connection.commit()

                return render_template(
                    "confirmation.html",
                    booking_reference=booking_reference,
                    passenger_name=passenger_name,
                    email=email,
                    phone=phone,
                    passengers=passengers,
                    flight=current_flight,
                    total_amount=total_amount
                )

            except (ValueError, sqlite3.Error) as exception:

                connection.rollback()

                error = str(exception)

            finally:

                connection.close()

    return render_template(
        "booking.html",
        flight=flight,
        error=error,
        user_email=session.get("user_email")
    )


# ==========================================
# MY TRIPS - AUTHENTICATED BOOKING HISTORY
# ==========================================

@app.route("/my-trips")
def my_trips():

    if not session.get("user_id"):

        return redirect(url_for("login"))

    email = session["user_email"]

    connection = get_connection()

    try:

        bookings = connection.execute("""
            SELECT
                bookings.*,
                flights.airline,
                flights.flight_number,
                flights.origin,
                flights.destination,
                flights.travel_date,
                flights.departure_time,
                flights.arrival_time

            FROM bookings

            JOIN flights
            ON bookings.flight_id = flights.id

            WHERE LOWER(bookings.email) = LOWER(?)

            ORDER BY bookings.created_at DESC
        """, (email,)).fetchall()

    finally:

        connection.close()

    message = request.args.get("message", "")

    return render_template(
        "my_trips.html",
        bookings=bookings,
        email=email,
        message=message,
        user_name=session.get("user_name")
    )


# ==========================================
# CANCEL BOOKING
# ==========================================

@app.route("/cancel-booking/<int:booking_id>", methods=["POST"])
def cancel_booking(booking_id):

    if not session.get("user_id"):

        return redirect(url_for("login"))

    email = session["user_email"]

    connection = get_connection()

    try:

        connection.execute("BEGIN IMMEDIATE")

        booking = connection.execute("""
            SELECT *
            FROM bookings
            WHERE id = ?
        """, (booking_id,)).fetchone()

        if booking is None:

            raise ValueError("Booking not found.")

        if booking["email"].casefold() != email.casefold():

            raise ValueError("You cannot cancel another user's booking.")

        if booking["booking_status"] != "CONFIRMED":

            raise ValueError("This booking has already been cancelled.")

        cursor = connection.execute("""
            UPDATE bookings
            SET booking_status = 'CANCELLED'
            WHERE id = ?
            AND booking_status = 'CONFIRMED'
        """, (booking_id,))

        if cursor.rowcount != 1:

            raise ValueError("Unable to cancel this booking.")

        connection.execute("""
            UPDATE flights
            SET seats_available = seats_available + ?
            WHERE id = ?
        """, (
            booking["passengers"],
            booking["flight_id"]
        ))

        connection.commit()

        message = "Booking cancelled successfully. Seats have been restored."

    except (ValueError, sqlite3.Error) as exception:

        connection.rollback()

        message = str(exception)

    finally:

        connection.close()

    return redirect(url_for(
        "my_trips",
        message=message
    ))


# ==========================================
# APPLICATION ENTRY POINT
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)
