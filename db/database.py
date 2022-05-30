import os
import sqlite3
import json
import logging

try:
    from appdata import App, AppSnippet
except ImportError:
    from .appdata import App, AppSnippet


logging.basicConfig(level=logging.CRITICAL)

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
APPS_DB_PATH = os.path.join(current_dir, "apps.db")
INIT_FILE = os.path.join(current_dir, "init_apps.sql")

APP_FIELDS = App.get_fields()
APP_SNIPPET_FIELDS = AppSnippet.get_fields()

JSON_FIELDS = ("developers", "publishers", "screenshots")


def insert_app(app: App, db):
    """Inserts App object to database"""
    app_id = app.app_id
    data = {}
    # Covert fields that are dictionary to json
    # and store them
    for k, v in app.items():
        if k in JSON_FIELDS:
            data[k] = json.dumps(v)
        else:
            data[k] = v

    # APP_FIELDS contains all sql column in order
    # columns example (:app_id, :name, :price, ...)
    ignore = ("tags", "genres", "categories")
    columns = [':' + i for i in APP_FIELDS if i not in ignore]
    db.execute(f"""
        REPLACE INTO apps
        VALUES ({','.join(columns)})""", data)

    if app.genres:
        for name, _id in app.genres.items():
            db.execute("REPLACE INTO genres VALUES (:genre_id, :name)",
                                            {"genre_id": _id, "name": name})
            db.execute("REPLACE INTO apps_genres VALUES (:app_id, :genre_id)",
                                                {"app_id": app_id, "genre_id": _id})

    if app.categories:
        for name, _id in app.categories.items():
            db.execute("REPLACE INTO categories VALUES (:category_id, :name)",
                                                {"category_id": _id, "name": name})
            db.execute("REPLACE INTO apps_categories VALUES (:app_id, :category_id)",
                                                    {"app_id": app_id, "category_id": _id})

    # Tags don't come with ids. they come with vote count for that tag
    if app.tags:
        for name, votes in app.tags.items():
            # Check tag name
            tag_id = db.execute("SELECT tag_id FROM tags WHERE name = :name", {"name": name}).fetchone()
            if tag_id:
                db.execute("REPLACE INTO apps_tags VALUES (:app_id, :tag_id, :votes)",
                                    {"app_id": app_id, "tag_id": tag_id[0], "votes": votes})
            else:
                db.execute("INSERT INTO tags VALUES (:tag_id, :name)", {"tag_id": tag_id, "name": name})
                db.execute("REPLACE INTO apps_tags VALUES (:app_id, :tag_id, :votes)",
                                {"app_id": app_id, "tag_id": db.lastrowid, "votes": votes})


def insert_app_over_million(app_id: int, db):
    db.execute("REPLACE INTO apps_over_million VALUES (?)", (app_id, ))


def insert_non_game_app(app_id: int, db):
    db.execute("REPLACE INTO non_game_apps VALUES (?)", (app_id, ))


def insert_failed_request(app_id: int, api_provider: str, error: str,  status_code: [int, None], db):
    db.execute("""\
        REPLACE INTO failed_requests
        VALUES (:app_id, :api_provider, :error, :status_code)
        """, {"app_id": app_id, "api_provider": api_provider, "error": error, "status_code": status_code}
    )


def get_applist(
        filters: dict, order: dict,
        coming_soon: bool, release_date: list,
        rating: int,
        offset: int, limit: int, db
        ) -> list[dict]:
    """
    Returns list of app snippets as dict objects.
    Inputs:
    filters: {
        tags: list of tag ids,
        genres: list of genre ids,
        categories: list of category ids
        }
    order: (
        column_name: 'ASC' or 'DESC'
        )
    coming_soon = 0 or 1
    release_date = [operator: str, value: str]
    limit: number of rows to return
    offset: row number to start from
    """
    check_filters(filters)
    check_order(order)
    check_release_date(release_date)
    check_rating(rating)

    filters_sql = build_filters_sql(filters)
    order_sql = build_order_sql(order)
    release_date_sql = build_release_date_sql(release_date)
    coming_soon_sql = build_coming_soon_sql(coming_soon)
    rating_sql = build_rating_sql(rating)

    combined_sql = build_combined_sql(filters_sql, order_sql, coming_soon_sql, release_date_sql, rating_sql, offset, limit)
    ordered_apps = db.execute(combined_sql).fetchall()

    applist = []
    for app in ordered_apps:
        snippet = {col: app[i] for i, col in enumerate(APP_SNIPPET_FIELDS)}
        snippet["tags"] = get_tags(snippet["app_id"], db)
        snippet["genres"] = get_genres(snippet["app_id"], db)
        snippet["categories"] = get_categories(snippet["app_id"], db)
        applist.append(snippet)

    return applist


def check_filters(filters: dict):
    """Raises error if:
    1. Keys aren't in tags, genres or categories.
    2. Values aren't list of integers.
    """
    if not isinstance(filters, dict):
        raise TypeError("Filters must be type of dict.")

    expected_keys = ("tags", "genres", "categories")
    filter_keys = [k for k in filters]

    for f in filters:
        # Check key names
        if f not in expected_keys:
            raise ValueError(f"{f} is not a valid filter.")
        # Check values
        elif not isinstance(filters[f], list):
            raise TypeError(f"Error: Invalid value for {f}: {filters[f]}, filter values must be type list.")
        # Check value content to protect againsts injection
        for _id in filters[f]:
            if not isinstance(_id, int):
                raise TypeError(f"{_id} is not an int. To filter by {f},  use type int for ids.")


def check_order(order: dict):
    """Raises error if:
    1. Key isn't a colmun name in apps table.
    2. Value isn't a valid direction string.
    """
    if not isinstance(order, dict):
        raise TypeError("Order must be type of dict.")

    for col, direction in order.items():
        check_column(col)
        if direction not in ("ASC", "DESC"):
            raise ValueError(f"{direction} is not a valid direction. Direction can only be ASC or DESC.")


def check_release_date(release_date: [list, tuple]):
    """Raises error if:
    1. First item isn't a valid comparison operator.
    2. Second item doesn't have numeric values when
    seperated by '-' character.
    """
    if not release_date:
        return
    comp_sign = release_date[0]
    date_str = release_date[1]
    valid_comp_signs = ['<', '<=', '>', '>=', '=', '!=', "IS", "IS NOT"]

    if comp_sign not in valid_comp_signs:
        raise ValueError(f"{comp_sign} is not a valid comparison sign for release_date.")

    if date_str != "NULL":
        for s in date_str.split('-'):
            if not s.isnumeric():
                raise ValueError(f"{s} is not a valid release_date string.")


def check_rating(rating: list):
    """Raises error if:
    1. First item isn't a valid comparison operator.
    2. Second value isn't numeric
    """
    if not rating:
        return
    comp_sign = rating[0]
    value = rating[1]
    valid_comp_signs = ['<', '<=', '>', '>=', '=', '!=', "IS", "IS NOT"]

    if comp_sign not in valid_comp_signs:
        raise ValueError(f"{comp_sign} is not a valid comparison sign for rating.")

    if value != "NULL":
        if not value.isnumeric():
            raise ValueError(f"{s} is not a valid rating value.")


def build_combined_sql(filters, order, coming_soon, release_date, rating, offset, limit) -> str:
    """Returns executable sql string."""
    where = " AND ".join([s for s in (filters, coming_soon, release_date, rating) if s])
    if where:
        where = f"WHERE {where}"
    return (
        f"SELECT {','.join(APP_SNIPPET_FIELDS)} "
        + f"FROM apps "
        + f"{where} "
        + f"{order} "
        + f"LIMIT {limit} OFFSET {offset}"
    )


def build_filters_sql(filters: [dict, None]) -> str:
    """Constructs sql statement from each key. Then merges them with INTERSECT string."""
    if not filters:
        return ""
    tag_sql = ""
    genre_sql = ""
    category_sql = ""

    tags = ",".join([str(i) for i in filters["tags"]])
    genres = ",".join([str(i) for i in filters["genres"]])
    categories = ",".join([str(i) for i in filters["categories"]])

    if filters["tags"]:
        tag_sql = f"SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN ({tags})"

    if filters["genres"]:
        genre_sql = f"SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN ({genres})"

    if filters["categories"]:
        category_sql = f"SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN ({categories})"

    # Filter empty sql strings and join them
    combined_tables = " INTERSECT ".join([s for s in [tag_sql, genre_sql, category_sql] if s])
    if combined_tables:
        return f"app_id IN ({combined_tables})"
    else:
        return ""


def build_order_sql(order: dict) -> str:
    if not order:
        return ""
    else:
        return "ORDER BY " + ", ".join((f"{col} {direction}" for col, direction in order.items()))


def build_release_date_sql(release_date: [list, tuple]) -> str:
    if not release_date:
        return ""
    comp_sign = release_date[0]
    date_str = release_date[1]
    return f"release_date {comp_sign} {date_str}"


def build_rating_sql(rating: list) -> str:
    if not rating:
        return ""
    comp_sign = rating[0]
    value = rating[1]
    return f"rating {comp_sign} {value}"


def build_coming_soon_sql(coming_soon: [int, None]) -> str:
    """If input is None return empty string."""
    if coming_soon is None:
        return ""
    return f"coming_soon = {coming_soon}"


def get_app(app_id: int, db) -> App:
    columns = [i for i in APP_FIELDS if i not in ("tags", "genres", "categories")]

    query = db.execute(f"SELECT {','.join(columns)} FROM apps WHERE app_id=?", (app_id, )).fetchone()
    if not query:
        return None

    app_data = {}
    for i, col in enumerate(columns):
        if col in JSON_FIELDS:
            print(col)
            app_data[col] = json.loads(query[i])
        else:
            app_data[col] = query[i]

    tags = get_tags(app_id, db)
    genres = get_genres(app_id, db)
    categories = get_categories(app_id, db)

    for i in (("tags", tags), ("genres", genres), ("categories", categories)):
        app_data.update({i[0]: i[1]})

    return App(app_data)


def get_app_ids(db) -> list[int]:
    """Returns all app_ids in apps table"""
    applist_query = db.execute("SELECT app_id FROM apps").fetchall()
    return [i[0] for i in applist_query]


def get_tags(app_id: int, db) -> list[dict]:
    """returns -> [{'id': value, 'name': value, 'votes': value}, ...]"""
    tags = []
    ids_votes = db.execute("SELECT DISTINCT tag_id, votes FROM apps_tags WHERE app_id = ?", (app_id, )).fetchall()

    if not ids_votes:
        return None

    for i in ids_votes:
        _id = i[0]
        votes = i[1]

        tag = {}
        tag["id"] = _id
        tag["name"] = db.execute("SELECT name FROM tags WHERE tag_id = ?", (_id,)).fetchone()[0]
        tag["votes"] = votes

        tags.append(tag)
    # id, votes, name
    return tags


def get_genres(app_id: int, db) -> dict:
    """returns -> {name: id}"""
    genres = db.execute("""
        SELECT name, genre_id FROM genres
        WHERE genre_id IN (
            SELECT genre_id FROM apps_genres
            WHERE app_id = :app_id
        )""", {"app_id": app_id}
    ).fetchall()
    # name : id
    return {i[0]: i[1] for i in genres}


def get_categories(app_id: int, db) -> dict:
    """returns -> {name: id}"""
    categories = db.execute("""
        SELECT name, category_id FROM categories
        WHERE category_id IN (
            SELECT category_id FROM apps_categories
            WHERE app_id = :app_id
        )""", {"app_id": app_id}
    ).fetchall()
    #  name : id
    return {i[0]: i[1] for i in categories}


def get_non_game_apps(db) -> list[int]:
    """Returns list of app_ids"""
    result = db.execute("SELECT app_id FROM non_game_apps").fetchall()
    return [i[0] for i in result]


def get_failed_requests(where: str, db) -> list[dict]:
    """returns -> [{app_id: int, api_provider: str, error: str, status_code: [int, None]}, ...]"""
    sql = f"SELECT app_id, api_provider, error, status_code FROM failed_requests {where}"

    results = db.execute(sql).fetchall()
    failed_requests = []

    if not results:
        return failed_requests

    for i in results:
        app = {
            "app_id": i[0],
            "api_provider": i[1],
            "error": i[2],
            "status_code": i[3]
        }
        failed_requests.append(app)
    return failed_requests


def check_column(col: str):
    """Checks if column's name is in AppSnippet fields."""
    if col not in APP_SNIPPET_FIELDS:
        raise ValueError(f"{col} is not a valid column to order by.")


def init_db(db):
    """Executes init script"""
    with open(INIT_FILE) as f:
        db.executescript(f.read())


def print_table(table: str, db):
    """Prints each row in the table"""
    table = db.execute(f"SELECT * FROM {table}")
    for row in table.fetchall():
        print(row)


def print_columns(table, db):
    """Prints every column name in the apps table"""
    print("Columns: ")
    columns = db.execute(f"PRAGMA table_info({table})").fetchall()
    for i in columns:
        print(i)


class Connection:
    """Context manager for database"""
    def __init__(self, database: str):
        self.con = sqlite3.connect(database)

    def __enter__(self):
        return self.con.cursor()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.con.commit()
        self.con.close()
