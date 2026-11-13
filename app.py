import logging
import os
import re
from contextlib import closing

import pymysql
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for


load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

database_status = {
    "connected": False,
    "message": "Database connection has not been checked yet.",
}


def get_database_config():
    """Read and validate the database configuration from the environment."""
    required_variables = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required_variables if not os.getenv(name)]
    if missing:
        raise ValueError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    database_name = os.environ["DB_NAME"]
    if not DB_NAME_PATTERN.fullmatch(database_name):
        raise ValueError("DB_NAME may contain only letters, numbers, and underscores.")

    try:
        port = int(os.getenv("DB_PORT", "3306"))
    except ValueError as error:
        raise ValueError("DB_PORT must be a number.") from error

    if not 1 <= port <= 65535:
        raise ValueError("DB_PORT must be between 1 and 65535.")

    return {
        "host": os.environ["DB_HOST"],
        "port": port,
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "connect_timeout": 10,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }, database_name


def get_database_connection():
    """Open a connection to the configured application database."""
    config, database_name = get_database_config()
    return pymysql.connect(**config, database=database_name)


def initialize_database():
    """Create the database and students table without deleting existing data."""
    global database_status

    try:
        config, database_name = get_database_config()

        # DB_NAME is validated before it is used as an SQL identifier.
        with closing(pymysql.connect(**config)) as server_connection:
            with server_connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            server_connection.commit()

        with closing(pymysql.connect(**config, database=database_name)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS students (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        email VARCHAR(255) NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            connection.commit()

        database_status = {
            "connected": True,
            "message": "Connected to Amazon RDS MySQL",
        }
        logger.info("Database and students table are ready.")
        return True
    except (ValueError, RuntimeError, pymysql.MySQLError) as error:
        database_status = {
            "connected": False,
            "message": "Unable to connect to Amazon RDS MySQL. Check the setup.",
        }
        logger.error("Database initialization failed: %s", error)
        return False


def fetch_students():
    """Return all registered students, newest first."""
    global database_status

    try:
        with closing(get_database_connection()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, name, email, created_at "
                    "FROM students ORDER BY created_at DESC, id DESC"
                )
                students = cursor.fetchall()

        database_status = {
            "connected": True,
            "message": "Connected to Amazon RDS MySQL",
        }
        return students, None
    except (ValueError, RuntimeError, pymysql.MySQLError) as error:
        database_status = {
            "connected": False,
            "message": "Unable to connect to Amazon RDS MySQL. Check the setup.",
        }
        logger.error("Could not retrieve students: %s", error)
        return [], "Students could not be loaded. Check the database setup and try again."


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not name or len(name) > 100:
            return redirect(url_for("index", error="invalid_name"))
        if len(email) > 255 or not EMAIL_PATTERN.fullmatch(email):
            return redirect(url_for("index", error="invalid_email"))

        try:
            with closing(get_database_connection()) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO students (name, email) VALUES (%s, %s)",
                        (name, email),
                    )
                connection.commit()
            return redirect(url_for("index", notice="registered"))
        except pymysql.IntegrityError as error:
            if error.args and error.args[0] == 1062:
                return redirect(url_for("index", error="duplicate"))
            logger.error("Student insert integrity error: %s", error)
            return redirect(url_for("index", error="database"))
        except (ValueError, RuntimeError, pymysql.MySQLError) as error:
            logger.error("Could not register student: %s", error)
            return redirect(url_for("index", error="database"))

    messages = {
        "invalid_name": ("danger", "Enter a student name between 1 and 100 characters."),
        "invalid_email": ("danger", "Enter a valid email address."),
        "duplicate": ("warning", "A student with that email address is already registered."),
        "database": ("danger", "Registration failed. Check the database setup and try again."),
    }
    notification = None
    if request.args.get("notice") == "registered":
        notification = ("success", "Student registered successfully.")
    elif request.args.get("error") in messages:
        notification = messages[request.args["error"]]

    students, load_error = fetch_students()
    if load_error and notification is None:
        notification = ("danger", load_error)

    return render_template(
        "index.html",
        students=students,
        database_status=database_status,
        notification=notification,
    )


if __name__ == "__main__":
    initialize_database()
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=False,
    )
