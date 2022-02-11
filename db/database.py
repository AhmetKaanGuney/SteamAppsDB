import os
import sqlite3
import json
import logging

from appdata import AppDetails, AppSnippet

logging.basicConfig(level=logging.DEBUG)

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

database = os.path.join(current_dir, "apps.db")
memory = ":memory:"

VALID_FIELDS = AppDetails().__attributes__
json_fields = ("developers", "publishers", "screenshots")


def insert_app(app_details: AppDetails, db):
    print("App ID: ", app_details.app_id)
    app_id = app_details.app_id
    data = {}
    # Covert some columns to json
    for k, v in app_details.items():
        if k in json_fields:
            data[k] = json.dumps(v)
        else:
            data[k] = v

    db.execute(f"""
        INSERT INTO apps
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
            db.execute("INSERT OR IGNORE INTO genres VALUES (:genre_id, :name)", {"genre_id": _id, "name": name})
            db.execute("INSERT INTO apps_genres VALUES (:app_id, :genre_id)", {"app_id": app_id, "genre_id": _id})

    if app_details.categories:
        for name, _id in app_details.categories.items():
            db.execute("INSERT OR IGNORE INTO categories VALUES (:category_id, :name)", {"category_id": _id, "name": name})
            db.execute("INSERT INTO apps_categories VALUES (:app_id, :category_id)", {"app_id": app_id, "category_id": _id})

    # Tags don't come with ids. they come with vote count for that tag
    if app_details.tags:
        for name, votes in app_details.tags.items():
            # Check tag name
            tag_id = db.execute("SELECT tag_id FROM tags WHERE name = :name", {"name": name}).fetchone()
            if tag_id:
                db.execute("INSERT INTO apps_tags VALUES (:app_id, :tag_id, :votes)", {"app_id": app_id, "tag_id": tag_id[0], "votes": votes})
            else:
                db.execute("INSERT INTO tags VALUES (:tag_id, :name)", {"tag_id": tag_id, "name": name})
                db.execute("INSERT INTO apps_tags VALUES (:app_id, :tag_id, :votes)", {"app_id": app_id, "tag_id": db.lastrowid, "votes": votes})


# TODO add the parameters
def get_applist(db) -> list[AppSnippet]:
    """\
    Returns list of app snippets.
    ordery_by: ORDER BY,
    filters: WHERE,
    batchsize: LIMIT
    offset: OFFSET
    """
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

    # Check LIMIT, OFFSET
    for i in [limit, offset]:
        if not isinstance(i, int):
            raise ValueError(f"'{i}' should be an int.")

    # Check ORDER BY
    for col, direction in order_by.items():
        if col not in VALID_FIELDS:
            raise ValueError(f"'{col}' is not a valid column to order by.")
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"'{direction}' is not a valid direction. Direction can only be 'ASC' or 'DESC'.")

    # Check FIELDS
    for k in filters:
        if k not in ("tags", "genres", "categories"):
            raise ValueError(f"'{k}' is not a valid filter.")
        if not filters[k]:
            continue
        # Protect againsts injection  - only accept integer values
        for i in filters[k]:
            if not isinstance(i, int):
                raise ValueError(f"For filtering '{k}', can only use type int for their ids.")

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
    filter_sql = " INTERSECT ".join([i for i in [tag_sql, genre_sql, category_sql] if i])
    print("filter_sql: ", filter_sql)

    if order_by:
        order_sql = f" ORDER BY " + ", ".join((f"{col} {direction}" for col, direction in order_by.items()))
    else:
        order_sql = ""
    print(order_sql)

    snippet_columns = (
        "app_id", "name", "price",
        "release_date", "coming_soon",
        "positive_reviews", "negative_reviews", "owner_count",
        "header_image", "windows", "mac", "linux"
    )

    if filter_sql:
        ordered_apps = db.execute(f"""
            SELECT {",".join(snippet_columns)}
            FROM apps
            WHERE app_id IN ({filter_sql}) {order_sql}
            LIMIT {limit} OFFSET {offset}
            """).fetchall()
    else:
        ordered_apps = db.execute(f"""
            SELECT {",".join(snippet_columns)}
            FROM apps
            LIMIT {limit} OFFSET {offset}
            """).fetchall()

    # Match queried columns with fetched values
    applist = []
    for app in ordered_apps:
        snippet_data = {col: app[i] for i, col in enumerate(snippet_columns)}
        applist.append(AppSnippet(snippet_data))

    return applist


def get_app_details(app_id: int, db) -> AppDetails:
    logging.debug(f"get_app_details()")
    query = db.execute("SELECT * FROM apps WHERE app_id=?", (app_id, )).fetchone()

    table_info = db.execute("PRAGMA table_info(apps)").fetchall()
    # Add column names
    columns = (i[1] for i in table_info)

    app_data = {}
    for i, col in enumerate(columns):
        if col in json_fields:
            app_data[col] = json.loads(query[i])
        else:
            app_data[col] = query[i]

    tags = get_tags(app_id, db)
    genres = get_genres(app_id, db)
    categories = get_categories(app_id, db)

    for i in (("tags", tags), ("genres", genres), ("categories", categories)):
        app_data.update({i[0]: i[1]})

    logging.debug(f"  Tags: {tags}")
    logging.debug(f"  Genres: {genres}")
    logging.debug(f"  Categories: {categories}")
    logging.debug(f"  App_data: {app_data}")

    return AppDetails(app_data)


def build_query(table_name: str, columns: list[str], conditions: list[str]) -> str:
    """
    table: name of table,
    columns: list of columns,
    conditions: list of conditions
    """
    # SQL = f"SELECT *app_id*, *name* FROM *apps* WHERE price < 100 AND coming_soon = 1"
    sql = "SELECT "
    cols_size = len(columns)
    for i, col in enumerate(columns):
        if i == cols_size - 1:
            sql += f"{col} "
        else:
            sql += f"{col}, "

    sql += f"FROM {table_name} "

    conds_size = len(conditions)
    if conds_size == 0:
        return sql

    sql += "WHERE "
    for i, condition in enumerate(conditions):
        # if reached last condition
        if i == conds_size - 1:
            sql += f"{condition}"
        else:
            sql += f"{condition} AND "

    return sql


def get_app_snippet(app_id: int, db):
    logging.debug("get_app_snippet()")

    app_query = db.execute("""
        SELECT app_id, name, price, release_date,
        header_image, windows, mac, linux
        FROM apps
        WHERE app_id = :app_id""", {"app_id": app_id}).fetchone()
    columns = ("app_id", "name", "price", "release_date", "header_image", "windows", "mac", "linux")
    app_snippet = {columns[i]: app_query[i] for i in range(len(app_query))}

    tag_query = get_tags(app_id, db)
    app_snippet.update({"tags": tag_query})

    logging.debug(f"  App Snippet: {app_snippet}")
    return app_snippet


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


# Context Manager
class Connection:
    def __init__(self, database: str):
        self.con = sqlite3.connect(database)

    def __enter__(self):
        return self.con.cursor()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.con.commit()
        self.con.close()


if __name__ == "__main__":
    with open("./test_app_data.json", "r") as f:
        app_data = json.load(f)

    app_data1 = app_data[0]
    app_data2 = app_data[1]
    app_data3 = app_data[2]

    with Connection(memory) as db:
        init_db(db)
        insert_app(AppDetails(app_data1), db)
        insert_app(AppDetails(app_data2), db)
        insert_app(AppDetails(app_data3), db)

        print("APPS TAGS: ")
        print_table("apps_tags", db)
        print("---")
        # print("App Details: ")
        # get_app_details(app_data1["app_id"], db)
        # print("App Snippet: ")
        # get_app_snippet(app_data1["app_id"], db)
        # for i in ["genres", "categories", "tags"]:
        #     print(i.upper(), ": ")
        #     query = {"table": i, "columns": ["*"], "conditions": []}
        #     print(db.execute(build_query(query)).fetchall())

        get_applist(db)