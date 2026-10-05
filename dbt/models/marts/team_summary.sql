select team_id, team_name, league_id, league_name,
       count(*) as games, sum(won::integer) as wins,
       round(100.0 * avg(won::integer), 2) as win_rate,
       round(avg(duration_seconds) / 60.0, 1) as avg_minutes,
       sum(has_draft::integer) as games_with_draft,
       max(started_at) as last_match_at
from {{ ref('fct_team_matches') }}
group by team_id, team_name, league_id, league_name
