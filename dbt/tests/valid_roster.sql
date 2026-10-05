select * from {{ ref('fct_team_rosters') }}
where cardinality(player_ids)<>5 or array_position(player_ids,null) is not null
