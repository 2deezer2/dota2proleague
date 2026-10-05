select team_id, team_name, opponent_id, opponent_name,
       count(*) as games, sum(won::integer) as wins,
       round(100.0 * avg(won::integer), 2) as win_rate
from {{ ref('fct_team_matches') }}
where opponent_id is not null
group by team_id, team_name, opponent_id, opponent_name
