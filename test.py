import json
import unittest
import sqlite3

from db.database import (
    init_db, get_applist, Connection, insert_app,
    check_filters, check_order, check_release_date,
    build_filters_sql, build_order_sql, build_release_date_sql,
    build_coming_soon_sql, build_combined_sql, get_tags, get_app_ids
    )
from db.appdata import AppDetails, AppSnippet


with open("./test/mock_data.json", "r") as f:
    mock_data = json.load(f)

class TestCheckFunctions(unittest.TestCase):
    def test_filters_input_type(self):
        for i in ([], "", 1):
            with self.assertRaises(TypeError):
                check_filters(i)

    def test_filters_input_key(self):
        with self.assertRaises(ValueError):
            check_filters({"invalid_key1": []})

    def test_filters_input_value(self):
        keys = ("tags", "genres", "categories")
        for k in keys:
            with self.assertRaises(TypeError):
                check_filters({k: {}})

        for k in keys:
            with self.assertRaises(TypeError):
                check_filters({k: ["should_be_int"]})

    def test_check_order_input_type(self):
        for i in ([], "", 0, True):
            with self.assertRaises(TypeError):
                check_order(i)

    def test_check_order_input_values(self):
        invalid_column = {"invalid_column": "DESC"}
        invalid_direction = {"release_date": "DIRECTION"}
        for i in (invalid_column, invalid_direction):
            with self.assertRaises(ValueError):
                check_order(i)

    def test_check_release_date(self):
        invalid_comp_sign = ["invalid", "0000-00-00"]
        invalid_date_str = ["=", ";DELETE * FROM apps;"]
        for i in (invalid_comp_sign, invalid_date_str):
            with self.assertRaises(ValueError):
                check_release_date(i)


class TestBuildFunctions(unittest.TestCase):
    """
    filters = {
        tags: 1, 2
        genres: 3, 4
        categories: 5, 6
    }
    order = {
        "release_date": "ASC",
        "positive_reviews": "DESC"
    }
    release_date = ["!=", '']
    coming_soon = 0
    limit = 10
    offset = 0
    """

    def test_build_combined_sql(self):
        filters_sql = (
            "app_id IN "
            "("
            "SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN (1, 2) "
            "INTERSECT "
            "SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN (3, 4) "
            "INTERSECT "
            "SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN (5, 6)"
            ")"
        )
        release_date_sql = "release_date != ''"
        coming_soon_sql = "coming_soon = 0"
        order_sql = "ORDER BY price ASC, release_date DESC"
        limit = 10
        offset = 0
        columns = ",".join(AppSnippet().__attributes__)
        combined = build_combined_sql(filters_sql, order_sql, coming_soon_sql, release_date_sql, offset, limit)
        expected_str = (
            f"SELECT {columns} FROM apps "
            + f"WHERE {filters_sql} "
            + f"AND {coming_soon_sql} AND {release_date_sql} "
            + order_sql
            + f" LIMIT {limit} OFFSET {offset}"
        )
        self.assertEqual(combined, expected_str)

    def test_build_filter_sql(self):
        self.assertEqual(build_filters_sql(""), "")

        tags_only = {"tags": [1, 2, 3], "genres": [], "categories": []}
        genres_only = {"tags": [], "genres": [1, 2, 3,], "categories": []}
        categories_only = {"tags": [], "genres": [], "categories": [1, 2, 3]}
        tags_and_genres = {"tags": [1, 2, 3], "genres": [1, 2, 3], "categories": []}
        tags_and_categories = {"tags": [1, 2, 3], "genres": [], "categories": [1, 2, 3]}
        genres_and_categories = {"tags": [], "genres": [1, 2, 3], "categories": [1, 2, 3]}
        all_filters = {"tags": [1, 2, 3], "genres": [1, 2, 3], "categories": [1, 2, 3]}

        self.assertEqual(
            build_filters_sql(tags_only),
            "app_id IN (SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN (1,2,3))"
        )
        self.assertEqual(
            build_filters_sql(genres_only),
            "app_id IN (SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN (1,2,3))"
        )
        self.assertEqual(
            build_filters_sql(categories_only),
            "app_id IN (SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN (1,2,3))"
        )
        self.assertEqual(
            build_filters_sql(tags_and_genres), (
                "app_id IN (SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN (1,2,3)"
                " INTERSECT SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN (1,2,3))"
            )
        )
        self.assertEqual(
            build_filters_sql(tags_and_categories), (
                "app_id IN (SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN (1,2,3)"
                " INTERSECT SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN (1,2,3))"
            )
        )
        self.assertEqual(
            build_filters_sql(genres_and_categories), (
                "app_id IN (SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN (1,2,3)"
                " INTERSECT SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN (1,2,3))"
            )
        )
        self.assertEqual(
            build_filters_sql(all_filters), (
                "app_id IN (SELECT DISTINCT app_id FROM apps_tags WHERE tag_id IN (1,2,3)"
                " INTERSECT SELECT DISTINCT app_id FROM apps_genres WHERE genre_id IN (1,2,3)"
                " INTERSECT SELECT DISTINCT app_id FROM apps_categories WHERE category_id IN (1,2,3))"
            )
        )

    def test_build_order_sql(self):
        self.assertEqual(build_order_sql(None), "")

        single_order = {"release_date": "ASC"}
        multiple_order = {
            "positive_reviews": "DESC",
            "release_date": "ASC",
            "price": "DESC"
        }
        self.assertEqual(build_order_sql(single_order),
            "ORDER BY release_date ASC"
        )
        self.assertEqual(build_order_sql(multiple_order),
            "ORDER BY positive_reviews DESC, release_date ASC, price DESC"
        )

    def test_build_release_date_sql(self):
        self.assertEqual(build_release_date_sql(""), "")

        release_date = ["<", "2000-01-01"]
        self.assertEqual(build_release_date_sql(release_date), "release_date < 2000-01-01")

    def test_build_coming_soon_sql(self):
        self.assertEqual(build_coming_soon_sql(0), "coming_soon = 0")
    #     self.assertEqual(build_coming_soon_sql(1), "coming_soon = 1")



# class TestGetAppList():
#     def setUp(self):
#         con = sqlite3.connect(":memory:")
#         self.db = con.cursor()

#         init_db(self.db)
#         for app in mock_data:
#             insert_app(AppDetails(app), self.db)

#         self.app_ids = get_app_ids(self.db)
#         self.tags = [
#             {'id': 1, 'name': 'T1'},
#             {'id': 2, 'name': 'T2'},
#         ]

#     def tearDown(self):
#         self.db.close()

#     def test_get_applist(self):
#         # TODO automate single tags genres and catregories input
#         all_apps = mock_data
#         all_query = get_applist({}, {}, None, None, 0, 10, self.db)
#         applist = ((i["app_id"], i["name"]) for i in all_query)

#         for i in all_apps:
#             app = (i["app_id"], i["name"])
#             self.assertIn(app, applist)

#         tag_id = 2
#         filters = {
#             "tags": [tag_id],
#             "genres": [],
#             "categories": []
#         }
#         order = {"release_date": "DESC"}
#         coming_soon = None
#         release_date = None
#         offset = 0
#         limit = 10
#         applist = get_applist(filters, order, coming_soon, release_date, offset, limit, self.db)

#         for app in applist:
#             tags_ids = [i["id"] for i in app["tags"]]
#             self.assertIn(tag_id, tags_ids)





if __name__ == "__main__":
    unittest.main()
