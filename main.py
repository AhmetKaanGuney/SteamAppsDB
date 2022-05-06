"""Web API for Steam apps database"""
import time
import json
import sqlite3
from flask import (
    Flask,
    request,
    render_template,
    jsonify,
    abort,
    Response,
    make_response
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from colorama import (init as init_colorama, Fore as color)

try:
    from .db.database import (
        get_app,
        get_applist,
        Connection,
        APPS_DB_PATH,
        get_failed_requests,
        get_non_game_apps
    )

    from .db.appdata import (
        App,
        AppSnippet
    )
    from .image_server import (
        IMAGES_PATH, DEBUG_IMAGES_PATH,
        load_images, gen_frames_v1, gen_frames_v2,
    )
except ImportError:
    from db.database import (
        get_app,
        get_applist,
        Connection,
        APPS_DB_PATH,
        get_failed_requests,
        get_non_game_apps
    )

    from db.appdata import (
        App,
        AppSnippet
    )
    from image_server import (
        IMAGES_PATH, DEBUG_IMAGES_PATH,
        load_images, gen_frames_v1, gen_frames_v2,
    )

# Load db into memory
source = sqlite3.connect(APPS_DB_PATH, check_same_thread=False, uri=True)
MEMORY_CON = sqlite3.connect(':memory:', check_same_thread=False)
source.backup(MEMORY_CON)
source.close()

APP_COUNT = MEMORY_CON.cursor().execute("SELECT COUNT(*) from apps").fetchone()[0]

init_colorama(autoreset=True)

app = Flask(__name__)
CORS(app)

daily_limit = 5000

# limiter = Limiter(
#     app,
#     key_func=get_remote_address,
#     default_limits=[f"{daily_limit}/day", "1/second"])

# sql_limit = limiter.shared_limit(f"{daily_limit}/day, 1/second", "sql")

images_obj = {
    'index': 0,
    'list': load_images(IMAGES_PATH)
}
debug_images_obj = {
    'index': 0,
    'list': load_images(DEBUG_IMAGES_PATH)
}

@app.route("/imageFeed/v1")
def image_feed_v1():
    args = request.args
    debug = int(args.get('debug', default=0, type=int))
    if debug:
        img_bin = gen_frames_v1(debug_images_obj)
    else:
        img_bin = gen_frames_v1(images_obj)

    response = make_response(img_bin)
    response.headers.set('Content-Type', 'image/jpeg')
    return response


@app.route("/imageFeed/v2")
def image_feed_v2():
    args = request.args
    fps = args.get('fps', default=20, type=int)
    debug = int(args.get('debug', default=0, type=int))

    return Response(
        gen_frames_v2(fps, debug),
        mimetype='multipart/x-mixed-replace;boundary=frame'
    )


@app.route("/GetAppDetails/<int:app_id>")
# @sql_limit
def app_details(app_id):
    start = time.perf_counter()

    with Connection(APPS_DB_PATH) as db:
        app = get_app(app_id, db)
        if app:
            return app.json(indent=None)
        else:
            return abort(404)

    stop = time.perf_counter()

    print(color.YELLOW + f"Time took: {stop - start:.1f} secs.")
    return app


@app.route("/GetAppList", methods=['GET'])
# @sql_limit
def app_list():
    args = request.args
    try:
        index = int(args.get("index", default=0))
        limit = int(args.get("limit", default=20))
    except ValueError as e:
        print(color.RED + type(e).__name__ + ": " + str(e))
        abort(400)

    # Filters
    tags = str_to_list(args.get("tags", default=""))
    genres = str_to_list(args.get("genres", default=""))
    categories = str_to_list(args.get("categories", default=""))
    filters = {
        "tags": tags,
        "genres": genres,
        "categories": categories
    }

    order_params = args.get("order", default="owner_count,DESC").split(",")
    order = parse_order_params(order_params)

    coming_soon = args.get("coming_soon", default=None)
    release_date = args.get("release_date", default=None)
    rating = args.get("rating", default=None)

    if release_date:
        release_date = [i.strip() for i in release_date.split(',')]
    if rating:
        rating = [i.strip() for i in rating.split(',')]

    if limit > 20:
        e = {
            "name": "Batch Limit Error",
            "description": f"Error: limit={limit} cannot be greater than 20",
        }
        print(color.RED + e.name + ": " + e.description)
        abort(400)

    start = time.perf_counter()

    try:
        app_list = get_applist(
            filters, order, coming_soon, release_date, rating, index, limit, MEMORY_CON.cursor()
        )
    except (ValueError, TypeError) as e:
        print(color.RED + type(e).__name__ + ": " + str(e))
        abort(400)

        stop = time.perf_counter()
        print(color.YELLOW + f"Time took: {stop - start:.1f} secs.")

        for i in app_list:
            tag_list = i["tags"]
            if not tag_list:
                continue
            tags = [i["id"] for i in tag_list]


    return jsonify(app_list)


@app.route("/")
# @sql_limit
def index():
    return render_template("api.html")


@app.route("/GetAppCount")
# @sql_limit
def app_count():
    return jsonify(APP_COUNT)


@app.errorhandler(HTTPException)
def handle_exception(e):
    print()
    response = e.get_response()
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description
    })
    response.content_type = "application/json"
    return response


def str_to_list(param: str):
    if param:
        return [int(i) for i in param.split(",")]
    else:
        return []


def parse_order_params(order_params) -> dict:
    order = {}
    i = 0
    while i < len(order_params) - 1:
        order[order_params[i]] = order_params[i+1]
        i += 2
    return order


# Utilities
# @app.route("/GetFailedRequests")
# @sql_limit
# def failed_requests():
#     with Connection(APPS_DB_PATH) as db:
#         failed_requests = get_failed_requests(None, db)
#     return jsonify(failed_requests)


# @app.route("/GetNonGameApps")
# @sql_limit
# def non_game_apps():
#     with Connection(APPS_DB_PATH) as db:
#         non_game_apps = get_non_game_apps(db)
#     return jsonify(non_game_apps)
