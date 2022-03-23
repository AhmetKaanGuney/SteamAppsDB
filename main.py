"""Web API for Steam apps database"""
import time
import json
from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    abort
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

try:
    from .db.database import (
        get_app_details,
        get_applist,
        Connection,
        APPS_DB_PATH,
        get_failed_requests,
        get_non_game_apps
    )

    from .db.appdata import (
        AppDetails,
        AppSnippet
    )
except ImportError:
    from db.database import (
        get_app_details,
        get_applist,
        Connection,
        APPS_DB_PATH,
        get_failed_requests,
        get_non_game_apps
    )

    from db.appdata import (
        AppDetails,
        AppSnippet
    )


app = Flask(__name__)

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "1 per second"])

sql_limit = limiter.shared_limit("200/day, 10/second", "sql")


@app.route("/GetAppDetails/<int:app_id>")
@sql_limit
def app_details(app_id):
    start = time.perf_counter()

    with Connection(APPS_DB_PATH) as db:
        app = get_app_details(app_id, db)
        if app:
            return app.json(indent=None)
        else:
            return abort(404)

    stop = time.perf_counter()

    print("<==============>")
    print(f"Time took: {stop - start:.1f} secs.")
    print("<==============>")
    return app


@app.route("/GetAppList", methods=['GET'])
@sql_limit
def app_list():
    args = request.args
    print("\n", request.args.keys())

    tags = get_as_list(args.get("tags", default=""))
    genres = get_as_list(args.get("genres", default=""))
    categories = get_as_list(args.get("categories", default=""))

    filters = {
        "tags": tags,
        "genres": genres,
        "categories": categories
    }
    order_params = args.get("order", default="owner_count,DESC").split(",")
    order = {order_params[0]: order_params[1]}
    index = int(args["index"])
    limit = int(args.get("limit", default=20))

    if limit > 20:
        e = f"Error: limit={limit} cannot be greater than 20"
        abort(400, e)

    print("filters: ", filters, "\norder: ", order, "\nindex: ", index, "\nlimit: ", limit)

    start = time.perf_counter()

    with Connection(APPS_DB_PATH) as db:
        try:
            app_list = get_applist(filters, order, index, limit, db)
        except (ValueError, TypeError) as e:
            abort(400, e)

        stop = time.perf_counter()
        print("<==============>")
        print(f"Time took: {stop - start:.1f} secs.")
        print("<==============>")
    return jsonify(app_list)


@app.route("/")
@sql_limit
def index():
    return render_template("api.md")


@app.route("/GetHighlights")
def higlights():
    # get: most owned, best rated, most recent
    order = {
        "owner_count": "DESC",
        "(positive_reviews / negative_reviews)": "DESC",
        "release_date": "DESC"
    }
    offset = 0

    with Connection(APPS_DB_PATH) as db:
        try:
            highlights = get_applist(None, order, offset, 10, db)
        except (ValueError, TypeError) as e:
            abort(400, e)
    return jsonify(highlights)


@app.route("/GetFailedRequests")
@sql_limit
def failed_requests():
    with Connection(APPS_DB_PATH) as db:
        failed_requests = get_failed_requests(None, db)
    return jsonify(failed_requests)


@app.route("/GetNonGameApps")
@sql_limit
def non_game_apps():
    with Connection(APPS_DB_PATH) as db:
        non_game_apps = get_non_game_apps(db)
    return jsonify(non_game_apps)


@app.errorhandler(HTTPException)
def handle_exception(e):
    print()
    print(e.name, e.description)
    response = e.get_response()
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description
    })
    response.content_type = "application/json"
    return response


def get_as_list(param: str):
    if param:
        return [int(i) for i in param.split(",")]
    else:
        return []
