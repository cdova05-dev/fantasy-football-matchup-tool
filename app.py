import streamlit as st
import polars as pl

from src.data import build_dashboard_data


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Fantasy Football Matchup Tool",
    page_icon="🏈",
    layout="wide"
)


# ============================================================
# DATA
# ============================================================

@st.cache_data(ttl=900, show_spinner="Loading current NFL matchup data...")
def load_dashboard_data():
    return build_dashboard_data()


matchup_board, player_details = load_dashboard_data()


# ============================================================
# HELPERS
# ============================================================

def ordinal(number):
    if number is None:
        return "—"

    number = int(number)

    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")

    return f"{number}{suffix}"


def matchup_color(label):
    colors = {
        "Favorable": "#22c55e",
        "Neutral": "#eab308",
        "Tough": "#ef4444",
        "BYE": "#8b5cf6"
    }
    return colors.get(label, "#6b7280")


def rank_status(rank_value):
    if rank_value is None:
        return "Neutral"

    rank_value = int(rank_value)

    if rank_value <= 10:
        return "Tough"
    if rank_value >= 23:
        return "Favorable"
    return "Neutral"


def efficiency_status(value, threshold=0.50):
    if value is None:
        return "Neutral"

    if value >= threshold:
        return "Favorable"
    if value <= -threshold:
        return "Tough"
    return "Neutral"


def pct_status(value, league_avg, tolerance=0.10):
    """Higher allowed is more favorable for the fantasy player."""
    if value is None or league_avg in (None, 0):
        return "Neutral"

    upper = league_avg * (1 + tolerance)
    lower = league_avg * (1 - tolerance)

    if value >= upper:
        return "Favorable"
    if value <= lower:
        return "Tough"
    return "Neutral"


def colored_metric(label, value, status="Neutral"):
    color = matchup_color(status)

    html = (
        f'<div style="border:1px solid {color};border-left:4px solid {color};'
        f'border-radius:10px;padding:11px 13px;min-height:78px;'
        f'background:rgba(255,255,255,0.018);">'
        f'<div style="font-size:11px;opacity:0.70;margin-bottom:5px;">{label}</div>'
        f'<div style="font-size:24px;font-weight:650;line-height:1.05;">{value}</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


def detail_metric(label, value, status="Neutral", subtext=None):
    color = matchup_color(status)

    subtext_html = ""
    if subtext:
        subtext_html = (
            f'<div style="font-size:9px;opacity:0.52;margin-top:5px;">'
            f'{subtext}</div>'
        )

    html = (
        f'<div style="border:1px solid {color};border-radius:8px;'
        f'padding:10px 11px;min-height:72px;background:rgba(255,255,255,0.012);">'
        f'<div style="font-size:10px;opacity:0.70;margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:20px;font-weight:620;line-height:1.05;">{value}</div>'
        f'{subtext_html}'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


def team_logo_url(team):
    espn_map = {
        "ARI": "ari", "ATL": "atl", "BAL": "bal", "BUF": "buf",
        "CAR": "car", "CHI": "chi", "CIN": "cin", "CLE": "cle",
        "DAL": "dal", "DEN": "den", "DET": "det", "GB": "gb",
        "HOU": "hou", "IND": "ind", "JAX": "jax", "KC": "kc",
        "LV": "lv", "LAC": "lac", "LAR": "lar", "LA": "lar",
        "MIA": "mia", "MIN": "min", "NE": "ne", "NO": "no",
        "NYG": "nyg", "NYJ": "nyj", "PHI": "phi", "PIT": "pit",
        "SEA": "sea", "SF": "sf", "TB": "tb", "TEN": "ten",
        "WAS": "wsh", "WSH": "wsh"
    }

    slug = espn_map.get(team)
    if slug is None:
        return None

    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{slug}.png"


def header_block(row):
    player = row["player"]
    team = row["team"]
    position = row["position"]
    opponent = row["opponent"]
    h_a = row["h_a"]
    label = row["matchup_label"]

    color = matchup_color(label)
    logo = team_logo_url(team)

    if opponent == "BYE":
        matchup_text = f"{team} — BYE WEEK"
    else:
        game_location = "vs" if h_a == "H" else "@"
        matchup_text = f"{team} {game_location} {opponent}"

    if logo:
        visual = (
            f'<div style="width:52px;height:52px;border-radius:12px;display:flex;'
            f'align-items:center;justify-content:center;background:rgba(255,255,255,0.04);'
            f'border:1px solid rgba(255,255,255,0.10);padding:5px;">'
            f'<img src="{logo}" style="max-width:100%;max-height:100%;object-fit:contain;" />'
            f'</div>'
        )
    else:
        initials = "".join(part[0] for part in player.split()[:2]).upper()
        visual = (
            f'<div style="width:52px;height:52px;border-radius:50%;display:flex;'
            f'align-items:center;justify-content:center;background:rgba(255,255,255,0.06);'
            f'border:1px solid rgba(255,255,255,0.12);font-size:16px;font-weight:700;">'
            f'{initials}</div>'
        )

    html = (
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'gap:18px;margin-top:8px;margin-bottom:6px;padding:8px 0;">'
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'{visual}'
        f'<div>'
        f'<div style="font-size:27px;font-weight:700;line-height:1.1;">{player}</div>'
        f'<div style="font-size:14px;opacity:0.70;margin-top:4px;">'
        f'{matchup_text} &nbsp;•&nbsp; {position}</div>'
        f'</div></div>'
        f'<div style="display:inline-block;padding:6px 12px;border-radius:8px;'
        f'background-color:{color};color:white;font-weight:700;font-size:15px;'
        f'white-space:nowrap;">{label}</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)


def matchup_takeaway(row):
    opponent = row["opponent"]
    position = row["position"]
    label = row["matchup_label"]
    rank = row["key_def_rank"]
    efficiency = row["efficiency_vs_league"]

    if opponent == "BYE":
        return "No game this week."

    if position == "RB":
        metric_value = row["rush_ypc_allowed"]
        metric_name = "yards per carry"
        area = "on the ground"
    else:
        metric_value = row["net_pass_yds_per_dropback"]
        metric_name = "net yards per dropback"
        area = "through the air"

    if label == "Favorable":
        opener = f"{opponent} has been a favorable matchup {area}"
    elif label == "Tough":
        opener = f"{opponent} has been a difficult matchup {area}"
    else:
        opener = f"{opponent} has been close to league-average {area}"

    details = []

    if rank is not None:
        details.append(f"ranking {ordinal(rank)} in the relevant efficiency metric")

    if metric_value is not None and efficiency is not None:
        if efficiency > 0:
            details.append(
                f"allowing {metric_value:.2f} {metric_name}, "
                f"{abs(efficiency):.2f} above league average"
            )
        elif efficiency < 0:
            details.append(
                f"allowing {metric_value:.2f} {metric_name}, "
                f"{abs(efficiency):.2f} below league average"
            )
        else:
            details.append(
                f"allowing {metric_value:.2f} {metric_name}, right at league average"
            )

    if details:
        return opener + ", " + " and ".join(details) + "."
    return opener + "."


def option_label(row):
    return f'{row["player"]} — {row["team"]} — {row["position"]}'


def build_player_options(board):
    rows = board.select(["gsis_id", "player", "team", "position"]).to_dicts()
    options = {}

    for row in rows:
        label = option_label(row)
        options[label] = row["gsis_id"]

    return dict(sorted(options.items(), key=lambda item: item[0].lower()))


PLAYER_OPTIONS = build_player_options(matchup_board)


def get_matchup_row(gsis_id):
    result = matchup_board.filter(pl.col("gsis_id") == gsis_id)
    return result.row(0, named=True)


def get_detail_row(gsis_id):
    result = player_details.filter(pl.col("gsis_id") == gsis_id)
    return result.row(0, named=True)


def game_info(row):
    if row["opponent"] == "BYE":
        return

    location_text = "Home" if row["h_a"] == "H" else "Away"

    st.markdown(
        f'<div class="small-note" style="margin-bottom:8px;">'
        f'📅 {row["gameday"]} &nbsp;&nbsp;•&nbsp;&nbsp; '
        f'🕒 {row["gametime"]} &nbsp;&nbsp;•&nbsp;&nbsp; {location_text}</div>',
        unsafe_allow_html=True
    )


def render_main_matchup(row):
    if row["opponent"] == "BYE":
        st.info(f'{row["player"]} does not have a game this week.')
        return

    col1, col2, col3 = st.columns(3, gap="small")

    key_rank_status = rank_status(row["key_def_rank"])
    key_eff_status = efficiency_status(row["efficiency_vs_league"])

    with col1:
        colored_metric(
            "Defense Rank",
            ordinal(row["key_def_rank"]),
            key_rank_status
        )

    with col2:
        if row["position"] == "RB":
            value = row["rush_ypc_allowed"]
            label = "Rush YPC Allowed"
        else:
            value = row["net_pass_yds_per_dropback"]
            label = "Net Pass Yds / Dropback"

        colored_metric(
            label,
            f"{value:.2f}" if value is not None else "—",
            key_eff_status
        )

    with col3:
        colored_metric(
            "Vs League Average",
            row["efficiency_vs_league_display"]
            if row["efficiency_vs_league_display"] is not None
            else "—",
            key_eff_status
        )

    st.markdown(
        f'<div class="takeaway-box"><strong>Matchup outlook:</strong> '
        f'{matchup_takeaway(row)}</div>',
        unsafe_allow_html=True
    )


def render_defense_details(row):
    if row["opponent"] == "BYE":
        return

    with st.expander("View Defense Details"):
        league_pass_yds = row["league_pass_yds_allowed"]
        league_pass_tds = row["league_pass_td_allowed_pg"]
        league_rush_yds = row["league_rush_yds_allowed"]
        league_rush_tds = row["league_rush_td_allowed_pg"]
        league_rush_ypc = row["league_rush_ypc"]
        league_net_pass = row["league_net_pass_ypd"]
        league_ypp = row["league_ypp"]

        top1, top2, top3, top4 = st.columns(4, gap="small")

        with top1:
            value = row["pass_yds_allowed"]
            detail_metric(
                "Pass Yards Allowed / Game",
                f"{value:.1f}" if value is not None else "—",
                pct_status(value, league_pass_yds),
                f"League avg: {league_pass_yds:.1f}"
            )

        with top2:
            value = row["pass_td_allowed_pg"]
            detail_metric(
                "Pass TDs Allowed / Game",
                f"{value:.2f}" if value is not None else "—",
                pct_status(value, league_pass_tds),
                f"League avg: {league_pass_tds:.2f}"
            )

        with top3:
            value = row["rush_yds_allowed"]
            detail_metric(
                "Rush Yards Allowed / Game",
                f"{value:.1f}" if value is not None else "—",
                pct_status(value, league_rush_yds),
                f"League avg: {league_rush_yds:.1f}"
            )

        with top4:
            value = row["rush_td_allowed_pg"]
            detail_metric(
                "Rush TDs Allowed / Game",
                f"{value:.2f}" if value is not None else "—",
                pct_status(value, league_rush_tds),
                f"League avg: {league_rush_tds:.2f}"
            )

        st.write("")

        bottom1, bottom2, bottom3 = st.columns(3, gap="small")

        with bottom1:
            value = row["rush_ypc_allowed"]
            detail_metric(
                "Rush YPC Allowed",
                f"{value:.2f}" if value is not None else "—",
                pct_status(value, league_rush_ypc),
                f"League avg: {league_rush_ypc:.2f}"
            )

        with bottom2:
            value = row["net_pass_yds_per_dropback"]
            detail_metric(
                "Net Pass Yds / Dropback",
                f"{value:.2f}" if value is not None else "—",
                pct_status(value, league_net_pass),
                f"League avg: {league_net_pass:.2f}"
            )

        with bottom3:
            value = row["yards_per_play_allowed"]
            detail_metric(
                "Yards / Play Allowed",
                f"{value:.2f}" if value is not None else "—",
                pct_status(value, league_ypp),
                f"League avg: {league_ypp:.2f}"
            )

        st.markdown(
            '<div class="legend-note">'
            'Green = 10%+ above league average • '
            'Yellow = within 10% • '
            'Red = 10%+ below league average'
            '</div>',
            unsafe_allow_html=True
        )


def render_volume_context(row):
    """Step 5: show whether raw yardage is being driven by defensive volume."""
    if row["opponent"] == "BYE":
        return

    with st.expander("View Volume Context"):
        if row["position"] == "RB":
            value = row["rush_attempts_faced_pg"]
            league = row["league_rush_attempts_faced_pg"]
            diff = row["rush_attempts_vs_league"]

            c1, c2, c3 = st.columns(3, gap="small")

            with c1:
                detail_metric(
                    "Rush Attempts Faced / Game",
                    f"{value:.1f}" if value is not None else "—",
                    pct_status(value, league),
                    f"League avg: {league:.1f}"
                )

            with c2:
                detail_metric(
                    "Rush Yards Allowed / Game",
                    f'{row["rush_yds_allowed"]:.1f}',
                    pct_status(
                        row["rush_yds_allowed"],
                        row["league_rush_yds_allowed"]
                    ),
                    f'League avg: {row["league_rush_yds_allowed"]:.1f}'
                )

            with c3:
                detail_metric(
                    "Rush YPC Allowed",
                    f'{row["rush_ypc_allowed"]:.2f}',
                    pct_status(
                        row["rush_ypc_allowed"],
                        row["league_rush_ypc"]
                    ),
                    f'League avg: {row["league_rush_ypc"]:.2f}'
                )

            if diff is not None:
                direction = "more" if diff > 0 else "fewer" if diff < 0 else "the same number of"
                st.caption(
                    f'{row["opponent"]} faces {abs(diff):.1f} {direction} rushing attempts '
                    f'per game than league average. This helps separate volume from efficiency.'
                )

        else:
            value = row["pass_dropbacks_faced_pg"]
            league = row["league_pass_dropbacks_faced_pg"]
            diff = row["pass_dropbacks_vs_league"]

            c1, c2, c3 = st.columns(3, gap="small")

            with c1:
                detail_metric(
                    "Pass Dropbacks Faced / Game",
                    f"{value:.1f}" if value is not None else "—",
                    pct_status(value, league),
                    f"League avg: {league:.1f}"
                )

            with c2:
                detail_metric(
                    "Pass Yards Allowed / Game",
                    f'{row["pass_yds_allowed"]:.1f}',
                    pct_status(
                        row["pass_yds_allowed"],
                        row["league_pass_yds_allowed"]
                    ),
                    f'League avg: {row["league_pass_yds_allowed"]:.1f}'
                )

            with c3:
                detail_metric(
                    "Net Pass Yds / Dropback",
                    f'{row["net_pass_yds_per_dropback"]:.2f}',
                    pct_status(
                        row["net_pass_yds_per_dropback"],
                        row["league_net_pass_ypd"]
                    ),
                    f'League avg: {row["league_net_pass_ypd"]:.2f}'
                )

            if diff is not None:
                direction = "more" if diff > 0 else "fewer" if diff < 0 else "the same number of"
                st.caption(
                    f'{row["opponent"]} faces {abs(diff):.1f} {direction} pass dropbacks '
                    f'per game than league average. This helps separate volume from efficiency.'
                )


def render_season_stats(detail_row):
    if detail_row["games_played"] is None:
        st.info(
            f'{detail_row["player"]} has not recorded a game yet this season.'
        )
        return

    games_played = int(detail_row["games_played"])

    st.caption(
        f"Production through {games_played} game"
        f"{'s' if games_played != 1 else ''}."
    )

    stat1, stat2, stat3, stat4 = st.columns(4, gap="small")

    with stat1:
        st.metric("Targets / Game", f'{detail_row["tgt_pg"]:.1f}')

    with stat2:
        st.metric("Receptions / Game", f'{detail_row["rec_pg"]:.1f}')

    with stat3:
        st.metric("Receiving Yds / Game", f'{detail_row["rec_yds_pg"]:.1f}')

    with stat4:
        st.metric("Rushing Yds / Game", f'{detail_row["rush_yds_pg"]:.1f}')

    td1, td2, td3 = st.columns(3, gap="small")

    with td1:
        st.metric("Games Played", games_played)

    with td2:
        st.metric("Rushing TDs", int(detail_row["rush_td"]))

    with td3:
        st.metric("Receiving TDs", int(detail_row["rec_td"]))


def compact_compare_card(row, detail):
    color = matchup_color(row["matchup_label"])
    logo = team_logo_url(row["team"])
    game_location = "vs" if row["h_a"] == "H" else "@"

    if row["opponent"] == "BYE":
        matchup = "BYE WEEK"
    else:
        matchup = f'{row["team"]} {game_location} {row["opponent"]}'

    logo_html = (
        f'<img src="{logo}" style="width:38px;height:38px;object-fit:contain;" />'
        if logo else ""
    )

    html = (
        f'<div style="border:1px solid rgba(255,255,255,0.08);border-radius:10px;'
        f'padding:12px 13px;margin-bottom:8px;">'
        f'<div style="display:flex;align-items:center;gap:10px;">'
        f'{logo_html}'
        f'<div>'
        f'<div style="font-size:20px;font-weight:700;">{row["player"]}</div>'
        f'<div style="font-size:12px;opacity:0.68;">{matchup} • {row["position"]}</div>'
        f'</div></div>'
        f'<div style="margin-top:9px;display:inline-block;padding:4px 8px;border-radius:6px;'
        f'background:{color};font-size:12px;font-weight:700;color:white;">'
        f'{row["matchup_label"]}</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)

    a, b = st.columns(2, gap="small")

    with a:
        st.metric("Defense Rank", ordinal(row["key_def_rank"]))

    with b:
        st.metric("Vs League Avg", row["efficiency_vs_league_display"])

    if row["position"] == "RB":
        v1 = row["rush_ypc_allowed"]
        v2 = row["rush_attempts_faced_pg"]
        label1 = "Rush YPC Allowed"
        label2 = "Rush Att Faced / G"
    else:
        v1 = row["net_pass_yds_per_dropback"]
        v2 = row["pass_dropbacks_faced_pg"]
        label1 = "Net Pass Yds / Dropback"
        label2 = "Pass Dropbacks / G"

    c, d = st.columns(2, gap="small")

    with c:
        st.metric(label1, f"{v1:.2f}" if v1 is not None else "—")

    with d:
        st.metric(label2, f"{v2:.1f}" if v2 is not None else "—")

    if detail["games_played"] is None:
        st.caption("No season production yet.")
    else:
        if row["position"] == "RB":
            st.caption(
                f'Season: {detail["rush_yds_pg"]:.1f} rush yds/G • '
                f'{detail["rec_pg"]:.1f} rec/G'
            )
        else:
            st.caption(
                f'Season: {detail["tgt_pg"]:.1f} targets/G • '
                f'{detail["rec_yds_pg"]:.1f} rec yds/G'
            )


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
<style>
.block-container {
    padding-top: 1.05rem;
    padding-bottom: 1.6rem;
    max-width: 1450px;
}

h1 {
    font-size: 2.0rem !important;
    margin-bottom: 0.15rem !important;
}

h2 {
    font-size: 1.35rem !important;
    margin-top: 0.55rem !important;
    margin-bottom: 0.30rem !important;
}

h3 {
    font-size: 1.15rem !important;
    margin-top: 0.45rem !important;
    margin-bottom: 0.25rem !important;
}

div[data-testid="stSelectbox"] {
    margin-bottom: 0.25rem;
}

div[data-testid="stExpander"] {
    margin-top: 0.30rem;
}

div[data-testid="stMetric"] {
    background-color: rgba(255,255,255,0.018);
    border: 1px solid rgba(255,255,255,0.06);
    padding: 10px 12px;
    border-radius: 9px;
}

div[data-testid="stMetricLabel"] {
    font-size: 11px;
}

div[data-testid="stMetricValue"] {
    font-size: 22px;
}

hr {
    margin-top: 0.8rem !important;
    margin-bottom: 0.8rem !important;
}

.small-note {
    font-size: 11px;
    opacity: 0.62;
    margin-top: 2px;
}

.legend-note {
    font-size: 10px;
    opacity: 0.52;
    margin-top: 6px;
}

.takeaway-box {
    margin-top: 8px;
    margin-bottom: 6px;
    padding: 9px 11px;
    border-radius: 8px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.07);
    font-size: 12px;
    line-height: 1.35;
}
</style>
""",
    unsafe_allow_html=True
)


# ============================================================
# APP HEADER
# ============================================================

st.title("Fantasy Football Matchup Tool")

st.caption(
    "Explore weekly RB, WR and TE matchups using opponent defensive production, "
    "efficiency, league averages and volume context."
)


# ============================================================
# TABS
# ============================================================

explore_tab, compare_tab = st.tabs([
    "Player Explorer",
    "Compare Players"
])


# ============================================================
# PLAYER EXPLORER
# ============================================================

with explore_tab:
    st.subheader("Player Explorer")

    selected_label = st.selectbox(
        "Search for a player",
        list(PLAYER_OPTIONS.keys()),
        key="explorer_player"
    )

    selected_id = PLAYER_OPTIONS[selected_label]

    row = get_matchup_row(selected_id)
    detail_row = get_detail_row(selected_id)

    header_block(row)
    game_info(row)
    render_main_matchup(row)
    render_defense_details(row)
    render_volume_context(row)

    st.divider()
    st.subheader(f'{row["player"]} — Season Stats')
    render_season_stats(detail_row)


# ============================================================
# PLAYER COMPARISON
# ============================================================

with compare_tab:
    st.subheader("Compare Players")

    st.caption(
        "Compare matchup context side by side. This view does not make a lineup "
        "decision for you—it shows the information so you can interpret it in "
        "the context of your roster and week."
    )

    labels = list(PLAYER_OPTIONS.keys())

    default_b = 1 if len(labels) > 1 else 0

    select_a, select_b = st.columns(2)

    with select_a:
        label_a = st.selectbox(
            "Player A",
            labels,
            index=0,
            key="compare_a"
        )

    with select_b:
        label_b = st.selectbox(
            "Player B",
            labels,
            index=default_b,
            key="compare_b"
        )

    id_a = PLAYER_OPTIONS[label_a]
    id_b = PLAYER_OPTIONS[label_b]

    if id_a == id_b:
        st.warning("Choose two different players to compare.")
    else:
        row_a = get_matchup_row(id_a)
        row_b = get_matchup_row(id_b)
        detail_a = get_detail_row(id_a)
        detail_b = get_detail_row(id_b)

        left, right = st.columns(2, gap="large")

        with left:
            compact_compare_card(row_a, detail_a)
            st.markdown(
                f'<div class="takeaway-box">{matchup_takeaway(row_a)}</div>',
                unsafe_allow_html=True
            )

        with right:
            compact_compare_card(row_b, detail_b)
            st.markdown(
                f'<div class="takeaway-box">{matchup_takeaway(row_b)}</div>',
                unsafe_allow_html=True
            )

        st.divider()
        st.caption(
            "Tip: matchup quality is only one part of a fantasy decision. "
            "Role, health, expected workload and your available alternatives can "
            "change how you use the comparison."
        )
