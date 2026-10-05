select match_id,player_slot from {{ ref('stg_player_matches') }}
group by match_id,player_slot having count(*) > 1
