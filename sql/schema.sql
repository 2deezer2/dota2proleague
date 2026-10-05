CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.pro_matches (
    match_id bigint PRIMARY KEY,
    start_time bigint NOT NULL,
    payload jsonb NOT NULL,
    discovered_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS raw.match_payloads (
    match_id bigint PRIMARY KEY REFERENCES raw.pro_matches(match_id),
    payload jsonb NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS raw.heroes (
    hero_id integer PRIMARY KEY,
    name text NOT NULL
);
