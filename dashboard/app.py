"""Scouting dashboard: results and drafts from the same date/team/tournament filters."""
import os
from datetime import date, timedelta

import pandas as pd
import psycopg
import streamlit as st

st.set_page_config(page_title="Dota 2 Pro Scout", page_icon="⚔️", layout="wide")
st.title("Dota 2 Pro Scout")
st.caption("Профессиональные матчи · результаты команд · пики и баны")


@st.cache_data(ttl=60)
def query(sql, params=()):
    with psycopg.connect(os.environ["WAREHOUSE_DSN"]) as conn:
        cursor = conn.execute(sql, params)
        return pd.DataFrame(cursor.fetchall(), columns=[col.name for col in cursor.description])


try:
    teams = query("SELECT DISTINCT team_id, team_name FROM analytics.fct_team_matches "
                  "ORDER BY team_name")
    leagues = query("SELECT DISTINCT league_id, league_name FROM analytics.fct_team_matches "
                    "WHERE league_id IS NOT NULL ORDER BY league_name")
except psycopg.errors.UndefinedTable:
    st.info("Витрины ещё не созданы. Запусти DAG dota2_pro_league или демо из README.")
    st.stop()
except psycopg.OperationalError:
    st.error("База данных пока недоступна. Проверь состояние PostgreSQL в Docker Compose.")
    st.stop()

if teams.empty:
    st.info("Нет матчей. Запусти сбор данных или загрузи демонстрационную выборку.")
    st.stop()

if st.sidebar.button("Обновить данные"):
    st.cache_data.clear()
    st.rerun()

team_options = {int(row.team_id): row.team_name for row in teams.itertuples()}
team_id = st.sidebar.selectbox("Команда", list(team_options), format_func=team_options.get)
league_options = {int(row.league_id): row.league_name for row in leagues.itertuples()}
league_id = st.sidebar.selectbox("Турнир", [None] + list(league_options),
                                 format_func=lambda item: "Все турниры" if item is None
                                 else league_options[item])
period = st.sidebar.date_input("Период", (date.today() - timedelta(days=90), date.today()))
if len(period) != 2:
    st.info("Выбери начало и конец периода.")
    st.stop()
conditions = "team_id=%s AND started_at >= %s AND started_at < %s"
params = [team_id, period[0], period[1] + timedelta(days=1)]
if league_id is not None:
    conditions += " AND league_id=%s"
    params.append(league_id)
matches = query("SELECT * FROM analytics.fct_team_matches WHERE " + conditions
                + " ORDER BY started_at DESC", tuple(params))
draft = query("SELECT * FROM analytics.fct_team_draft WHERE " + conditions, tuple(params))
if matches.empty:
    st.info("В выбранном периоде нет матчей этой команды.")
    st.stop()

if (matches.league_id == 999999).any():
    st.warning("Выборка содержит синтетический Demo League — это не реальные результаты.")

left, middle, right = st.columns(3)
left.metric("Матчей", len(matches))
middle.metric("Винрейт", f"{matches.won.mean() * 100:.1f}%")
right.metric("Матчи с драфтом", f"{matches.has_draft.sum()} / {len(matches)}")
st.caption("Винрейт относится к собранной выборке. Баны — действия выбранной команды. "
           "Наличие драфта означает хотя бы одно событие; полнота отдельных драфтов не гарантируется.")

st.subheader("Пики и баны")
if draft.empty:
    st.info("Для этой выборки данные драфтов отсутствуют.")
else:
    draft["pick_win"] = draft.is_pick & draft.won
    heroes = draft.groupby("hero_name").agg(
        picks=("is_pick", "sum"), actions=("is_pick", "size"), wins=("pick_win", "sum"))
    heroes["bans"] = heroes.actions - heroes.picks
    heroes["pick_win_rate"] = (heroes.wins / heroes.picks.replace(0, float("nan")) * 100).round(1)
    heroes = heroes.sort_values(["picks", "bans"], ascending=False)
    st.bar_chart(heroes[["picks", "bans"]].head(15))
    st.dataframe(heroes.drop(columns="actions"), use_container_width=True)

st.subheader("Результаты против соперников")
opponents = matches.groupby(["opponent_id", "opponent_name"]).agg(
    games=("won", "size"), wins=("won", "sum"), win_rate=("won", "mean"))
opponents["win_rate"] = (opponents.win_rate * 100).round(1)
st.dataframe(opponents.sort_values("games", ascending=False), use_container_width=True)
st.subheader("Последние матчи")
st.dataframe(matches[["match_id", "started_at", "league_name", "opponent_name", "won",
                      "duration_seconds", "has_draft"]], use_container_width=True)
st.download_button("Скачать выборку CSV", matches.to_csv(index=False).encode("utf-8"),
                   file_name=f"team_{team_id}_matches.csv", mime="text/csv")
