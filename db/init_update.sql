-- NON-GAME APPS
CREATE TABLE IF NOT EXISTS non_game_apps (
    app_id INTEGER UNIQUE
);
-- REJECTED APPS
CREATE TABLE IF NOT EXISTS rejected_apps (
    app_id INTEGER UNIQUE
);
-- TIMED OUT REQUESTS
CREATE TABLE IF NOT EXISTS timed_out_requests (
    app_id PRIMARY KEY,
    provider TEXT
);