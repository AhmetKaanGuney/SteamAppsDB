from dataclasses import dataclass, field
import json

@dataclass
class AppData:
    """An interface for app data"""
    app_id: int = 0
    name: str = ""
    price: [int, None] = None

    release_date: str = ""
    coming_soon: bool = False

    developers: list[str] = field(default_factory=list)
    publishers: list[str] = field(default_factory=list)

    tags: list[dict] = field(default_factory=list)
    genres: list[dict] = field(default_factory=list)
    categories: list[dict] = field(default_factory=list)

    owner_count: int = 0
    positive_reviews: int = 0
    negative_reviews: int = 0

    about_the_game: str = ""
    short_description: str = ""
    detailed_description: str = ""

    website: str = ""
    header_image: str = ""
    screenshots: list[dict] = field(default_factory=list)

    languages: str = ""

    windows: bool = False
    mac: bool = False
    linux: bool = False

    def update(self, mapping: dict):
        """Dictionary update method"""
        self.__dict__.update(mapping)

    def serialize(self):
        """Retrun object as dict. JSON serializeable"""
        obj = {}
        for a in self.__attributes__:
            obj[a] = self.__getattribute__(a)
        return obj

    def json(self, indent=0):
        output = {}
        for a in self.__attributes__:
            output[a] = self.__getattribute__(a)
            json.dumps(output)
        return json.dumps(output, indent=indent)

    @property
    def __attributes__(self):
        """Returns all attributes, that are not callable or dunder methods"""
        attributes = [a for a in dir(self) if not (a.startswith("__") or callable(getattr(self, a)))]
        return attributes

    def __repr__(self):
        repr_object = {}
        for a in self.__attributes__:
            repr_object[a] = self.__getattribute__(a)

        return str(repr_object)


if __name__ == "__main__":
    app1_dict = {
        "app_id": 1847860,
        "name": "Jigsaw Souls",
        "owners": "0 .. 20,000",
        "price": None,
        "tags": [],
        "positive_reviews": 0,
        "negative_reviews": 0,
        "detailed_description": "<img src=\"https://cdn.cloudflare.steamstatic.com/steam/apps/1847860/extras/descri\u00e7ao_da_pagina_da_loja.png?t=1643226401\" /><br><br>Daltoniel in his daily routine, from working out, wearing the costumes of his favorite heroes or eating his powerful enemies in delicious meals that he prepared himself, how good is it to enjoy life being a demigod slime.<h2 class=\"bb_tag\">features</h2><br><ul class=\"bb_ul\"><li>Jigsaw puzzle having 12 cute illustrations of Daltoniel</li></ul><ul class=\"bb_ul\"><li>For each jigsaw puzzle, 3 difficulty levels can be set</li></ul><ul class=\"bb_ul\"><li>A relaxing and imersive clean Background</li></ul><ul class=\"bb_ul\"><li>Zoom in/Zoom Out</li></ul><ul class=\"bb_ul\"><li>Draggable scenario</li></ul><ul class=\"bb_ul\"><li>A bunch of game juiciness</li></ul><ul class=\"bb_ul\"><li>Relax with a comforting and exclusive lo-fi soundtrack</li></ul>",
        "about_the_game": "<img src=\"https://cdn.cloudflare.steamstatic.com/steam/apps/1847860/extras/descri\u00e7ao_da_pagina_da_loja.png?t=1643226401\" /><br><br>Daltoniel in his daily routine, from working out, wearing the costumes of his favorite heroes or eating his powerful enemies in delicious meals that he prepared himself, how good is it to enjoy life being a demigod slime.<h2 class=\"bb_tag\">features</h2><br><ul class=\"bb_ul\"><li>Jigsaw puzzle having 12 cute illustrations of Daltoniel</li></ul><ul class=\"bb_ul\"><li>For each jigsaw puzzle, 3 difficulty levels can be set</li></ul><ul class=\"bb_ul\"><li>A relaxing and imersive clean Background</li></ul><ul class=\"bb_ul\"><li>Zoom in/Zoom Out</li></ul><ul class=\"bb_ul\"><li>Draggable scenario</li></ul><ul class=\"bb_ul\"><li>A bunch of game juiciness</li></ul><ul class=\"bb_ul\"><li>Relax with a comforting and exclusive lo-fi soundtrack</li></ul>",
        "short_description": "A fun puzzle about Daltoniel, the protagonist from the Souls Saga by Pickles Entertainment. Relax resolving this jigsaw puzzle with 12 original pictures and 3 difficulty levels!",
        "supported_languages": "English<strong>*</strong>, French<strong>*</strong>, Italian<strong>*</strong>, German<strong>*</strong>, Spanish - Latin America<strong>*</strong>, Polish<strong>*</strong>, Portuguese - Brazil<strong>*</strong><br><strong>*</strong>languages with full audio support",
        "header_image": "https://cdn.akamai.steamstatic.com/steam/apps/1847860/header.jpg?t=1643226401",
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
            "path_thumbnail": "https://cdn.akamai.steamstatic.com/steam/apps/1847860/ss_d581b15836aaa6dd2457af38da9be6170b3c7fd1.600x338.jpg?t=1643226401",
            "path_full": "https://cdn.akamai.steamstatic.com/steam/apps/1847860/ss_d581b15836aaa6dd2457af38da9be6170b3c7fd1.1920x1080.jpg?t=1643226401"
        } ],
        "languages": "",
        "release_date": "2022-02-11",
        "coming_soon": True,
        "windows": True,
        "mac": False,
        "linux": False
    }
    app1 = AppData()
    app1.coming_soon = False
    app1.update({"TEST": "TEST"})
    app1.update({"LOL": ["lila", "lele", "lolo"]})
    print(app1.json(indent=2))
    # print(app1.__attributes__)