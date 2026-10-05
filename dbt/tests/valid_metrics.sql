select * from {{ ref('team_summary') }}
where wins > games or wins < 0 or win_rate < 0 or win_rate > 100 or avg_minutes <= 0
