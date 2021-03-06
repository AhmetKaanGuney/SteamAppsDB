-- APPS
CREATE TABLE IF NOT EXISTS apps (
    app_id INTEGER PRIMARY KEY,
    name TEXT,
    price INTEGER,
    release_date TEXT,
    coming_soon INT,
    developers TEXT,
    publishers TEXT,
    owner_count INTEGER,
    rating INTEGER,
    positive_reviews INTEGER,
    negative_reviews INTEGER,
    about_the_game TEXT,
    short_description TEXT,
    detailed_description TEXT,
    website TEXT,
    header_image TEXT,
    screenshots TEXT,
    languages TEXT,
    windows INTEGER,
    mac INTEGER,
    linux INTEGER
);
-- APPS OVER MILLION
CREATE TABLE IF NOT EXISTS apps_over_million (
    app_id INTEGER PRIMARY KEY
);
-- TAGS
CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    name UNIQUE
);
-- GENRES
CREATE TABLE IF NOT EXISTS genres (
    genre_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);
-- CATEGORIES
CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT UNIQUE
);
-- APP <-> TAGS MAP
CREATE TABLE IF NOT EXISTS apps_tags (
    app_id INTEGER,
    tag_id INTEGER,
    votes INTEGER
);
-- APP <-> GENRES MAP
CREATE TABLE IF NOT EXISTS apps_genres (
    app_id INTEGER,
    genre_id INTEGER
);
-- APP <-> CATEGORIES MAP
CREATE TABLE IF NOT EXISTS apps_categories (
    app_id INTEGER,
    category_id INTEGER
);
-- NON-GAME APPS
CREATE TABLE IF NOT EXISTS non_game_apps (
    app_id INTEGER UNIQUE
);
-- FAILED REQUESTS
CREATE TABLE IF NOT EXISTS failed_requests (
    app_id PRIMARY KEY,
    api_provider TEXT,
    error TEXT,
    status_code INTEGER
);