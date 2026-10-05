select * from {{ ref('stg_matches') }} where duration_seconds <= 0
