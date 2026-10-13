"""Fantasy football data pipeline for the Streamlit matchup tool.

This version keeps the original personal-roster workflow, but also supports
building matchup data for every current RB, WR, and TE so the app can be
shared with other fantasy managers.

Main entry points:
    build_dashboard_data()          -> all current RB/WR/TE players
    build_my_roster_data()          -> original MY_PLAYERS list
    build_matchup_board()           -> matchup table only
"""

from __future__ import annotations

from typing import Iterable

import nflreadpy as nfl
from nflreadpy.config import update_config
import polars as pl

# Streamlit already caches the completed dashboard for 15 minutes in app.py.
# Disable nflreadpy's longer internal cache so each dashboard rebuild checks
# nflverse for newly published schedules/stats instead of reusing stale files.
update_config(cache_mode="off", verbose=False)


MY_PLAYERS = [
    "Jahmyr Gibbs",
    "David Montgomery",
    "Chris Olave",
    "DeVonta Smith",
    "Jameson Williams",
    "Breece Hall",
    "Kyle Pitts",
    "Denzel Boston",
    "Woody Marks",
    "Alvin Kamara",
    "Travis Kelce",
    "Tank Dell",
    "Zach Charbonnet",
]

SKILL_POSITIONS = ["RB", "WR", "TE"]


def get_current_context() -> tuple[int, int]:
    """Return the current NFL season and week reported by nflreadpy."""
    return nfl.get_current_season(), nfl.get_current_week()


def load_base_data() -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Load the source tables used by the project."""
    players = nfl.load_players()
    schedule = nfl.load_schedules()
    player_stats = nfl.load_player_stats()
    team_stats = nfl.load_team_stats()
    return players, schedule, player_stats, team_stats


def get_player_pool(
    players: pl.DataFrame,
    season: int,
    player_names: Iterable[str] | None = None,
) -> pl.DataFrame:
    """Return current fantasy-relevant RB/WR/TE players.

    If player_names is supplied, the pool is restricted to those names.
    Otherwise the function builds a shareable all-player pool.

    The last_season guard is only used when that field exists in nflreadpy's
    player metadata.
    """
    filters = (
        pl.col("position").is_in(SKILL_POSITIONS)
        & pl.col("latest_team").is_not_null()
        & pl.col("display_name").is_not_null()
    )

    if "last_season" in players.columns:
        filters = filters & (pl.col("last_season") >= season)

    if player_names is not None:
        names = list(player_names)
        filters = filters & pl.col("display_name").is_in(names)

    return (
        players
        .filter(filters)
        .select([
            "gsis_id",
            "display_name",
            "position",
            "latest_team",
        ])
        .unique(subset=["gsis_id"])
        .sort(["position", "display_name"])
    )


def get_roster_info(
    players: pl.DataFrame,
    my_players: Iterable[str] = MY_PLAYERS,
    season: int | None = None,
) -> pl.DataFrame:
    """Backward-compatible helper for the original personal roster."""
    if season is None:
        season, _ = get_current_context()
    return get_player_pool(players, season, my_players)


def get_week_schedule(
    schedule: pl.DataFrame,
    season: int,
    week: int,
) -> pl.DataFrame:
    """Return the regular-season schedule for one week."""
    return (
        schedule
        .filter(
            (pl.col("season") == season)
            & (pl.col("week") == week)
            & (pl.col("game_type") == "REG")
        )
        .select([
            "week",
            "gameday",
            "gametime",
            "away_team",
            "home_team",
        ])
    )


def get_team_matchups(week_schedule: pl.DataFrame) -> pl.DataFrame:
    """Convert game rows into one team/opponent row for every team playing."""
    away_rows = week_schedule.select([
        pl.col("away_team").alias("team"),
        pl.col("home_team").alias("opponent"),
        pl.lit("A").alias("home_away"),
        "gameday",
        "gametime",
    ])

    home_rows = week_schedule.select([
        pl.col("home_team").alias("team"),
        pl.col("away_team").alias("opponent"),
        pl.lit("H").alias("home_away"),
        "gameday",
        "gametime",
    ])

    return pl.concat([away_rows, home_rows])


def get_player_matchups(
    player_pool: pl.DataFrame,
    team_matchups: pl.DataFrame,
) -> pl.DataFrame:
    """Attach the current week's matchup to each player."""
    return (
        player_pool
        .join(
            team_matchups,
            left_on="latest_team",
            right_on="team",
            how="left",
        )
        .with_columns([
            pl.col("opponent").fill_null("BYE"),
            pl.col("home_away").fill_null("-"),
            pl.col("gameday").fill_null("BYE"),
            pl.col("gametime").fill_null("-"),
        ])
    )


def get_roster_matchups(
    roster_info: pl.DataFrame,
    team_matchups: pl.DataFrame,
) -> pl.DataFrame:
    """Backward-compatible alias for the original roster workflow."""
    return get_player_matchups(roster_info, team_matchups)


def get_defense_check(
    team_stats: pl.DataFrame,
    season: int,
    week: int,
) -> pl.DataFrame:
    """Keep completed regular-season games before the requested week."""
    return (
        team_stats
        .filter(
            (pl.col("season") == season)
            & (pl.col("season_type") == "REG")
            & (pl.col("week") < week)
        )
        .select([
            "week",
            "team",
            "opponent_team",
            "passing_yards",
            "passing_tds",
            "rushing_yards",
            "rushing_tds",
            "attempts",
            "carries",
            "sacks_suffered",
            "sack_yards_lost",
        ])
    )


def get_defense_stats(defense_check: pl.DataFrame) -> pl.DataFrame:
    """Build per-game defensive box-score stats and volume context."""
    return (
        defense_check
        .group_by("opponent_team")
        .agg([
            pl.len().alias("def_games_played"),
            pl.col("passing_yards").mean().alias("pass_yards_allowed"),
            pl.col("passing_tds").sum().alias("pass_tds_allowed"),
            pl.col("passing_tds").mean().alias("pass_tds_allowed_pg"),
            pl.col("rushing_yards").mean().alias("rush_yards_allowed"),
            pl.col("rushing_tds").sum().alias("rush_tds_allowed"),
            pl.col("rushing_tds").mean().alias("rush_tds_allowed_pg"),
            pl.col("carries").mean().alias("rush_attempts_faced_pg"),
            (pl.col("attempts") + pl.col("sacks_suffered"))
                .mean()
                .alias("pass_dropbacks_faced_pg"),
            (pl.col("attempts") + pl.col("sacks_suffered") + pl.col("carries"))
                .mean()
                .alias("plays_faced_pg"),
        ])
        .rename({"opponent_team": "defense_team"})
        .with_columns([
            pl.col("pass_yards_allowed").round(1),
            pl.col("pass_tds_allowed_pg").round(2),
            pl.col("rush_yards_allowed").round(1),
            pl.col("rush_tds_allowed_pg").round(2),
            pl.col("rush_attempts_faced_pg").round(1),
            pl.col("pass_dropbacks_faced_pg").round(1),
            pl.col("plays_faced_pg").round(1),
        ])
    )


def get_defense_efficiency(defense_check: pl.DataFrame) -> pl.DataFrame:
    """Calculate season-to-date defensive efficiency from total opportunities."""
    return (
        defense_check
        .group_by("opponent_team")
        .agg([
            pl.col("rushing_yards").sum().alias("rush_yards_allowed_total"),
            pl.col("carries").sum().alias("rush_attempts_faced"),
            pl.col("passing_yards").sum().alias("pass_yards_allowed_total"),
            pl.col("sack_yards_lost").sum().alias("sack_yards_lost_total"),
            pl.col("attempts").sum().alias("pass_attempts_faced"),
            pl.col("sacks_suffered").sum().alias("sacks_faced"),
            pl.col("rushing_yards").sum().alias("total_rush_yards"),
            pl.col("passing_yards").sum().alias("total_pass_yards"),
        ])
        .with_columns([
            (
                pl.col("rush_yards_allowed_total")
                / pl.col("rush_attempts_faced")
            ).alias("rush_ypc_allowed"),
            (
                (
                    pl.col("pass_yards_allowed_total")
                    - pl.col("sack_yards_lost_total")
                )
                /
                (
                    pl.col("pass_attempts_faced")
                    + pl.col("sacks_faced")
                )
            ).alias("net_pass_yds_per_dropback"),
            (
                (
                    pl.col("total_pass_yards")
                    - pl.col("sack_yards_lost_total")
                    + pl.col("total_rush_yards")
                )
                /
                (
                    pl.col("pass_attempts_faced")
                    + pl.col("sacks_faced")
                    + pl.col("rush_attempts_faced")
                )
            ).alias("yards_per_play_allowed"),
        ])
        .rename({"opponent_team": "defense_team"})
        .select([
            "defense_team",
            "rush_ypc_allowed",
            "net_pass_yds_per_dropback",
            "yards_per_play_allowed",
        ])
        .with_columns([
            pl.col("rush_ypc_allowed").round(2),
            pl.col("net_pass_yds_per_dropback").round(2),
            pl.col("yards_per_play_allowed").round(2),
        ])
    )


def get_player_summary(
    player_stats: pl.DataFrame,
    season: int,
    week: int,
    player_ids: Iterable[str] | None = None,
) -> pl.DataFrame:
    """Summarize completed games for all players or a selected player-ID pool."""
    filters = (
        (pl.col("week") < week)
        & pl.col("position").is_in(SKILL_POSITIONS)
    )

    if "season" in player_stats.columns:
        filters = filters & (pl.col("season") == season)

    if player_ids is not None:
        ids = list(player_ids)
        filters = filters & pl.col("player_id").is_in(ids)

    player_baseline = (
        player_stats
        .filter(filters)
        .select([
            "player_id",
            "player_display_name",
            "position",
            "week",
            "rushing_yards",
            "rushing_tds",
            "targets",
            "receptions",
            "receiving_yards",
            "receiving_tds",
        ])
    )

    return (
        player_baseline
        .group_by([
            "player_id",
            "player_display_name",
            "position",
        ])
        .agg([
            pl.len().alias("games_played"),
            pl.col("targets").mean().alias("tgt_pg"),
            pl.col("receptions").mean().alias("rec_pg"),
            pl.col("receiving_yards").mean().alias("rec_yds_pg"),
            pl.col("rushing_yards").mean().alias("rush_yds_pg"),
            pl.col("rushing_tds").sum().alias("rush_td"),
            pl.col("receiving_tds").sum().alias("rec_td"),
        ])
        .with_columns([
            pl.col("tgt_pg").round(1),
            pl.col("rec_pg").round(1),
            pl.col("rec_yds_pg").round(1),
            pl.col("rush_yds_pg").round(1),
        ])
    )


def get_league_efficiency(defense_efficiency: pl.DataFrame) -> dict[str, float]:
    """Return league-average efficiency values."""
    league = defense_efficiency.select([
        pl.col("rush_ypc_allowed").mean().alias("league_rush_ypc"),
        pl.col("net_pass_yds_per_dropback").mean().alias("league_net_pass_ypd"),
        pl.col("yards_per_play_allowed").mean().alias("league_ypp"),
    ])

    return {
        "rush_ypc": league["league_rush_ypc"][0],
        "net_pass_ypd": league["league_net_pass_ypd"][0],
        "ypp": league["league_ypp"][0],
    }


def get_league_defense_stats(defense_stats: pl.DataFrame) -> dict[str, float]:
    """Return league averages for box-score and volume detail cards."""
    league = defense_stats.select([
        pl.col("pass_yards_allowed").mean().alias("league_pass_yards_allowed"),
        pl.col("pass_tds_allowed_pg").mean().alias("league_pass_tds_allowed_pg"),
        pl.col("rush_yards_allowed").mean().alias("league_rush_yards_allowed"),
        pl.col("rush_tds_allowed_pg").mean().alias("league_rush_tds_allowed_pg"),
        pl.col("rush_attempts_faced_pg").mean().alias("league_rush_attempts_faced_pg"),
        pl.col("pass_dropbacks_faced_pg").mean().alias("league_pass_dropbacks_faced_pg"),
        pl.col("plays_faced_pg").mean().alias("league_plays_faced_pg"),
    ])

    return {
        "pass_yards": league["league_pass_yards_allowed"][0],
        "pass_td_pg": league["league_pass_tds_allowed_pg"][0],
        "rush_yards": league["league_rush_yards_allowed"][0],
        "rush_td_pg": league["league_rush_tds_allowed_pg"][0],
        "rush_attempts_pg": league["league_rush_attempts_faced_pg"][0],
        "pass_dropbacks_pg": league["league_pass_dropbacks_faced_pg"][0],
        "plays_pg": league["league_plays_faced_pg"][0],
    }


def get_defense_ranks(defense_efficiency: pl.DataFrame) -> pl.DataFrame:
    """Rank defenses 1=toughest, 32=weakest by efficiency allowed."""
    return (
        defense_efficiency
        .with_columns([
            pl.col("rush_ypc_allowed").rank("ordinal").alias("rush_def_rank"),
            pl.col("net_pass_yds_per_dropback").rank("ordinal").alias("pass_def_rank"),
        ])
        .select([
            "defense_team",
            "rush_def_rank",
            "pass_def_rank",
        ])
    )


def build_final_board(
    player_matchups: pl.DataFrame,
    defense_stats: pl.DataFrame,
    player_summary: pl.DataFrame,
) -> pl.DataFrame:
    """Build schedule + player production + opponent defense data."""
    return (
        player_matchups
        .join(
            defense_stats,
            left_on="opponent",
            right_on="defense_team",
            how="left",
        )
        .rename({
            "display_name": "player",
            "latest_team": "team",
            "home_away": "h_a",
        })
        .join(
            player_summary,
            left_on="gsis_id",
            right_on="player_id",
            how="left",
        )
        .select([
            "gsis_id",
            "player",
            "position",
            "team",
            "opponent",
            "h_a",
            "gameday",
            "gametime",
            "games_played",
            "tgt_pg",
            "rec_pg",
            "rec_yds_pg",
            "rush_yds_pg",
            "rush_td",
            "rec_td",
            pl.col("pass_yards_allowed").alias("pass_yds_allowed"),
            pl.col("pass_tds_allowed").alias("pass_td_allowed"),
            pl.col("pass_tds_allowed_pg").alias("pass_td_allowed_pg"),
            pl.col("rush_yards_allowed").alias("rush_yds_allowed"),
            pl.col("rush_tds_allowed").alias("rush_td_allowed"),
            pl.col("rush_tds_allowed_pg").alias("rush_td_allowed_pg"),
            "rush_attempts_faced_pg",
            "pass_dropbacks_faced_pg",
            "plays_faced_pg",
        ])
    )


def make_player_details(final_board: pl.DataFrame) -> pl.DataFrame:
    """Return player production data for detail panels."""
    return final_board.select([
        "gsis_id",
        "player",
        "position",
        "team",
        "games_played",
        "tgt_pg",
        "rec_pg",
        "rec_yds_pg",
        "rush_yds_pg",
        "rush_td",
        "rec_td",
    ])


def make_matchup_board(
    final_board: pl.DataFrame,
    defense_efficiency: pl.DataFrame,
    defense_ranks: pl.DataFrame,
    league_efficiency: dict[str, float],
    league_defense_stats: dict[str, float],
) -> pl.DataFrame:
    """Build the UI-facing matchup table."""
    league_rush_ypc = league_efficiency["rush_ypc"]
    league_net_pass_ypd = league_efficiency["net_pass_ypd"]

    board = (
        final_board
        .join(
            defense_efficiency,
            left_on="opponent",
            right_on="defense_team",
            how="left",
        )
        .join(
            defense_ranks,
            left_on="opponent",
            right_on="defense_team",
            how="left",
        )
        .with_columns([
            pl.col("pass_yds_allowed").round(1),
            pl.col("rush_yds_allowed").round(1),
            pl.when(pl.col("opponent") == "BYE")
              .then(pl.lit("BYE"))
              .when(pl.col("position") == "RB")
              .then(pl.lit("Rush Defense"))
              .otherwise(pl.lit("Pass Defense"))
              .alias("matchup_focus"),
            pl.when(pl.col("position") == "RB")
              .then(pl.col("rush_yds_allowed"))
              .otherwise(pl.col("pass_yds_allowed"))
              .alias("key_matchup_value"),
            pl.when(pl.col("position") == "RB")
              .then(pl.col("rush_ypc_allowed"))
              .otherwise(pl.col("net_pass_yds_per_dropback"))
              .alias("key_efficiency_stat"),
            pl.when(pl.col("opponent") == "BYE")
              .then(pl.lit("BYE WEEK"))
              .otherwise(pl.lit("ACTIVE"))
              .alias("week_status"),
            pl.when(pl.col("position") == "RB")
              .then(pl.col("rush_def_rank"))
              .otherwise(pl.col("pass_def_rank"))
              .alias("key_def_rank"),
        ])
        .with_columns([
            pl.lit(league_defense_stats["pass_yards"]).round(1).alias("league_pass_yds_allowed"),
            pl.lit(league_defense_stats["pass_td_pg"]).round(2).alias("league_pass_td_allowed_pg"),
            pl.lit(league_defense_stats["rush_yards"]).round(1).alias("league_rush_yds_allowed"),
            pl.lit(league_defense_stats["rush_td_pg"]).round(2).alias("league_rush_td_allowed_pg"),
            pl.lit(league_defense_stats["rush_attempts_pg"]).round(1).alias("league_rush_attempts_faced_pg"),
            pl.lit(league_defense_stats["pass_dropbacks_pg"]).round(1).alias("league_pass_dropbacks_faced_pg"),
            pl.lit(league_defense_stats["plays_pg"]).round(1).alias("league_plays_faced_pg"),
            pl.lit(league_rush_ypc).round(2).alias("league_rush_ypc"),
            pl.lit(league_net_pass_ypd).round(2).alias("league_net_pass_ypd"),
            pl.lit(league_efficiency["ypp"]).round(2).alias("league_ypp"),
        ])
        .with_columns([
            (pl.col("pass_yds_allowed") - pl.col("league_pass_yds_allowed"))
              .round(1).alias("pass_yds_vs_league"),
            (pl.col("pass_td_allowed_pg") - pl.col("league_pass_td_allowed_pg"))
              .round(2).alias("pass_td_pg_vs_league"),
            (pl.col("rush_yds_allowed") - pl.col("league_rush_yds_allowed"))
              .round(1).alias("rush_yds_vs_league"),
            (pl.col("rush_td_allowed_pg") - pl.col("league_rush_td_allowed_pg"))
              .round(2).alias("rush_td_pg_vs_league"),
            (pl.col("rush_attempts_faced_pg") - pl.col("league_rush_attempts_faced_pg"))
              .round(1).alias("rush_attempts_vs_league"),
            (pl.col("pass_dropbacks_faced_pg") - pl.col("league_pass_dropbacks_faced_pg"))
              .round(1).alias("pass_dropbacks_vs_league"),
            (pl.col("plays_faced_pg") - pl.col("league_plays_faced_pg"))
              .round(1).alias("plays_vs_league"),
            pl.when(pl.col("opponent") == "BYE")
              .then(pl.lit(None, dtype=pl.Float64))
              .when(pl.col("position") == "RB")
              .then(pl.col("rush_ypc_allowed") - league_rush_ypc)
              .otherwise(pl.col("net_pass_yds_per_dropback") - league_net_pass_ypd)
              .round(2)
              .alias("efficiency_vs_league"),
        ])
        .with_columns([
            pl.when(pl.col("week_status") == "BYE WEEK")
              .then(pl.lit("BYE"))
              .when(pl.col("efficiency_vs_league") >= 0.50)
              .then(pl.lit("Favorable"))
              .when(pl.col("efficiency_vs_league") <= -0.50)
              .then(pl.lit("Tough"))
              .otherwise(pl.lit("Neutral"))
              .alias("matchup_label"),
            pl.col("efficiency_vs_league")
              .map_elements(
                  lambda x: f"{x:+.2f}" if x is not None else "BYE",
                  return_dtype=pl.Utf8,
              )
              .alias("efficiency_vs_league_display"),
        ])
    )

    return board


def _build_dashboard_data(
    player_names: Iterable[str] | None = None,
    season: int | None = None,
    week: int | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    current_season, current_week = get_current_context()
    season = current_season if season is None else season
    week = current_week if week is None else week

    players, schedule, player_stats, team_stats = load_base_data()

    player_pool = get_player_pool(players, season, player_names)
    week_schedule = get_week_schedule(schedule, season, week)
    team_matchups = get_team_matchups(week_schedule)
    player_matchups = get_player_matchups(player_pool, team_matchups)

    defense_check = get_defense_check(team_stats, season, week)
    defense_stats = get_defense_stats(defense_check)
    defense_efficiency = get_defense_efficiency(defense_check)
    defense_ranks = get_defense_ranks(defense_efficiency)
    league_efficiency = get_league_efficiency(defense_efficiency)
    league_defense_stats = get_league_defense_stats(defense_stats)

    player_summary = get_player_summary(
        player_stats,
        season,
        week,
        player_pool["gsis_id"].to_list(),
    )

    final_board = build_final_board(
        player_matchups,
        defense_stats,
        player_summary,
    )

    matchup_board = make_matchup_board(
        final_board,
        defense_efficiency,
        defense_ranks,
        league_efficiency,
        league_defense_stats,
    )

    player_details = make_player_details(final_board)

    return matchup_board, player_details


def build_dashboard_data(
    player_names: Iterable[str] | None = None,
    season: int | None = None,
    week: int | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Build data for all current RB/WR/TE players by default.

    Pass player_names to restrict the output to a custom roster or shortlist.
    """
    return _build_dashboard_data(player_names, season, week)


def build_my_roster_data(
    season: int | None = None,
    week: int | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Build the original personal-roster view."""
    return _build_dashboard_data(MY_PLAYERS, season, week)


def build_matchup_board(
    player_names: Iterable[str] | None = None,
    season: int | None = None,
    week: int | None = None,
) -> pl.DataFrame:
    """Convenience entry point for the main matchup board."""
    matchup_board, _ = build_dashboard_data(player_names, season, week)
    return matchup_board


if __name__ == "__main__":
    board, details = build_dashboard_data()
    print(board)
    print(details)
