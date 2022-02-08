import os
import sqlite3
import json

from appdata import AppData

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

database = os.path.join(current_dir, "apps.db")
memory = ":memory:"

json_fields = ["developers", "publishers", "screenshots"]


def insert_app(app_data: AppData, db):
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
    # TODO update tags categoriesegories amd their mappings
    if app_data.genres:
        for name, _id in app_data.genres.items():
            db.execute("INSERT INTO apps_genres VALUES (:app_id, :genre_id)", {"app_id": app_data.app_id, "genre_id": _id})
            try:
                db.execute("INSERT INTO genres VALUES (:genre_id, :name)", {"genre_id": _id, "name": name})
            except sqlite3.IntegrityError:
                continue
    
    if app_data.categories:
        for name, _id in app_data.categories.items():
            db.execute("INSERT INTO apps_categories VALUES (:app_id, :category_id)", {"app_id": app_data.app_id, "category_id": _id})
            try:
                db.execute("INSERT INTO categories VALUES (:category_id, :name)", {"category_id": _id, "name": name})
            except sqlite3.IntegrityError:
                continue

    if app_data.tags:
        for name, _id in app_data.tags.items():
            db.execute("INSERT INTO apps_tags VALUES (:app_id, :tag_id)", {"app_id": app_data.app_id, "tag_id": _id})
            try:
                db.execute("INSERT INTO tags VALUES (:tag_id, :name)", {"tag_id": _id, "name": name})
            except sqlite3.IntegrityError:
                continue




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


def get_app_details(app_id: int, db) -> AppData:
    query = db.execute("SELECT * FROM apps WHERE app_id=?", (app_id, )).fetchone()

    table_info = db.execute("PRAGMA table_info(apps)").fetchall()
    columns = []
    for i in table_info:
        # Index for the column name
        columns.append(i[1])
    
    app_data = {}
    for i, col in enumerate(columns):
        if col in json_fields:
            app_data[col] = json.loads(query[i])
        else:
            app_data[col] = query[i]
    
    # BUILD QUERY!!!
    # tag_query = build_query({
    #     "table": "apps_tags", 
    #     "columns": ["tag_id"],
    #     "conditions": [f"app_id = {app_id}"]
    #     })
    # tag_ids = [i[0] for i in db.execute(tag_query).fetchall()]
    # print("TAG_IDs:\n", tag_ids)

    sql = f"""\
    SELECT tag_id, name FROM tags
    WHERE tag_id IN (
        SELECT tag_id FROM apps_tags
        WHERE app_id = :app_id
    )
    """
    tags = db.execute(sql, {"app_id": app_id}).fetchall()
    print("TAGS:\n", tags)

    return AppData(app_data)


def build_query(query: dict) -> str:
    """
    query_map {
        table: name of table,
        columns: list of columns,
        conditions: list of conditions
    }
    """
    # SQL = f"SELECT *app_id*, *name* FROM *apps* WHERE price < 100 AND coming_soon = 1"
    sql = "SELECT "
    cols_size = len(query["columns"])
    for i, col in enumerate(query['columns']):
        if i == cols_size - 1:
            sql += f"{col} "
        else:
            sql += f"{col}, "
    
    sql += f"FROM {query['table']} "

    conds_size = len(query['conditions'])
    if conds_size == 0:
        return sql
    
    sql += "WHERE "
    for i, condition in enumerate(query['conditions']):
        # if reached last condition
        if i == conds_size - 1:
            sql += f"{condition}"
        else:
            sql += f"{condition} AND "
    
    return sql


def get_app_snippet(app_id: int, db):
    app_query = db.execute("""
    SELECT app_id, name, price, release_date, 
    header_image, windows, mac, linux
    FROM apps
    WHERE app_id=?""", (app_id, ))
    print("App:")
    print(app_query.fetchall())

    tags_querry = db.execute("""
    SELECT tag_id, name FROM tags 
    WHERE tag_id = (
        SELECT tag_id FROM apps_tags WHERE app_id=:app_id
    )""", {"app_id": app_id})
    print("Tag:")
    print(tags_querry.fetchall())



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
    app_data =  {
        "app_id": 1,
        "about_the_game": "about...",
        "categories": {
            "Single-player": 2,
            "Steam Achievements": 22
        },
        "coming_soon": False,
        "detailed_description": "detailss...",
        "developers": [
            "My Label Game Studio"
        ],
        "categories":{
            "Casual": "4",
            "Indie": "23"
        },
        "header_image": "img_link",
        "languages": "English",
        "linux": False,
        "mac": True,
        "name": "App One",
        "negative_reviews": 0,
        "owner_count": 10000,
        "positive_reviews": 1,
        "price": "199",
        "publishers": [
            "My Label Game Studio"
        ],
        "release_date": "2022-01-29",
        "screenshots": [
        {
            "id": 0,
            "path_thumbnail": "img_link"
        },
        {
            "id": 1,
            "path_thumbnail": "img_link"
        }
        ],
        "short_description": "shorty..",
        "tags": {
            "Casual": 63,
            "Puzzle": 38,
            "Side Scroller": 34,
            "3D": 31,
            "Isometric": 30,
            "Singleplayer": 22,
            "Indie": 21
        },
        "website": None,
        "windows": True
    }
    app_data2 =  {
        "app_id": 2,
        "about_the_game": "about...",
        "categories": {
            "Single-player": 2,
            "Steam Achievements": 22
        },
        "coming_soon": False,
        "detailed_description": "detailss...",
        "developers": [
            "My Label Game Studio"
        ],
        "categories": {
            "Casual": "4",
            "Indie": "23"
        },
        "header_image": "img_link",
        "languages": "English",
        "linux": False,
        "mac": True,
        "name": "App Two",
        "negative_reviews": 0,
        "owner_count": 10000,
        "positive_reviews": 1,
        "price": "199",
        "publishers": [
            "My Label Game Studio"
        ],
        "release_date": "2022-01-29",
        "screenshots": [
        {
            "id": 0,
            "path_thumbnail": "img_link"
        },
        {
            "id": 1,
            "path_thumbnail": "img_link"
        }
        ],
        "short_description": "shorty..",
        "tags": {
            "Casual": 63,
            "Puzzle": 38,
            "Side Scroller": 34,
            "3D": 31,
            "Isometric": 30,
            "Singleplayer": 22,
            "Indie": 21
        },
        "website": None,
        "windows": True
    }
    app_id = app_data["app_id"]
    with Connection(memory) as db:
        init_db(db)

        print("Inserting AppData...")
        insert_app(AppData(app_data), db)

        query = {"table": "apps", "columns": ["app_id", "name"], "conditions": ["price > 100", "languages = 'English'", "positive_reviews = 1"]}
        sql = build_query(query)
        print(f"QUERY: \n{sql}")
        print(f"RESULT:\n{db.execute(sql).fetchall()}")

        insert_app(AppData(app_data2), db)
        print("App Details: ")
        get_app_details(app_id, db)
        # get_app_details(2, db)
        get_app_snippet(app_id, db)
        for i in ["genres", "categories", "tags"]:
            print(i.upper(), ": ")
            query = {"table": i, "columns": ["*"], "conditions": []}
            print(db.execute(build_query(query)).fetchall())