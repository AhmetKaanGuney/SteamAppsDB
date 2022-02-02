import os
import sqlite3

from appdata import AppData

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

database = os.path.join(current_dir, "apps.db")


def insert_app(app_data: AppData):
    pass



def get_new_and_trending(cursor: sqlite3.Cursor):
    cursor.execute("""
    SELECT app FROM apps
    ORDER BY app.release_date, app.positive_reviews DESC""")



def main():
    con = sqlite3.connect(database)
    cur = con.cursor()

    result = cur.execute("SELECT * FROM apps")
    print(result.fetchall())

if __name__ == "__main__":
    main()