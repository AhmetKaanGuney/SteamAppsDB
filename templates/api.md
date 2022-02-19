<h1>API DOCUMENTATION</h1>
<br>
<pre>
GET /GetAppList:
    json body:
    {
        "filters": {
            "tags": [],
            "genres": [],
            "categories": []
        },
        "order": {
            "column_name": "ASC" or "DESC",
        },
        "index": current index
    }
Return format:
Applist is list of AppSnippet objects.
AppSnippet():
    app_id  : int
    name    : str
    price   : int

    release_date: str
    coming_soon : bool

    positive_reviews: int
    negative_reviews: int
    owner_count     : int

    header_image: str

    windows : bool
    mac     : bool
    linux   : bool

    tags    : list[dict]

Tags Example :
[
    {
        "id"    : 10,
        "name"  : "example",
        "votes" : 300
    },
    {
        "id"    : 56,
        "name"  : "example2",
        "votes" : 26
    }
]

AppDetails():
    app_id  : int
    name    : str
    price   : int

    release_date: str
    coming_soon : bool

    developers: list[str]
    publishers: list[str]

    tags        : list[dict]
    genres      : dict
    categories  : dict

    owner_count     : int
    positive_reviews: int
    negative_reviews: int

    about_the_game      : str
    short_description   : str
    detailed_description: str

    website     : str
    header_image: str
    screenshots : list[dict]

    languages: str

    windows : bool
    mac     : bool
    linux   : bool

</pre>

