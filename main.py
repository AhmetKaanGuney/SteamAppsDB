"""Web API for Steam apps database"""
import json
import sys
from flask import (
    Flask,
    request,
    render_template,
)

from .db.database import (
    get_app_details,
    get_applist,
    Connection,
    DATABASE_PATH
)

from .db.appdata import (
    AppDetails,
    AppSnippet
)


app = Flask(__name__)


@app.route("/GetAppDetails/<int:app_id>")
def app_details(app_id):
    with Connection(DATABASE_PATH) as db:
        return get_app_details(app_id, db).json(indent=None)


# http://127.0.0.1:5000/GetAppList?<filters>&<order_by>
@app.route("/GetAppList")
def app_list():
    print("APP LIST: ")
    # Default Values
    filters = {
        "tags": [],
        "genres": [],
        "categories": []
    }
    order_by = {
        "release_date": "DESC",
    }
    order = request.args.get("order_by")
    # TODO ad tags categories genres
    print(filters)
    return "Applist Response"

@app.route("/", methods=["GET"])
def api_doc():
    return render_template("api.html") 

