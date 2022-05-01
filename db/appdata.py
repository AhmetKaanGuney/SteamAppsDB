from dataclasses import dataclass
import json


@dataclass
class DataContainer:
    """Metaclass for customized dataclass"""

    def __init__(self, data=None):
        if data:
            self.update(data)

    def update(self, attributes: dict):
        """Updates existing attributes. Raises error if attribute doesn't exists."""
        # Check for typos
        for a in attributes:
            if a not in self.__attributes__:
                raise AttributeError(f"'{type(self).__name__}' object has no attribute '{a}'")

        self.__dict__.update(attributes)

    @property
    def __attributes__(self) -> list[str]:
        """Returns public attributes, that are not callable or dunder methods."""
        attributes = []
        for a in dir(self):
            if not (a.startswith("_") or callable(getattr(self, a))):
                attributes.append(a)
        return attributes

    def items(self) -> list[tuple]:
        items_view = []
        for a in self.__attributes__:
            items_view.append((a, self.__getattribute__(a)))
        return items_view

    def as_dict(self) -> dict:
        """Returns atributes as key value pairs."""
        obj = {}
        for a in self.__attributes__:
            obj[a] = self.__getattribute__(a)
        return obj

    def json(self, indent=0) -> str:
        output = {}
        for a in self.__attributes__:
            output[a] = self.__getattribute__(a)
            json.dumps(output)
        return json.dumps(output, indent=indent)

    def __getitem__(self, key):
        return self.__getattribute__(key)

    def __repr__(self) -> str:
        return str(self.json(indent=2))


class App(DataContainer):
    """An interface for app details"""
    app_id: int = 0
    name: str = ""
    price: int = None

    release_date: str = ""
    coming_soon: bool = False

    developers: list[str] = None
    publishers: list[str] = None

    tags: list[dict] = None
    genres: dict = None
    categories: dict = None

    owner_count: int = 0
    rating: int = 0
    positive_reviews: int = 0
    negative_reviews: int = 0

    about_the_game: str = ""
    short_description: str = ""
    detailed_description: str = ""

    website: str = ""
    header_image: str = ""
    screenshots: list[dict] = None

    languages: str = ""

    windows: bool = False
    mac: bool = False
    linux: bool = False

    @staticmethod
    def get_fields():
        """Returns all sql columns"""
        return (
            "app_id", "name", "price",
            "release_date", "coming_soon",
            "developers", "publishers",
            "tags", "genres", "categories",
            "owner_count", "rating",
            "positive_reviews", "negative_reviews",
            "about_the_game", "short_description", "detailed_description",
            "website", "header_image", "screenshots",
            "languages",
            "windows", "mac", "linux"
        )



class AppSnippet(DataContainer):
    """An interface for holding app snippet data
    This interface's fields are based of database columns.
    Why there are no 'tags', 'genres' or 'categories' fields?
    These fields are intentionally omitted by default.
    Because AppSnippet().__attributes__ is designed to be called for specifying
    the column names while querying. So having these field would cause an errors
    because these columns don't exists in the 'apps' table.
    The need to be called seperately.
    """
    app_id: int = None
    name: str = ""
    price: int = None

    release_date: str = ""
    coming_soon: bool = False

    owner_count: int = 0
    rating: int = 0
    positive_reviews: int = 0
    negative_reviews: int = 0

    header_image: str = ""

    windows: bool = False
    mac: bool = False
    linux: bool = False

    @staticmethod
    def get_fields():
        return (
            "app_id", "name", "price",
            "release_date", "coming_soon",
            "owner_count", "rating",
            "positive_reviews", "negative_reviews",
            "header_image",
            "windows", "mac", "linux"
        )


if __name__ == "__main__":
    app1_dict = {
        "app_id": 1847860,
        "name": "Jigsaw Souls",
        "owner_count": "0 .. 20,000",
        "price": None,
        "tags": [],
        "positive_reviews": 0,
        "negative_reviews": 0,
        "detailed_description": "",
        "about_the_game": "",
        "short_description": "A fun puzzle about Daltoniel.",
        "header_image": "",
        "website": None,
        "developers": [
        "Mr Tomatus"
        ],
        "publishers": [
        "Mr Tomatus"
        ],
        "categories": [
        {
            "id": 2,
            "description": "Single-player"
        }
        ],
        "genres": [
        {
            "id": "4",
            "description": "Casual"
        }
        ],
        "screenshots": [
        {
            "id": 0,
            "path_thumbnail": "",
            "path_full": ""
        } ],
        "languages": "",
        "release_date": "2022-02-11",
        "coming_soon": True,
        "windows": True,
        "mac": False,
        "linux": False
    }
    app1 = App()
    app1.update(app1_dict)
    app1.update({"about_the_game": "TEST"})
    app1.update({"languages": ["lila", "lele", "lolo"]})
    print(app1.json(indent=2))
    app_snippet = AppSnippet()
