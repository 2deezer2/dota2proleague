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
CREATE TABLE IF NOT EXISTS raw.leagues (
    league_id bigint PRIMARY KEY,
    name text NOT NULL,
    family text,
    tier_source text NOT NULL DEFAULT 'user_selected_family',
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS raw.team_profiles (
    team_id bigint PRIMARY KEY,
    payload jsonb NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS raw.player_profiles (
    account_id bigint PRIMARY KEY,
    payload jsonb NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now()
);
