select p.*, t.started_at, t.team_id, t.team_name, t.opponent_id, t.won,
       t.league_id, t.league_name, t.patch_id, t.duration_seconds
from {{ ref('stg_player_matches') }} p
join {{ ref('fct_team_matches') }} t on p.match_id=t.match_id and p.side=t.side
