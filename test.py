import json
from db.database import (
    init_db, get_applist, Connection, insert_app
    )
from db.appdata import AppDetails, AppSnippet


with open("./test/mock_data.json", "r") as f:
    mock_data = json.load(f)


with Connection(":memory:") as db:
    init_db(db)
    app1, app2, app3 = mock_data[0], mock_data[1], mock_data[2]
    for i in [app1, app2, app3]:
        insert_app(AppDetails(i), db)


    filters = {
        "tags": [],
        "genres": [],
        "categories": []
    }
