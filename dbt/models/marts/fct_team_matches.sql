select match_id, started_at, league_id, league_name, patch_id, duration_seconds, has_draft,
       radiant_team_id as team_id, radiant_name as team_name,
       dire_team_id as opponent_id, dire_name as opponent_name,
       0 as side, radiant_win as won
from {{ ref('stg_matches') }}
where radiant_team_id is not null
union all
select match_id, started_at, league_id, league_name, patch_id, duration_seconds, has_draft,
       dire_team_id as team_id, dire_name as team_name,
       radiant_team_id as opponent_id, radiant_name as opponent_name,
       1 as side, not radiant_win as won
from {{ ref('stg_matches') }}
where dire_team_id is not null
