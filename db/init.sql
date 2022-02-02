-- APPS
CREATE TABLE IF NOT EXISTS apps (
    app_id INTEGER PRIMARY KEY,
    name TEXT,
    price INTEGER,
    release_date TEXT,
    developer TEXT,
    publisher TEXT,
    owner_count INTEGER,
    positive_reviews INTEGER,
    negative_reviews INTEGER,
    languages TEXT,
    header_image TEXT,
    website TEXT
);
-- TAGS
CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY,
    tag_name TEXT
);
-- GENRES
CREATE TABLE IF NOT EXISTS genres (
    genre_id INTEGER PRIMARY KEY,
    genre_name TEXT
);
-- APP <-> TAGS MAP
CREATE TABLE IF NOT EXISTS apps_tags (
    app_id INTEGER,
    tag_id INTEGER
);
-- APP <-> GENRES MAP
CREATE TABLE IF NOT EXISTS apps_genres (
    app_id INTEGER,
    genre_id INTEGER
);