-- For bans, team_id means the team making the ban, not the targeted opponent.
select t.match_id, t.started_at, t.team_id, t.team_name, t.opponent_id, t.opponent_name,
       t.league_id, t.league_name, t.patch_id, t.won,
       d.draft_order, d.hero_id, d.hero_name, d.is_pick
from {{ ref('fct_team_matches') }} t
join {{ ref('stg_draft') }} d on d.match_id=t.match_id and d.side=t.side
