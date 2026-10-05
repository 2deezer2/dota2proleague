select team_id, team_name, league_id, league_name, hero_id, hero_name,
       count(*) filter (where is_pick) as picks,
       count(*) filter (where not is_pick) as bans,
       sum(won::integer) filter (where is_pick) as pick_wins,
       round(100.0 * avg(won::integer) filter (where is_pick), 2) as pick_win_rate
from {{ ref('fct_team_draft') }}
group by team_id, team_name, league_id, league_name, hero_id, hero_name
