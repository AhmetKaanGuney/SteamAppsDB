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
</pre>

