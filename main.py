"""Web API for Steam apps database"""
import time
import json
import sys
from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    abort
)

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


@app.route("/GetAppDetails/<int:app_id>")
def app_details(app_id):
    start = time.perf_counter()
    with Connection(APPS_DB_PATH) as db:
        app_details = get_app_details(app_id, db).json(indent=None)

    stop = time.perf_counter()

    print("<==============>")
    print(f"Time took: {stop - start:.1f} secs.")
    print("<==============>")
    return app_details


@app.route("/GetAppList")
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
def api_doc():
    return render_template("api.md")


# Server failed requests
@app.route("/GetFailedRequests")
def failed_requests():
    with Connection(APPS_DB_PATH) as db:
        failed_requests = get_failed_requests(None, db)

    return jsonify(failed_requests)


@app.route("/GetNonGameApps")
def non_game_apps():
    with Connection(APPS_DB_PATH) as db:
        non_game_apps = get_non_game_apps(db)

    return jsonify(non_game_apps)