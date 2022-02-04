import os
import sqlite3

from appdata import AppData

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)

database = os.path.join(current_dir, "apps.db")


def insert_app(app: AppData):
    con = sqlite3.connect(database)
    cur = con.cursor()
    cur.execute(f"""
        INSERT INTO apps (
            app_id, name, price,
            release_date, coming_soon,
            developers, publishers,
            owner_count, positive_reviews, negative_reviews,
            about_the_game, short_description, detailed_description,
            website, header_image, screenshots,
            languages, windows, mac, linux
        )
        VALUES (
            {app.app_id}, {app.name}, {app.price},
            {app.release_date}, {app.coming_soon},
            {app.developers}, {app.publishers},
            {app.owner_count}, {app.positive_reviews}, {app.negative_reviews},
            {app.about_the_game}, {app.short_description}, {app.detailed_description},
            {app.website}, {app.header_image}, {app.screenshots},
            {app.languages}, {app.windows}, {app.mac}, {app.linux}
        )
        """)
    # TODO update tags genres, categories amd their mappings
    con.commit()
    con.close()


def get_applist(order_by, filters, offset, batchsize) -> list[AppData]:
    """\
    Returns list of app objects.
    ordery_by: ORDER BY,
    filters: WHERE,
    batchsize: LIMIT
    offset: OFFSET
    """
    # sqlite3
    #  LIMIT and OFFSET
    # EXAMPLE:
    # batchsize = 1000
    # offset = 0
    # while True:
    #     c.execute(
    #         'SELECT words FROM testWords ORDER BY somecriteria LIMIT ? OFFSET ?',
    #         (batchsize, offset))
    #     batch = list(c)
    #     offset += batchsize
    #     if not batch:
    #         break
    pass




def get_new_and_trending(cursor: sqlite3.Cursor):
    cursor.execute("""
    SELECT app FROM apps
    ORDER BY app.release_date, app.positive_reviews DESC""")



def main():
    con = sqlite3.connect(database)
    cur = con.cursor()

    result = cur.execute("SELECT * FROM apps")
    print(result.fetchall())

if __name__ == "__main__":
    main()