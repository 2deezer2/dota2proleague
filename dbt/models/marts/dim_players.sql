with observed as (
    select distinct on (account_id) account_id, player_name
    from {{ ref('fct_player_matches') }} where account_id is not null
    order by account_id,started_at desc,match_id desc
)
select o.account_id,
       coalesce(p.payload->'profile'->>'name',p.payload->'profile'->>'personaname',
                o.player_name,'Player ' || o.account_id) as name,
       p.fetched_at as profile_fetched_at
from observed o left join {{ source('raw','player_profiles') }} p using (account_id)
