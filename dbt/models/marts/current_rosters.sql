with latest as (
    select *, row_number() over (partition by team_id order by started_at desc,match_id desc) as rn
    from {{ ref('fct_team_rosters') }}
)
select l.team_id, l.team_name, l.roster_id, l.roster_spell, l.player_ids,
       s.first_seen_at, s.last_seen_at, s.games, s.wins, s.win_rate,
       (select max(t.started_at) from {{ ref('fct_team_matches') }} t
        where t.team_id=l.team_id) as latest_team_match_at
from latest l join {{ ref('roster_spells') }} s using (team_id,roster_spell,roster_id,player_ids)
where l.rn=1
