select match_id, team_id from {{ ref('fct_team_matches') }}
group by match_id, team_id having count(*) > 1
