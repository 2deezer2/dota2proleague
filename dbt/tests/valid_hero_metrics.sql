select * from {{ ref('hero_summary') }}
where pick_wins > picks or pick_win_rate < 0 or pick_win_rate > 100
