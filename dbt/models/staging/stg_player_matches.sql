select m.match_id,
       (p->>'player_slot')::integer as player_slot,
       case when (p->>'player_slot')::integer < 128 then 0 else 1 end as side,
       case when (p->>'account_id')::bigint in (0,4294967295) then null
            else (p->>'account_id')::bigint end as account_id,
       coalesce(p->>'name', p->>'personaname') as player_name,
       (p->>'hero_id')::integer as hero_id,
       (p->>'kills')::integer as kills,
       (p->>'deaths')::integer as deaths,
       (p->>'assists')::integer as assists,
       (p->>'gold_per_min')::integer as gold_per_min,
       (p->>'xp_per_min')::integer as xp_per_min
from {{ source('raw','match_payloads') }} m
cross join lateral jsonb_array_elements(
    coalesce(nullif(m.payload->'players','null'::jsonb),'[]'::jsonb)) p
where (p->>'player_slot') is not null
