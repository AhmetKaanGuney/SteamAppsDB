"""Web API for Steam apps database"""
import time
import json
import sys
from flask import (
    Flask,
    request,
    render_template,
    jsonify
)

try:
    from .db.database import (
        get_app_details,
        get_applist,
        Connection,
        APPS_DB_PATH
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
        APPS_DB_PATH
    )

    from db.appdata import (
        AppDetails,
        AppSnippet
    )


app = Flask(__name__)


@app.route("/GetAppDetails/<int:app_id>")
def app_details(app_id):
    with Connection(APPS_DB_PATH) as db:
        return get_app_details(app_id, db).json(indent=None)


# http://127.0.0.1:5000/GetAppList?filters=<tag=1,2,3&genre>&<order_by>

@app.route("/GetAppList")
def app_list():
    BATCH_SIZE = 20
    print("<== APP LIST ==>")
    print("Request URL: ", request.url)
    query = json.loads(request.json)
    print("Request JSON: ", query)

    start = time.perf_counter()

    with Connection(APPS_DB_PATH) as db:
        app_list = get_applist(query["filters"], query["order"], BATCH_SIZE, query["index"], db)

        stop = time.perf_counter()
        print("Time took: ", stop - start, " secs.")
        print("<==============>")

        return jsonify(app_list)

@app.route("/", methods=["GET"])
def api_doc():
    return render_template("api.md")

