from dataclasses import dataclass

@dataclass
class AppData:
    """An interface for app data"""
    app_id: int = 0
    name: str = ""
    price: [int, None] = None

    release_date: str = ""
    coming_soon: bool = False

    developers: list[str] = None
    publishers: list[str] = None

    tags: dict = None
    genres: dict = None
    categories: dict = None

    owner_count: int = 0
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

    def __init__(self, app_data=None):
        if app_data:
            self.update(app_data)

    def update(self, attributes: dict):
        """Updates existing attributes.
        Raises error if attribute doesn't exists.
        """
        # Check for typos
        for a in attributes:
            if a not in self.__attributes__:
                raise AttributeError(f"Attribute not found: '{a}'")

        self.__dict__.update(attributes)

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

    @property
    def __attributes__(self) -> list[str]:
        """Returns all attributes, that are not callable or dunder methods."""
        attributes = [a for a in dir(self) if not (a.startswith("_") or callable(getattr(self, a)))]
        return attributes

    def __repr__(self) -> str:
        repr_object = {}
        for a in self.__attributes__:
            repr_object[a] = self.__getattribute__(a)

        return str(repr_object)


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
        "languages": "English<strong>*</strong>, French<strong>*</strong>",
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
    app1 = AppData()
    app1.update(app1_dict)
    app1.update({"about_the_game": "TEST"})
    app1.update({"languages": ["lila", "lele", "lolo"]})
    print(app1.json(indent=2))
    # print(app1.__attributes__)