select team_id from {{ ref('current_rosters') }} group by team_id having count(*) > 1
