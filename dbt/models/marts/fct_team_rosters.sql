-- A roster change is an observed different five, including possible stand-ins.
-- An incomplete/anonymous five is unknown; never impute it from later matches.
with lineups as (
    select match_id, team_id,
           array_agg(distinct account_id order by account_id)
               filter (where account_id is not null) as player_ids
    from {{ ref('fct_player_matches') }}
    group by match_id, team_id
    having count(*)=5 and count(distinct account_id)=5
), signatures as (
    select t.*, l.player_ids, md5(array_to_string(l.player_ids,',')) as roster_id
    from {{ ref('fct_team_matches') }} t
    join lineups l using (match_id,team_id)
), changes as (
    select *, case when roster_id is distinct from
        lag(roster_id) over (partition by team_id order by started_at,match_id)
        then 1 else 0 end as changed
    from signatures
)
select *, sum(changed) over (partition by team_id order by started_at,match_id
           rows between unbounded preceding and current row) as roster_spell
from changes
