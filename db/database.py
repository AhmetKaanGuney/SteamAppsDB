import os
import sqlite3
import json
import logging

from appdata import AppData

logging.basicConfig(level=logging.DEBUG)

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

database = os.path.join(current_dir, "apps.db")

# TODO get app snippet,  snippet_columns = [app_id, name, price, platforms, tags, header_image]
# TODO get app details as AppData(), all json fields parsed and turned into Python objects
#       then convert AppData to json with AppData.json() and send through API
# TODO get applist:
#       order by [price, release_date, reviews],
#       filter by [coming_soon, release_date, price, free-to-play, reviews_under_certain_number],
#       limit and offset then return batch

def insert_app(appdata: AppData, cursor: sqlite3.Cursor):
    # Add to Apps
    json_fields = ["developers", "publishers", "screenshots"]
    app_dict = appdata.as_dict()

    for k, v in app_dict.items():
        if k in json_fields:
            app_dict[k] = json.dumps(v)

    apps_sql = f"""
    INSERT INTO apps VALUES (
        :app_id, :name, :price,
        :release_date, :coming_soon,
        :developers, :publishers,
        :owner_count, :positive_reviews, :negative_reviews,
        :about_the_game, :short_description, :detailed_description,
        :website, :header_image, :screenshots,
        :languages, :windows, :mac, :linux
        )
    """
    cursor.execute(apps_sql, app_dict)

    # Add to Tags and Apps_Tags
    for name, votes in appdata.tags.items():
        try:
            cursor.execute(
                "INSERT INTO tags (name, votes) VALUES (:name, :votes)", {"name": name, "votes": votes}
                )
            cursor.execute("INSERT INTO apps_tags VALUES (:app_id, :tag_id)", {"app_id": appdata.app_id, "tag_id": cursor.lastrowid})
        except sqlite3.IntegrityError:
            continue

    logging.debug(get_table("tags", cursor))
    logging.debug(get_table("apps_tags", cursor))

    # Add to Genres
    for name, _id in appdata.genres.items():
        try:
            cursor.execute(
                "INSERT INTO genres VALUES (:genre_id, :name)", {"genre_id": _id, "name": name}
                )
            cursor.execute("INSERT INTO apps_genres VALUES (:app_id, :genre_id)", {"app_id": appdata.app_id, "genre_id": cursor.lastrowid})
        except sqlite3.IntegrityError:
            continue

    logging.debug(get_table("genres", cursor))
    logging.debug(get_table("apps_genres", cursor))

    # Add to Categories
    for name, _id in appdata.categories.items():
        try:
            cursor.execute(
                "INSERT INTO categories VALUES (:category_id, :name)", {"category_id": _id, "name": name}
                )
            cursor.execute("INSERT INTO apps_categories VALUES (:app_id, :category_id)", {"app_id": appdata.app_id, "category_id": cursor.lastrowid})
        except sqlite3.IntegrityError:
            continue

    logging.debug(get_table("categories", cursor))
    logging.debug(get_table("apps_categories", cursor))


def get_table(table_name: str, cursor):
    rows = cursor.execute(f"SELECT * FROM {table_name}").fetchall()
    output = "\n--- " + table_name.upper() + " ---" + "\n"
    for i in rows:
        if len(i) == 2:
            output += f"{i[0]} - {(i[1])}" + "\n"
        else:
            output += f"{i[0]} - {(i[1:])}" + "\n"

    return output


def get_applist(order_by, filters, offset, batchsize) -> list[AppData]:
    """\
    Returns list of app objects.
    ordery_by: ORDER BY,
    filters: WHERE,
    batchsize: LIMIT
    offset: OFFSET
    """
    # sqlite3
    #  LIMIT and OFFSET
    # EXAMPLE:
    # batchsize = 1000
    # offset = 0
    # while True:
    #     c.execute(
    #         'SELECT words FROM testWords ORDER BY somecriteria LIMIT ? OFFSET ?',
    #         (batchsize, offset))
    #     batch = list(c)
    #     offset += batchsize
    #     if not batch:
    #         break
    pass

def main():
    con = sqlite3.connect(":memory:")
    cur = con.cursor()

    with open("./init.sql") as f:
        script = f.read()

    cur.executescript(script)

    test_appdata =   {
        "about_the_game": "Test game",
        "app_id": 1848640,
        "categories": {
            "Single-player": 2
        },
        "coming_soon": False,
        "detailed_description": "Detailed test.",
        "developers": [
            "Aviahel"
        ],
        "genres": {
            "Indie": "23",
            "Simulation": "28",
            "Sports": "18"
        },
        "header_image": "header_image_link",
        "languages": "English, Russian",
        "linux": False,
        "mac": False,
        "name": "VR Async Balls",
        "negative_reviews": 0,
        "owner_count": 10000,
        "positive_reviews": 1,
        "price": "299",
        "publishers": [
            "Aviahel"
        ],
        "release_date": "2022-01-10",
        "screenshots": [
            {
                "id": 0,
                "path_thumbnail": "sc_link",
                "path_full": "sc_link"
            },
            {
                "id": 1,
                "path_thumbnail": "sc_link",
                "path_full": "sc_link",
            }
        ],
        "tags": {
            "Simulation": 64,
            "Sports": 55,
            "VR": 52,
            "Singleplayer": 41,
            "Asymmetric VR": 36,
            "Physics": 30,
            "Realistic": 27,
            "Atmospheric": 25,
            "Tabletop": 23,
            "Indie": 21,
            "Linear": 21,
            "Gambling": 19,
            "Turn-Based Tactics": 17,
            "First-Person": 15
        }
    }
    test_app = AppData(test_appdata)
    insert_app(test_app, cursor=cur)
    logging.debug(get_table("apps", cur))

    con.close()

if __name__ == "__main__":
    main()