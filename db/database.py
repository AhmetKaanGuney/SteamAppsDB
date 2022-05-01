import os
import sqlite3
import json
import logging

try:
    from appdata import AppDetails, AppSnippet
except ImportError:
    from .appdata import AppDetails, AppSnippet


logging.basicConfig(level=logging.CRITICAL)

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
APPS_DB_PATH = os.path.join(current_dir, "apps.db")
INIT_FILE = os.path.join(current_dir, "init_apps.sql")

APP_SNIPPET_FIELDS = AppDetails().__attributes__
APP_SNIPPET_FIELDS = AppSnippet().__attributes__

JSON_FIELDS = ("developers", "publishers", "screenshots")


def insert_app(app_dets: AppDetails, db):
    """Inserts AppDetails object to database"""
    app_id = app_dets.app_id
    data = {}
    # Covert fields that are dictionary to json
    # and store them
    for k, v in app_dets.items():
        if k in JSON_FIELDS:
            data[k] = json.dumps(v)
        else:
            data[k] = v

    db.execute("""
        REPLACE INTO apps
        VALUES (
            :app_id, :name, :price,
            :release_date, :coming_soon,
            :developers, :publishers,
            :owner_count, :rating, :positive_reviews, :negative_reviews,
            :about_the_game, :short_description, :detailed_description,
            :website, :header_image, :screenshots,
            :languages, :windows, :mac, :linux
        )""", data)

    if app_dets.genres:
        for name, _id in app_dets.genres.items():
            db.execute("REPLACE INTO genres VALUES (:genre_id, :name)",
                                            {"genre_id": _id, "name": name})
            db.execute("REPLACE INTO apps_genres VALUES (:app_id, :genre_id)",
                                                {"app_id": app_id, "genre_id": _id})

    if app_dets.categories:
        for name, _id in app_dets.categories.items():
            db.execute("REPLACE INTO categories VALUES (:category_id, :name)",
                                                {"category_id": _id, "name": name})
            db.execute("REPLACE INTO apps_categories VALUES (:app_id, :category_id)",
                                                    {"app_id": app_id, "category_id": _id})

    # Tags don't come with ids. they come with vote count for that tag
    if app_dets.tags:
        for name, votes in app_dets.tags.items():
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


def get_app_details(app_id: int, db) -> AppDetails:
    query = db.execute("SELECT * FROM apps WHERE app_id=?", (app_id, )).fetchone()
    if not query:
        return None

    table_info = db.execute("PRAGMA table_info(apps)").fetchall()
    # Get column names
    columns = (i[1] for i in table_info)

    app_data = {}
    for i, col in enumerate(columns):
        if col in JSON_FIELDS:
            app_data[col] = json.loads(query[i])
        else:
            app_data[col] = query[i]

    tags = get_tags(app_id, db)
    genres = get_genres(app_id, db)
    categories = get_categories(app_id, db)

    for i in (("tags", tags), ("genres", genres), ("categories", categories)):
        app_data.update({i[0]: i[1]})

    return AppDetails(app_data)


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
    """Takes input in two forms.
    1. With parentheses:
        Checks each column name in the left and right of the operator
        If column name isn't in AppSnippet fields raises error.
    2. Without parentheses:
        Checks if column's name is in AppSnippet fields.
    """
    if col.startswith("(") and col.endswith(")"):
        operators = ("+", "-", "/", "*")
        content: str = col[1:-1]
        cols = [content]

        for op in operators:
            i = 0
            op_detected = False
            while True:
                if i >= len(cols):
                    break
                col = cols[i]

                for index, char in enumerate(col):
                    if char == op:
                        # Split str in half from the operator
                        left = cols[i][:index]
                        right = cols[i][index + 1:]
                        # Insert items inplace
                        cols[i] = left
                        cols.insert(i + 1, right)
                        op_detected = True

                if op_detected:
                    # reset checking
                    i = 0
                    op_detected = False
                else:
                    i += 1

        column_names = [i.strip() for i in cols]
        for i in column_names:
            if i not in APP_SNIPPET_FIELDS:
                raise ValueError(f"{i} is not a valid column to order by.")
    else:
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


def print_columns():
    """Prints every column name in the apps table"""
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
    mock_data = os.path.join(parent_dir, "test/mock_data.json")
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
        order = {
            "price": "ASC",
            "release_date": "DESC"
        }
        limit = 20
        offset = 0
        applist = get_applist(filters, order, limit, offset, db)
        print("APPLIST: \n", applist)

        for i in range(5):
            insert_non_game_app(i, db)

        print("Insert non-game-app")
        print_table("non_game_apps", db)

        print("Insert rejected-app")
        print_table("rejected_apps", db)

        non_game_apps = get_non_game_apps(db)
        print("Non game apps: ", non_game_apps)
