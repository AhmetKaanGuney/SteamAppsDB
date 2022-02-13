import os
import sqlite3
import json
import logging

try:
    from appdata import AppDetails, AppSnippet
except ImportError:
    from .appdata import AppDetails, AppSnippet
    

logging.basicConfig(level=logging.DEBUG)

current_dir = os.path.dirname(__file__)
DATABASE_PATH = os.path.join(current_dir, "apps.db")

APP_DETAILS_FIELDS = AppDetails().__attributes__
APP_SNIPPET_FIELDS = AppSnippet().__attributes__

JSON_FILEDS = ("developers", "publishers", "screenshots")


def insert_app(app_details: AppDetails, db):
    app_id = app_details.app_id
    data = {}
    # Covert fields that are dictionary to json
    # and store them
    for k, v in app_details.items():
        if k in JSON_FILEDS:
            data[k] = json.dumps(v)
        else:
            data[k] = v

    db.execute(f"""
        REPLACE INTO apps
        VALUES (
            :app_id, :name, :price,
            :release_date, :coming_soon,
            :developers, :publishers,
            :owner_count, :positive_reviews, :negative_reviews,
            :about_the_game, :short_description, :detailed_description,
            :website, :header_image, :screenshots,
            :languages, :windows, :mac, :linux
        )""", data)

    if app_details.genres:
        for name, _id in app_details.genres.items():
            db.execute("INSERT OR IGNORE INTO genres VALUES (:genre_id, :name)",
                                            {"genre_id": _id, "name": name})
            db.execute("INSERT OR IGNORE INTO apps_genres VALUES (:app_id, :genre_id)",
                                                {"app_id": app_id, "genre_id": _id})

    if app_details.categories:
        for name, _id in app_details.categories.items():
            db.execute("INSERT OR IGNORE INTO categories VALUES (:category_id, :name)",
                                                {"category_id": _id, "name": name})
            db.execute("INSERT OR IGNORE INTO apps_categories VALUES (:app_id, :category_id)",
                                                    {"app_id": app_id, "category_id": _id})

    # Tags don't come with ids. they come with vote count for that tag
    if app_details.tags:
        for name, votes in app_details.tags.items():
            # Check tag name
            tag_id = db.execute("SELECT tag_id FROM tags WHERE name = :name", {"name": name}).fetchone()
            if tag_id:
                db.execute("INSERT OR IGNORE INTO apps_tags VALUES (:app_id, :tag_id, :votes)",
                                    {"app_id": app_id, "tag_id": tag_id[0], "votes": votes})
            else:
                db.execute("INSERT INTO tags VALUES (:tag_id, :name)", {"tag_id": tag_id, "name": name})
                db.execute("INSERT OR IGNORE INTO apps_tags VALUES (:app_id, :tag_id, :votes)",
                                {"app_id": app_id, "tag_id": db.lastrowid, "votes": votes})


def get_applist(filters: dict, order_by: dict, limit, offset, db) -> list[AppSnippet]:
    """
    ordery_by: {
        column_name: order (only 'ASC' or 'DESC')
        }
    filters: {
        tags: list of tag ids,
        genres: list of genre ids,
        categories: list of category ids
        }
    limit: number of rows to return
    offset: row number to start from
    """
    # Check LIMIT, OFFSET
    if not isinstance(limit, int):
        raise TypeError(f"'{limit}' is not an int. Limit parameter should be an int.")
    if not isinstance(offset, int):
        raise TypeError(f"'{offset}' is not an int. Offset parameter should be an int.")

    # Check ORDER BY
    for col, order in order_by.items():
        if col not in APP_DETAILS_FIELDS:
            raise ValueError(f"'{col}' is not a valid column to order by.")
        if order not in ("ASC", "DESC"):
            raise ValueError(f"'{order}' is not a valid order. Order can only be 'ASC' or 'DESC'.")

    # Check FIELDS
    for f in filters:
        if f not in ("tags", "genres", "categories"):
            raise ValueError(f"'{f}' is not a valid filter.")
        if not filters[f]:
            continue
        # Protect againsts injection  - only accept integer values
        for _id in filters[f]:
            if not isinstance(_id, int):
                raise TypeError(f"'{_id}' is not an int. To filter by '{f}', can only use type int for their ids.")


    tags = ",".join([str(i) for i in filters["tags"]])
    genres = ",".join([str(i) for i in filters["genres"]])
    categories = ",".join([str(i) for i in filters["categories"]])

    # Build sql
    tag_sql = ""
    genre_sql = ""
    category_sql = ""

    if filters["tags"]:
       tag_sql = f"SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN ({tags})"

    if filters["genres"]:
        genre_sql = f"SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN ({genres})"

    if filters["categories"]:
        category_sql = f"SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN ({categories})"

    # Filter empty sql strings and join them
    filter_columns = " INTERSECT ".join([s for s in [tag_sql, genre_sql, category_sql] if s])

    if filter_columns:
        filter_sql = f"WHERE app_id IN ({filter_columns})"
    else:
        filter_sql = ""

    logging.debug(f"Filter Columns String: '{filter_columns}'")
    logging.debug(f"Filter Sql : '{filter_sql}'")

    if order_by:
        order_sql = f"ORDER BY " + ", ".join((f"{col} {direction}" for col, direction in order_by.items()))
    else:
        order_sql = ""

    logging.debug(f"Order Sql : {order_sql}")

    # Since we use the same list (APP_SNIPPET_FILEDS) to query and
    # to turn the data into a dictionary
    # It's safe to query fields like this becuese the order of the items
    # doesn't change.
    combined_sql = f"""
    SELECT {",".join(APP_SNIPPET_FIELDS)}
    FROM apps
    {filter_sql}
    {order_sql}
    LIMIT {limit} OFFSET {offset}"""

    logging.debug(f"Combined SQL : {combined_sql}")

    ordered_apps = db.execute(combined_sql).fetchall()

    # Match queried columns with fetched values
    applist = []
    for app in ordered_apps:
        snippet_data = {col: app[i] for i, col in enumerate(APP_SNIPPET_FIELDS)}
        applist.append(AppSnippet(snippet_data))

    return applist


def get_app_details(app_id: int, db) -> AppDetails:
    query = db.execute("SELECT * FROM apps WHERE app_id=?", (app_id, )).fetchone()

    table_info = db.execute("PRAGMA table_info(apps)").fetchall()
    # Get column names
    columns = (i[1] for i in table_info)

    app_data = {}
    for i, col in enumerate(columns):
        if col in JSON_FILEDS:
            app_data[col] = json.loads(query[i])
        else:
            app_data[col] = query[i]

    tags = get_tags(app_id, db)
    genres = get_genres(app_id, db)
    categories = get_categories(app_id, db)

    for i in (("tags", tags), ("genres", genres), ("categories", categories)):
        app_data.update({i[0]: i[1]})

    return AppDetails(app_data)


def get_tags(app_id: int, db):
    tags = db.execute(f"""
        SELECT name, tag_id FROM tags
        WHERE tag_id IN (
            SELECT tag_id FROM apps_tags
            WHERE app_id = :app_id
        )""", {"app_id": app_id}).fetchall()

    return {i[0]: i[1] for i in tags}


def get_genres(app_id: int, db):
    genres = db.execute(f"""
        SELECT name, genre_id FROM genres
        WHERE genre_id IN (
            SELECT genre_id FROM apps_genres
            WHERE app_id = :app_id
        )""", {"app_id": app_id}
    ).fetchall()

    return {i[0]: i[1] for i in genres}


def get_categories(app_id: int, db):
    categories = db.execute(f"""
        SELECT name, category_id FROM categories
        WHERE category_id IN (
            SELECT category_id FROM apps_categories
            WHERE app_id = :app_id
        )""", {"app_id": app_id}
    ).fetchall()

    return {i[0]: i[1] for i in categories}


def print_table(table: str, db):
        table = db.execute(f"SELECT * FROM {table}")
        for row in table.fetchall():
            print(row)

def init_db(db):
    with open("init.sql") as f:
        db.executescript(f.read())

def print_columns():
    print("Columns: ")
    columns = db.execute("PRAGMA table_info(apps)").fetchall()
    print(columns)


class Connection:
    """Context manager for database"""
    def __init__(self, database: str):
        self.con = sqlite3.connect(database)

    def __enter__(self):
        return self.con.cursor()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.con.commit()
        self.con.close()


if __name__ == "__main__":
    print("Using Mock Data...")
    mock_data = os.path.join(current_dir, "test/mock_data.json")
    with open(mock_data, "r") as f:
        app_data = json.load(f)

    app_data1 = app_data[0]
    app_data2 = app_data[1]
    app_data3 = app_data[2]

    with Connection(":memory:") as db:
        # Init Database
        print("Initialising database at memory...")
        init_db(db)
        print("Inserting Apps...")
        insert_app(AppDetails(app_data1), db)
        insert_app(AppDetails(app_data2), db)
        insert_app(AppDetails(app_data3), db)
        print("---")
        app_details = get_app_details(app_data1["app_id"], db)
        print("APP DETAILS : \n", app_details)
        print("---")

        # Get Applist
        filters = {
            "tags": [],
            "genres": [],
            "categories": []
        }
        order_by = {
            "price": "ASC",
            "release_date": "DESC"
        }
        limit = 20
        offset = 0
        applist = get_applist(filters, order_by, limit, offset, db)
        print("APPLIST: \n", applist)