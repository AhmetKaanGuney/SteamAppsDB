import os
import sqlite3
import json
import logging

from appdata import AppData

logging.basicConfig(level=logging.DEBUG)

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

database = os.path.join(current_dir, "apps.db")
memory = ":memory:"

json_fields = ("developers", "publishers", "screenshots")


def insert_app(app_data: AppData, db):
    print("App ID: ", app_data.app_id)
    data = {}
    for k, v in app_data.as_dict().items():
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

    if app_data.genres:
        for name, _id in app_data.genres.items():
            db.execute("INSERT OR IGNORE INTO genres VALUES (:genre_id, :name)", {"genre_id": _id, "name": name})
            db.execute("INSERT INTO apps_genres VALUES (:app_id, :genre_id)", {"app_id": app_data.app_id, "genre_id": _id})

    if app_data.categories:
        for name, _id in app_data.categories.items():
            db.execute("INSERT OR IGNORE INTO categories VALUES (:category_id, :name)", {"category_id": _id, "name": name})
            db.execute("INSERT INTO apps_categories VALUES (:app_id, :category_id)", {"app_id": app_data.app_id, "category_id": _id})

    if app_data.tags:
        for name, votes in app_data.tags.items():
            # Check tag name
            tag_id = db.execute("SELECT tag_id FROM tags WHERE name = :name", {"name": name}).fetchone()
            if tag_id:
                db.execute("INSERT INTO apps_tags VALUES (:app_id, :tag_id, :votes)", {"app_id": app_data.app_id, "tag_id": tag_id[0], "votes": votes})
            else:
                db.execute("INSERT INTO tags VALUES (:tag_id, :name)", {"tag_id": tag_id, "name": name})
                db.execute("INSERT INTO apps_tags VALUES (:app_id, :tag_id, :votes)", {"app_id": app_data.app_id, "tag_id": db.lastrowid, "votes": votes})


# def get_applist(order_by, filters: dict, offset, batchsize, db) -> list[AppData]:
def get_applist(filters: dict, db) -> list[AppData]:
    """\
    Returns list of app objects.
    ordery_by: ORDER BY,
    filters: WHERE,
    batchsize: LIMIT
    offset: OFFSET
    """
    filters = {
        "tags": [1],
        "genres": [],
        "categories": []
    }
    # App One: tags=1,2  genres=1,2  categories=1,2
    # App Two: tags=2,3  genres=2,3  categories=2,3
    # App Three: tags=3,4  genres=3,4  categories=3,4

    empty_filters = []
    # Check values
    for k in filters:
        if not filters[k]:
            empty_filters.append(k)
            continue

        # Protect againsts injection  - only accept integer values
        for i in filters[k]:
            if not isinstance(i, int):
                raise ValueError(f"For filtering '{k}', can only use type int for their ids")

    tags = ",".join([str(i) for i in filters["tags"]])
    genres = ",".join([str(i) for i in filters["genres"]])
    categories = ",".join([str(i) for i in filters["categories"]])
    print("tags joined:", tags)
    print("genres joined:", genres)
    print("categories joined:", categories)

    # TODO skip for empty filter then
    # append all app_ids to a filtered_app_ids set()
    # Order: Select apps where app_id in filtered_app_ids ORDER BY (someting) DESC
    tag_filtered = db.execute(f"SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN ({tags})").fetchall()
    genre_filtered = db.execute(f"SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN ({genres})").fetchall()
    category_filtered = db.execute(f"SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN ({categories})").fetchall()

    print("tag filtered:", tag_filtered)
    print("genre filtered:", genre_filtered)
    print("categorie filtered:", category_filtered)

    # filter_sql = db.execute("""
    #     SELECT app_id FROM apps_tags WHERE tag_id IN :tags
    #     INNER JOIN (
    #         SELE
    #     )
    # """)
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


def get_app_details(app_id: int, db) -> AppData:
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

    return AppData(app_data)


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
        insert_app(AppData(app_data1), db)
        insert_app(AppData(app_data2), db)
        insert_app(AppData(app_data3), db)

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

        get_applist({}, db)