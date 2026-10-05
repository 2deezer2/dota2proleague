"""Daily ingestion and dbt validation. No network/DB work during DAG parsing."""
import os
import subprocess
from datetime import timedelta

import pendulum
from airflow.sdk import dag, task


@dag(
    dag_id="dota2_pro_league",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="Europe/Moscow"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries":2, "retry_delay":timedelta(minutes=10)},
    tags=["dota2", "opendota", "dbt"],
)
def pro_league():
    @task(execution_timeout=timedelta(minutes=45))
    def collect():
        from dota_scout.warehouse import sync
        return sync(pages=int(os.getenv("MATCH_PAGES", "3")),
                    limit=int(os.getenv("MATCH_LIMIT", "50")))

    @task(execution_timeout=timedelta(minutes=15))
    def build_marts():
        subprocess.run(["/opt/dbt/bin/dbt", "build", "--project-dir", "/opt/project/dbt",
                        "--profiles-dir", "/opt/project/dbt"], check=True)

    @task(execution_timeout=timedelta(minutes=15))
    def profiles():
        from dota_scout.warehouse import sync_profiles
        return sync_profiles(limit=int(os.getenv("PROFILE_LIMIT", "20")))

    collect() >> profiles() >> build_marts()


pro_league()
