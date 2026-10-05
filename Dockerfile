FROM apache/airflow:3.3.1-python3.12
USER root
RUN mkdir -p /opt/project /opt/dbt && chown -R airflow:0 /opt/project /opt/dbt
USER airflow
COPY --chown=airflow:0 . /opt/project
RUN pip install --no-cache-dir "apache-airflow==3.3.1" "psycopg[binary]>=3.2,<4" \
    --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.3.1/constraints-3.12.txt
RUN python -m venv /opt/dbt && /opt/dbt/bin/pip install --no-cache-dir -r /opt/project/requirements-dbt.txt
ENV PYTHONPATH=/opt/project/src
WORKDIR /opt/project
