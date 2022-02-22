"""Web API for Steam apps database"""
import time
from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    abort
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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


@app.route("/GetAppList")
@sql_limit
def app_list():
    BATCH_SIZE = 20

    if request.json:
        query = request.json
    else:
        return abort(400, "JSON filed is empty!")

    filters = query["filters"]
    order = query["order"]
    index = query["index"]

    start = time.perf_counter()

    with Connection(APPS_DB_PATH) as db:
        try:
            app_list = get_applist(filters, order, BATCH_SIZE, index, db)
        except (ValueError, TypeError) as e:
            abort(400, e)

        stop = time.perf_counter()
        print("<==============>")
        print(f"Time took: {stop - start:.1f} secs.")
        print("<==============>")
        return jsonify(app_list)

@app.route("/", methods=["GET"])
@sql_limit
def api_doc():
    return render_template("api.md")


# Server failed requests
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
