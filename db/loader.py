"""
SQLite database loader for the Nifty100 Data Foundation project.
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "nifty100.db"


def get_connection(db_path=DB_PATH):
    """
    Create a SQLite connection with foreign key enforcement enabled.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(db_path=DB_PATH):
    """
    Create all database tables using db/schema.sql.
    """
    db_path = Path(db_path)
    schema_path = Path(__file__).resolve().parent / "schema.sql"

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    with open(schema_path, "r", encoding="utf-8") as file:
        schema_sql = file.read()

    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


def load_dataframe(
    df: pd.DataFrame,
    table_name: str,
    db_path=DB_PATH,
    if_exists: str = "append",
):
    """
    Insert a normalized DataFrame into a SQLite table.

    Parameters:
        df:
            Normalized pandas DataFrame.
        table_name:
            Target SQLite table name.
        db_path:
            SQLite database path.
        if_exists:
            Behavior when table already contains data.
            Supported values: append, replace, fail.

    Returns:
        int:
            Number of rows loaded.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame.")

    if df.empty:
        return 0

    allowed_if_exists = {"append", "replace", "fail"}

    if if_exists not in allowed_if_exists:
        raise ValueError(
            f"if_exists must be one of {allowed_if_exists}"
        )

    conn = get_connection(db_path)

    try:
        df.to_sql(
            table_name,
            conn,
            if_exists=if_exists,
            index=False,
        )
        conn.commit()
    finally:
        conn.close()

    return len(df)


def get_table_row_count(
    table_name: str,
    db_path=DB_PATH,
):
    """
    Return the number of rows currently present in a table.
    """
    conn = get_connection(db_path)

    try:
        cursor = conn.execute(
            f"SELECT COUNT(*) FROM [{table_name}]"
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def foreign_key_check(db_path=DB_PATH):
    """
    Return all SQLite foreign-key violations.
    """
    conn = get_connection(db_path)

    try:
        return conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    finally:
        conn.close()


if __name__ == "__main__":
    create_schema()

    print("Database schema created successfully.")
    print(f"Database: {DB_PATH}")

    conn = get_connection()

    try:
        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        print("Tables:")
        for table in tables:
            print(f" - {table[0]}")

        print(
            "Foreign Keys:",
            conn.execute("PRAGMA foreign_keys").fetchone()[0],
        )

        print(
            "FK Check:",
            conn.execute("PRAGMA foreign_key_check").fetchall(),
        )
    finally:
        conn.close()