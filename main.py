"""Web API for Steam apps database"""
import json
import sys
from flask import (
    Flask,
    url_for,
    render_template,
)

from .db.database import (
    get_app_details,
    get_applist,
    Connection,
    DATABASE_PATH
    )


app = Flask(__name__)

@app.route("/GetAppDetails/<int:app_id>")
def app_details(app_id):
    with Connection(DATABASE_PATH) as db:
        app_details = get_app_details(app_id, db)
    return app_details

@app.route("/api", methods=["GET"])
def api_doc():
    return render_template("api.html") 

