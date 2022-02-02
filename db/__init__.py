"""Initialize sqlite database"""
import sqlite3

import os

# TODO check init script
# TODO check tables
current_dir = os.path.basename(__file__)
parent_dir = os.path.dirname(current_dir)

database = os.path.join(current_dir, "apps.db")
init_script = os.path.join(current_dir, "init.sql")

con = sqlite3.connect(database)
cur = con.cursor()

cur.executescript(init_script)

con.commit()
con.close()

