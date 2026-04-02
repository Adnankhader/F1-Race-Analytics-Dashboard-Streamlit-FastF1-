# Generated from: project (4).ipynb
# Converted at: 2026-04-01T07:49:05.906Z
# Next step (optional): refactor into modules & generate tests with RunCell
# Quick start: pip install runcell

"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              F1 INTERACTIVE ANALYTICS DASHBOARD — STREAMLIT APP             ║
║                                                                              ║
║  HOW TO RUN:                                                                 ║
║    1. Open your terminal / Anaconda prompt                                   ║
║    2. Install dependencies:                                                  ║
║         pip install streamlit fastf1 matplotlib pandas numpy seaborn        ║
║    3. Run the app:                                                            ║
║         streamlit run f1_dashboard.py                                        ║
║    4. A browser tab opens automatically at http://localhost:8501             ║
║                                                                              ║
║  STRUCTURE:                                                                  ║
║    Section 1 — Imports & page config                                         ║
║    Section 2 — Helper / data loading functions                               ║
║    Section 3 — Session Overview (Qualifying)                                 ║
║    Section 4 — Session Overview (Race)                                       ║
║    Section 5 — Head to Head (Qualifying)                                     ║
║    Section 6 — Head to Head (Race)                                           ║
║    Section 7 — Main app router (sidebar + mode selection)                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  SECTION 1 — IMPORTS & PAGE CONFIG                                          │
# └─────────────────────────────────────────────────────────────────────────────┘

import streamlit as st          # the web framework — turns Python into a webpage
import fastf1                   # F1 data library
import fastf1.plotting          # helper for team colours
import matplotlib.pyplot as plt # all our charts
import matplotlib.colors as mcolors
import matplotlib.ticker as ticker
from matplotlib.collections import LineCollection  # used for track heatmap
import pandas as pd
import numpy as np
import seaborn as sns           # nicer boxplots
import warnings
import os
warnings.filterwarnings("ignore")  # suppress minor warnings so the UI stays clean

# ── Streamlit page setup ──────────────────────────────────────────────────────
# This MUST be the first Streamlit call in the file
st.set_page_config(
    page_title="F1 Analytics Dashboard",
    page_icon="🏎️",
    layout="wide",          # use full browser width
    initial_sidebar_state="expanded",
)

# ── Enable FastF1 cache ───────────────────────────────────────────────────────
# The cache saves downloaded data so you don't re-download every run.
# A folder called "f1_cache" will be created in the same directory as this file.


# Create the cache folder if it doesn't exist, then enable it
cache_path = "f1_cache"
os.makedirs(cache_path, exist_ok=True)   # exist_ok=True means no error if it already exists
fastf1.Cache.enable_cache(cache_path)

# ── Global matplotlib style ───────────────────────────────────────────────────
# Dark theme to match F1 aesthetics
plt.rcParams.update({
    "figure.facecolor":  "#0f0f0f",
    "axes.facecolor":    "#1a1a1a",
    "axes.edgecolor":    "#333333",
    "axes.labelcolor":   "#aaaaaa",
    "xtick.color":       "#aaaaaa",
    "ytick.color":       "#aaaaaa",
    "text.color":        "#ffffff",
    "grid.color":        "#2a2a2a",
    "grid.linewidth":    0.5,
    "legend.facecolor":  "#1a1a1a",
    "legend.edgecolor":  "#333333",
})

# ── Grand Prix list ───────────────────────────────────────────────────────────


YEAR_LIST = [2026,2025,2024, 2023, 2022, 2021]


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  SECTION 2 — HELPER FUNCTIONS                                               │
# └─────────────────────────────────────────────────────────────────────────────┘
# ── Dynamic schedule helpers ──────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def get_race_schedule(year: int) -> pd.DataFrame:
    """
    Fetch the real race calendar for a given year.
    Filters out pre-season testing so only actual race weekends appear.
    Cached — only downloads once per year, instant on repeat calls.
    """
    schedule = fastf1.get_event_schedule(year)
    # Remove testing events (they have EventFormat = "testing")
    schedule = schedule[schedule["EventFormat"] != "testing"].reset_index(drop=True)
    return schedule


@st.cache_data(show_spinner=False)
def get_available_drivers(year: int, gp: str, session_code: str) -> list:
    """
    Load just enough of a session to get the driver list.
    We set telemetry=False so this is fast (~3 seconds vs ~30 seconds).
    Returns a sorted list of driver abbreviations e.g. ['ALO', 'HAM', 'VER']
    """
    try:
        session = fastf1.get_session(year, gp, session_code)
        session.load(telemetry=False, weather=False, messages=False)
        drivers = sorted(session.laps["Driver"].dropna().unique().tolist())
        return drivers
    except Exception:
        return []   # return empty list if something goes wrong — handled in UI
@st.cache_data(show_spinner=False)
def load_session(year: int, gp: str, session_type: str):
    """
    Load and cache a FastF1 session.

    @st.cache_data means Streamlit remembers the result — if you call this
    function again with the same year/gp/session_type, it returns instantly
    without re-downloading anything.

    Parameters
    ----------
    year         : e.g. 2024
    gp           : e.g. "Bahrain"
    session_type : "Q" for qualifying, "R" for race

    Returns
    -------
    session object or None if loading failed
    """
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load(telemetry=True, weather=True, messages=False)
        return session
    except Exception as e:
        st.error(f"Could not load session: {e}")
        return None


def get_driver_color(driver: str, session) -> str:
    """
    Safely get a driver's official team colour.
    Falls back to grey if the colour isn't found.
    """
    try:
        return fastf1.plotting.get_driver_color(driver, session)
    except Exception:
        return "#888888"


def format_laptime(td) -> str:
    """
    Convert a pandas Timedelta like 0 days 00:01:29.456 → '1:29.456'
    Makes lap times human-readable in tables.
    """
    if pd.isnull(td):
        return "N/A"
    total_seconds = td.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"


def clean_laps(laps):
    """
    Remove outlier laps (pit laps, safety car laps, very slow laps).
    FastF1's pick_quicklaps() handles most of this automatically.
    We also drop rows where LapTime is null.
    """
    return (
        laps
        .pick_quicklaps()                        # removes clear outliers
        .dropna(subset=["LapTime"])              # must have a valid lap time
        .copy()
    )


def show_figure(fig):
    """
    Render a matplotlib figure in Streamlit and then close it.
    Always close figures after showing — otherwise they stack up in memory.
    """
    st.pyplot(fig)
    plt.close(fig)


def section_header(title: str, subtitle: str = ""):
    """Helper to render a consistent section header."""
    st.markdown(f"### {title}")
    if subtitle:
        st.caption(subtitle)
    st.markdown("---")


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  SECTION 3 — SESSION OVERVIEW: QUALIFYING                                   │
# └─────────────────────────────────────────────────────────────────────────────┘

def show_qualifying_overview(session):
    """
    Renders all qualifying analysis panels:
      3A. Session results table
      3B. Lap time distribution (boxplot only)
      3C. Fastest sector heatmap
      3D. Fastest lap overview & gap to pole
      3E. Circuit map with sector-wise fastest times
    """

    st.markdown("## Qualifying Analysis")
    laps = session.laps

    # ── 3A. SESSION RESULTS TABLE ─────────────────────────────────────────────
    section_header("Session Results", "Final qualifying classification")

    results = session.results[[
        "Position", "Abbreviation", "FullName", "TeamName", "Q1", "Q2", "Q3"
    ]].copy()

    for col in ["Q1", "Q2", "Q3"]:
        results[col] = results[col].apply(format_laptime)

    results = results.sort_values("Position").reset_index(drop=True)
    st.dataframe(results, use_container_width=True, hide_index=True)

    # ── 3B. LAP TIME DISTRIBUTION (boxplot only) ──────────────────────────────
    section_header("Lap Time Distribution", "All valid laps per driver — spread shows consistency")

    valid_laps = clean_laps(laps).copy()
    valid_laps["LapTime_s"] = valid_laps["LapTime"].dt.total_seconds()

    driver_order = (
        valid_laps.groupby("Driver")["LapTime_s"]
        .min()
        .sort_values()
        .index.tolist()
    )

    fig, ax = plt.subplots(figsize=(14, 5))
    for i, driver in enumerate(driver_order):
        d = valid_laps[valid_laps["Driver"] == driver]["LapTime_s"]
        color = get_driver_color(driver, session)
        ax.boxplot(
            d, positions=[i], widths=0.5,
            patch_artist=True,
            boxprops=dict(facecolor=color, alpha=0.7),
            medianprops=dict(color="white", linewidth=1.5),
            whiskerprops=dict(color="#aaaaaa"),
            capprops=dict(color="#aaaaaa"),
            flierprops=dict(marker="o", color=color, alpha=0.3, markersize=3),
        )
    ax.set_xticks(range(len(driver_order)))
    ax.set_xticklabels(driver_order, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Lap time (s)")
    ax.set_title("Lap Time Distribution")
    ax.grid(axis="y")
    plt.tight_layout()
    show_figure(fig)

    # ── 3C. FASTEST SECTOR HEATMAP ────────────────────────────────────────────
    section_header("Sector Time Heatmap", "Lower = faster. Colour intensity shows relative speed per sector.")

    sector_data = {}
    for driver in driver_order:
        d = valid_laps[valid_laps["Driver"] == driver]
        sector_data[driver] = {
            "S1": d["Sector1Time"].dt.total_seconds().min(),
            "S2": d["Sector2Time"].dt.total_seconds().min(),
            "S3": d["Sector3Time"].dt.total_seconds().min(),
        }

    sector_df   = pd.DataFrame(sector_data).T.loc[driver_order]
    sector_norm = sector_df.copy()
    for col in sector_norm.columns:
        col_min = sector_norm[col].min()
        col_max = sector_norm[col].max()
        sector_norm[col] = (sector_norm[col] - col_min) / (col_max - col_min + 1e-9)

    fig, ax = plt.subplots(figsize=(6, len(driver_order) * 0.45 + 1))
    im = ax.imshow(sector_norm.values, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=1)

    for row_i, driver in enumerate(driver_order):
        for col_j, sector in enumerate(["S1", "S2", "S3"]):
            val = sector_df.loc[driver, sector]
            text_color = "white" if sector_norm.loc[driver, sector] > 0.5 else "black"
            ax.text(col_j, row_i, f"{val:.3f}",
                    ha="center", va="center", fontsize=8, color=text_color)

    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["Sector 1", "Sector 2", "Sector 3"])
    ax.set_yticks(range(len(driver_order)))
    ax.set_yticklabels(driver_order, fontsize=8)
    ax.set_title("Best Sector Times Heatmap (red = slowest, green = fastest)")
    plt.colorbar(im, ax=ax, label="Relative pace (0=fastest, 1=slowest)")
    plt.tight_layout()
    show_figure(fig)

    # ── 3D. FASTEST LAP OVERVIEW & GAP TO POLE ────────────────────────────────
    section_header("Fastest Lap Overview", "Each driver's best lap and gap to pole position")

    fastest_laps = []
    for driver in driver_order:
        d = valid_laps[valid_laps["Driver"] == driver]
        if d.empty:
            continue
        best = d.loc[d["LapTime_s"].idxmin()]
        fastest_laps.append({
            "Driver":       driver,
            "Team":         best.get("Team", ""),
            "FastestLap_s": best["LapTime_s"],
            "FastestLap":   format_laptime(best["LapTime"]),
        })

    fastest_df = pd.DataFrame(fastest_laps).sort_values("FastestLap_s").reset_index(drop=True)
    pole_time  = fastest_df["FastestLap_s"].min()
    fastest_df["Gap to Pole"] = fastest_df["FastestLap_s"].apply(
        lambda x: f"+{x - pole_time:.3f}s" if x != pole_time else "POLE"
    )

    fig, ax = plt.subplots(figsize=(9, len(fastest_df) * 0.45 + 1))
    gaps   = fastest_df["FastestLap_s"] - pole_time
    colors = [get_driver_color(d, session) for d in fastest_df["Driver"]]
    bars   = ax.barh(fastest_df["Driver"], gaps, color=colors, edgecolor="#333333", height=0.6)

    for bar, gap in zip(bars, gaps):
        ax.text(
            bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
            f"+{gap:.3f}s" if gap > 0 else "POLE",
            va="center", fontsize=8, color="white",
        )

    ax.invert_yaxis()
    ax.set_xlabel("Gap to pole (seconds)")
    ax.set_title("Gap to Pole Position")
    ax.grid(axis="x")
    plt.tight_layout()
    show_figure(fig)

    st.dataframe(
        fastest_df[["Driver", "Team", "FastestLap", "Gap to Pole"]],
        use_container_width=True, hide_index=True
    )

    # ── 3E. CIRCUIT MAP — SECTOR-WISE FASTEST TIMES ───────────────────────────
    section_header(
        "Circuit Map — Sector Fastest Times",
        "Track coloured by sector. Annotation shows who set the fastest time in each sector and by how much."
    )

    # We need telemetry from the overall fastest lap to draw the track shape.
    # We use the pole lap because it's guaranteed to be a complete, clean lap.
    try:
        pole_driver = fastest_df.iloc[0]["Driver"]
        pole_lap    = laps.pick_drivers(pole_driver).pick_fastest()
        tel         = pole_lap.get_telemetry().add_distance()
    except Exception as e:
        st.warning(f"Could not load telemetry for circuit map: {e}")
        return

    x = tel["X"].values.astype(float)
    y = tel["Y"].values.astype(float)

    # ── Find sector boundary indices ──────────────────────────────────────────
    # FastF1 stores the distance at which each sector ends on the lap object.
    # We find the closest telemetry point to each boundary distance.
    try:
        s1_end_dist = pole_lap["Sector1SessionTime"]   # not distance — use time
        # Alternative approach: use distance fractions (more reliable across tracks)
        # Sector boundaries are roughly at 1/3 and 2/3 of the lap distance,
        # but FastF1 gives us the exact session times — we match those to telemetry.
        total_dist  = tel["Distance"].max()

        # Map sector end times to telemetry indices via SessionTime
        s1_end_time = pole_lap["Sector1SessionTime"]
        s2_end_time = pole_lap["Sector2SessionTime"]

        # Find index in telemetry closest to each sector boundary time
        s1_idx = (tel["SessionTime"] - s1_end_time).abs().idxmin()
        s2_idx = (tel["SessionTime"] - s2_end_time).abs().idxmin()

        # Split telemetry into three sectors
        s1_x, s1_y = x[:s1_idx],        y[:s1_idx]
        s2_x, s2_y = x[s1_idx:s2_idx],  y[s1_idx:s2_idx]
        s3_x, s3_y = x[s2_idx:],        y[s2_idx:]

    except Exception:
        # Fallback: split by distance thirds if session time approach fails
        n = len(x)
        s1_x, s1_y = x[:n//3],        y[:n//3]
        s2_x, s2_y = x[n//3:2*n//3],  y[n//3:2*n//3]
        s3_x, s3_y = x[2*n//3:],      y[2*n//3:]

    # ── Find fastest driver per sector ────────────────────────────────────────
    # For each sector, find the driver with the minimum sector time.
    sector_winners = {}
    for sector_key, col in [("S1", "Sector1Time"), ("S2", "Sector2Time"), ("S3", "Sector3Time")]:
        best_time   = None
        best_driver = None
        for driver in driver_order:
            d = valid_laps[valid_laps["Driver"] == driver][col].dt.total_seconds()
            if d.empty or d.isna().all():
                continue
            driver_best = d.min()
            if best_time is None or driver_best < best_time:
                best_time   = driver_best
                best_driver = driver
        sector_winners[sector_key] = {
            "driver": best_driver,
            "time":   best_time,
            "color":  get_driver_color(best_driver, session) if best_driver else "#888888",
        }

    # ── Draw the circuit ──────────────────────────────────────────────────────
    SECTOR_COLORS = {
        "S1": "#e8002d",   # red
        "S2": "#ffd700",   # yellow / gold
        "S3": "#00d2be",   # teal / F1 green
    }

    fig, ax = plt.subplots(figsize=(10, 8))

    # Faint grey background track for visual depth
    ax.plot(x, y, color="#2a2a2a", linewidth=14,
            solid_capstyle="round", solid_joinstyle="round", zorder=1)

    # Draw each sector in its colour
    for (sx, sy), sector_key in [
        ((s1_x, s1_y), "S1"),
        ((s2_x, s2_y), "S2"),
        ((s3_x, s3_y), "S3"),
    ]:
        if len(sx) > 1:
            ax.plot(sx, sy,
                    color=SECTOR_COLORS[sector_key],
                    linewidth=6,
                    solid_capstyle="round",
                    solid_joinstyle="round",
                    zorder=2)

    # ── Sector boundary markers ───────────────────────────────────────────────
    # White dot at the start of each sector boundary
    boundaries = [
        (s1_x[-1], s1_y[-1]) if len(s1_x) > 0 else (x[0], y[0]),
        (s2_x[-1], s2_y[-1]) if len(s2_x) > 0 else (x[0], y[0]),
    ]
    for bx, by in boundaries:
        ax.scatter(bx, by, color="white", s=80, zorder=5,
                   edgecolors="#0f0f0f", linewidths=1.5)

    # Start / finish marker
    ax.scatter(x[0], y[0], color="white", s=150, marker="D",
               zorder=6, edgecolors="#0f0f0f", linewidths=1.5)

    # ── Sector annotation boxes ───────────────────────────────────────────────
    # Place a label near the midpoint of each sector showing:
    #   SECTOR X | DRIVER | time
    for (sx, sy), sector_key in [
        ((s1_x, s1_y), "S1"),
        ((s2_x, s2_y), "S2"),
        ((s3_x, s3_y), "S3"),
    ]:
        if len(sx) < 2:
            continue

        # Use midpoint of the sector for label placement
        mid = len(sx) // 2
        lx, ly = sx[mid], sy[mid]

        winner = sector_winners[sector_key]
        driver = winner["driver"] or "N/A"
        time_s = winner["time"]
        time_str = f"{int(time_s // 60)}:{time_s % 60:06.3f}" if time_s else "N/A"

        label = f"{sector_key}  ·  {driver}  ·  {time_str}"

        ax.annotate(
            label,
            xy=(lx, ly),
            xytext=(lx, ly),
            fontsize=8,
            fontweight="bold",
            color="white",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.5",
                facecolor=SECTOR_COLORS[sector_key],
                edgecolor="white",
                linewidth=1,
                alpha=0.92,
            ),
            zorder=7,
        )

    # ── Legend ────────────────────────────────────────────────────────────────
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=SECTOR_COLORS["S1"], label=f"Sector 1 — {sector_winners['S1']['driver']}"),
        Patch(facecolor=SECTOR_COLORS["S2"], label=f"Sector 2 — {sector_winners['S2']['driver']}"),
        Patch(facecolor=SECTOR_COLORS["S3"], label=f"Sector 3 — {sector_winners['S3']['driver']}"),
    ]
    ax.legend(handles=legend_elements, loc="upper right",
              fontsize=9, facecolor="#1a1a1a", edgecolor="#333333", labelcolor="white")

    ax.axis("equal")
    ax.axis("off")
    fig.suptitle(
        f"Circuit Map — Sector Fastest Times\n"
        f"{session.event['EventName']} {session.event.year} Qualifying",
        color="white", fontsize=12, fontweight="bold"
    )
    plt.tight_layout()
    show_figure(fig)

    # Clean summary table below the map
    summary_rows = []
    for sector_key, col in [("S1", "Sector1Time"), ("S2", "Sector2Time"), ("S3", "Sector3Time")]:
        w = sector_winners[sector_key]
        summary_rows.append({
            "Sector":  sector_key,
            "Driver":  w["driver"],
            "Time":    f"{w['time']:.3f}s" if w["time"] else "N/A",
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  SECTION 4 — SESSION OVERVIEW: RACE                                         │
# └─────────────────────────────────────────────────────────────────────────────┘

def show_race_overview(session):
    """
    Renders all race analysis panels:
      4A. Race results (grid vs finish)
      4B. Lap time trend (pace evolution)
      4C. Lap time distribution (boxplot)
      4D. Position changes over race
      4E. Pit stop analysis
      4F. Tyre strategy
    """

    st.markdown("## Race Analysis")
    laps = session.laps

    # Cleaned laps (no pit laps, no safety car laps)
    valid_laps = clean_laps(laps).copy()
    valid_laps["LapTime_s"] = valid_laps["LapTime"].dt.total_seconds()

    # Driver order by finishing position
    results = session.results.sort_values("Position").dropna(subset=["Position"])
    driver_order = results["Abbreviation"].tolist()

    # ── 4A. RACE RESULTS ──────────────────────────────────────────────────────
    section_header("Race Results", "Final classification and grid vs finish comparison")

    col1, col2 = st.columns(2)

    with col1:
        # Results table
        results_table = session.results[[
            "Position", "GridPosition", "Abbreviation", "FullName",
            "TeamName", "Points", "Status"
        ]].copy().sort_values("Position").reset_index(drop=True)
        st.dataframe(results_table, use_container_width=True, hide_index=True)

    with col2:
        # Grid vs finish scatter — shows who gained / lost positions
        fig, ax = plt.subplots(figsize=(6, 6))
        r = session.results.dropna(subset=["GridPosition", "Position"]).copy()
        r["GridPosition"] = r["GridPosition"].astype(int)
        r["Position"]     = r["Position"].astype(int)

        for _, row in r.iterrows():
            color = get_driver_color(row["Abbreviation"], session)
            # Line from grid to finish
            ax.plot(
                [0, 1], [row["GridPosition"], row["Position"]],
                color=color, linewidth=1.5, alpha=0.7
            )
            ax.text(-0.05, row["GridPosition"], row["Abbreviation"],
                    ha="right", va="center", fontsize=7, color=color)
            ax.text(1.05, row["Position"], row["Abbreviation"],
                    ha="left", va="center", fontsize=7, color=color)

        ax.set_xlim(-0.3, 1.3)
        ax.invert_yaxis()
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Grid", "Finish"], fontsize=10)
        ax.set_ylabel("Position")
        ax.set_title("Grid vs Finish Position")
        ax.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        show_figure(fig)

    # ── 4B. LAP TIME TREND ────────────────────────────────────────────────────
    # ── 4B. LAP TIME TREND ────────────────────────────────────────────────────
    section_header("Lap Time Trend", "Race pace by team — fastest driver per team only")

    # Step 1: Find the fastest driver per team based on median clean lap time.
    # We use median (not mean) because it's more robust to outlier laps.
    team_representative = {}
    for driver in driver_order:
        d = valid_laps[valid_laps["Driver"] == driver]
        if d.empty:
            continue
        # Get team name for this driver from results
        team_rows = results[results["Abbreviation"] == driver]
        if team_rows.empty:
            continue
        team = team_rows.iloc[0]["TeamName"]
        median_time = d["LapTime_s"].median()

        # Keep this driver only if they're faster (lower median) than whoever
        # we already stored for this team
        if team not in team_representative:
            team_representative[team] = (driver, median_time)
        else:
            _, current_best = team_representative[team]
            if median_time < current_best:
                team_representative[team] = (driver, median_time)

    # Step 2: Plot one line per team using that team's representative driver
    fig, ax = plt.subplots(figsize=(13, 5))

    for team, (driver, _) in sorted(team_representative.items()):
        d = valid_laps[valid_laps["Driver"] == driver].sort_values("LapNumber")
        if d.empty:
            continue
        color = get_driver_color(driver, session)

        # Raw lap times — thin and slightly transparent
        ax.plot(
            d["LapNumber"], d["LapTime_s"],
            color=color, linewidth=0.8, alpha=0.35,
        )
        # Rolling average — thick line, more readable
        # window=3 keeps it responsive; increase to 5 for smoother lines
        rolling = d["LapTime_s"].rolling(window=3, center=True, min_periods=1).mean()
        ax.plot(
            d["LapNumber"], rolling,
            color=color, linewidth=2.0, alpha=0.95,
            label=f"{driver}  ({team})",
        )

    ax.set_xlabel("Lap number")
    ax.set_ylabel("Lap time (s)")
    ax.set_title("Lap Time Trend — Fastest Driver per Team (3-lap rolling avg)")
    ax.legend(fontsize=7, loc="upper right", ncol=2)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    show_figure(fig)

    # ── 4C. LAP TIME DISTRIBUTION ─────────────────────────────────────────────
    section_header("Lap Time Distribution", "Boxplot of clean race laps — shows consistency")

    fig, ax = plt.subplots(figsize=(13, 5))
    for i, driver in enumerate(driver_order):
        d = valid_laps[valid_laps["Driver"] == driver]["LapTime_s"]
        if d.empty:
            continue
        color = get_driver_color(driver, session)
        ax.boxplot(
            d, positions=[i], widths=0.5, patch_artist=True,
            boxprops=dict(facecolor=color, alpha=0.7),
            medianprops=dict(color="white", linewidth=1.5),
            whiskerprops=dict(color="#aaaaaa"),
            capprops=dict(color="#aaaaaa"),
            flierprops=dict(marker="o", color=color, alpha=0.3, markersize=3),
        )

    ax.set_xticks(range(len(driver_order)))
    ax.set_xticklabels(driver_order, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Lap time (s)")
    ax.set_title("Race Lap Time Distribution (cleaned laps only)")
    ax.grid(axis="y")
    plt.tight_layout()
    show_figure(fig)

    # ── 4D. POSITION CHANGE OVER RACE ─────────────────────────────────────────
    section_header("Position Changes", "Every driver's position from lap 1 to the flag")

    all_laps = laps[["Driver", "LapNumber", "Position"]].dropna(subset=["Position"]).copy()
    all_laps["Position"]  = all_laps["Position"].astype(int)
    all_laps["LapNumber"] = all_laps["LapNumber"].astype(int)
    total_laps = int(all_laps["LapNumber"].max())

    fig, ax = plt.subplots(figsize=(14, 8))

    for driver in driver_order:
        d = all_laps[all_laps["Driver"] == driver].sort_values("LapNumber")
        if d.empty:
            continue
        color = get_driver_color(driver, session)
        ax.plot(d["LapNumber"], d["Position"],
                color=color, linewidth=1.4, alpha=0.85)
        # Driver label at the finish line
        last = d.iloc[-1]
        ax.text(last["LapNumber"] + 0.5, last["Position"],
                driver, color=color, fontsize=7, va="center")

    ax.set_ylim(len(driver_order) + 0.5, 0.5)   # P1 at top
    ax.set_xlim(0, total_laps + 6)
    ax.set_xlabel("Lap")
    ax.set_ylabel("Position")
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.set_yticklabels([f"P{i}" for i in range(0, len(driver_order) + 2)], fontsize=8)
    ax.set_title("Race Position Changes")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    show_figure(fig)

       # ── 4F. TYRE STRATEGY ─────────────────────────────────────────────────────
    section_header("Tyre Strategy", "Stint lengths coloured by compound")

    COMPOUND_COLORS = {
        "SOFT":   "#e8002d",   # red
        "MEDIUM": "#ffd700",   # yellow
        "HARD":   "#f0f0f0",   # white
        "INTER":  "#39b54a",   # green
        "WET":    "#0067ff",   # blue
        "UNKNOWN":"#888888",
    }

    strat = laps[["Driver", "Stint", "Compound", "LapNumber"]].dropna().copy()
    strat["Compound"] = strat["Compound"].str.upper().fillna("UNKNOWN")

    fig, ax = plt.subplots(figsize=(14, len(driver_order) * 0.55 + 1))

    for y_pos, driver in enumerate(driver_order):
        d = strat[strat["Driver"] == driver]
        if d.empty:
            continue
        for stint_num in sorted(d["Stint"].unique()):
            stint_laps = d[d["Stint"] == stint_num]["LapNumber"]
            compound   = d[d["Stint"] == stint_num]["Compound"].iloc[0]
            color      = COMPOUND_COLORS.get(compound, "#888888")

            start = stint_laps.min()
            end   = stint_laps.max()
            length = end - start + 1

            ax.barh(
                y_pos, length, left=start,
                color=color, edgecolor="#333333",
                height=0.6, alpha=0.9,
            )
            # Label the compound inside the bar if wide enough
            if length >= 4:
                ax.text(
                    start + length / 2, y_pos,
                    compound[0],   # just first letter: S / M / H / I / W
                    ha="center", va="center",
                    fontsize=7, fontweight="bold",
                    color="black" if compound in ["MEDIUM", "HARD"] else "white",
                )

    ax.set_yticks(range(len(driver_order)))
    ax.set_yticklabels(driver_order, fontsize=8)
    ax.set_xlabel("Lap number")
    ax.set_title("Tyre Strategy")
    ax.grid(axis="x", alpha=0.3)

    # Manual legend for compound colours
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=c, edgecolor="#333333", label=k)
        for k, c in COMPOUND_COLORS.items() if k != "UNKNOWN"
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
    plt.tight_layout()
    show_figure(fig)


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  SECTION 5 — HEAD TO HEAD: QUALIFYING                                       │
# └─────────────────────────────────────────────────────────────────────────────┘

def show_h2h_qualifying(session, d1: str, d2: str):
    """
    Head-to-head qualifying comparison between two drivers:
      5A. Sector-wise bar chart
      5B. Delta to fastest lap
      5C. Speed trap analysis
      5D. Throttle application on fastest lap
      5E. Full telemetry comparison (speed, throttle, brake, gear)
    """

    st.markdown(f"## Head to Head — Qualifying: {d1} vs {d2}")

    laps = session.laps
    color1 = get_driver_color(d1, session)
    color2 = get_driver_color(d2, session)

    # Get fastest laps
    try:
        lap1 = laps.pick_drivers(d1).pick_fastest()
        lap2 = laps.pick_drivers(d2).pick_fastest()
    except Exception as e:
        st.error(f"Could not get fastest laps: {e}")
        return

    tel1 = lap1.get_telemetry().add_distance()
    tel2 = lap2.get_telemetry().add_distance()

    t1_s = lap1["LapTime"].total_seconds()
    t2_s = lap2["LapTime"].total_seconds()

    # ── 5A. SECTOR-WISE COMPARISON ────────────────────────────────────────────
    # ── 5A. SECTOR-WISE COMPARISON ────────────────────────────────────────────
    section_header("Sector Times", "Side-by-side comparison of best sector times")

    sectors = ["Sector1Time", "Sector2Time", "Sector3Time"]
    labels  = ["Sector 1", "Sector 2", "Sector 3"]

    s1_times = [lap1[s].total_seconds() for s in sectors]
    s2_times = [lap2[s].total_seconds() for s in sectors]

    x     = np.arange(3)
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width/2, s1_times, width, label=d1,
                   color=color1, edgecolor="#333333", alpha=0.9)
    bars2 = ax.bar(x + width/2, s2_times, width, label=d2,
                   color=color2, edgecolor="#333333", alpha=0.9)

    for bar, t in zip(bars1, s1_times):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{t:.3f}s", ha="center", va="bottom", fontsize=8, color=color1)
    for bar, t in zip(bars2, s2_times):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{t:.3f}s", ha="center", va="bottom", fontsize=8, color=color2)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Time (s)")
    ax.set_title("Sector Time Comparison")
    ax.legend()
    ax.grid(axis="y")
    plt.tight_layout()
    show_figure(fig)

    # ── 5A-ii. CIRCUIT MAPS — one per driver ──────────────────────────────────
    # Each map colours the three sectors in their own colour and annotates
    # that driver's sector time in each zone.

    SECTOR_COLORS = {
        "S1": "#e8002d",   # red
        "S2": "#ffd700",   # gold
        "S3": "#00d2be",   # teal
    }

    def _draw_circuit_map(ax, lap, tel, driver_color, driver_name,
                          s1_t, s2_t, s3_t):
        """
        Draw a single circuit map for one driver.
        Sectors are coloured S1=red / S2=gold / S3=teal.
        Each sector gets an annotation showing the driver's time for that sector.

        Parameters
        ----------
        ax          : matplotlib Axes to draw on
        lap         : FastF1 lap object (used to find sector boundary times)
        tel         : telemetry DataFrame with X, Y, SessionTime, Distance
        driver_color: team colour hex string (used for the start/finish dot)
        driver_name : abbreviation string for the title
        s1_t/s2_t/s3_t : sector times in seconds (float)
        """
        x_coords = tel["X"].values.astype(float)
        y_coords = tel["Y"].values.astype(float)

        # ── Find sector boundary indices via SessionTime ───────────────────────
        try:
            s1_end_time = lap["Sector1SessionTime"]
            s2_end_time = lap["Sector2SessionTime"]
            s1_idx = (tel["SessionTime"] - s1_end_time).abs().idxmin()
            s2_idx = (tel["SessionTime"] - s2_end_time).abs().idxmin()
        except Exception:
            # Fallback: split by distance thirds
            n = len(x_coords)
            s1_idx = n // 3
            s2_idx = 2 * n // 3

        # Split into three sector arrays
        sectors_coords = {
            "S1": (x_coords[:s1_idx],       y_coords[:s1_idx]),
            "S2": (x_coords[s1_idx:s2_idx], y_coords[s1_idx:s2_idx]),
            "S3": (x_coords[s2_idx:],       y_coords[s2_idx:]),
        }
        sector_times = {"S1": s1_t, "S2": s2_t, "S3": s3_t}

        # ── Background track (dark grey, slightly thicker) ────────────────────
        ax.plot(x_coords, y_coords, color="#2a2a2a", linewidth=14,
                solid_capstyle="round", solid_joinstyle="round", zorder=1)

        # ── Coloured sector lines ─────────────────────────────────────────────
        for sector_key, (sx, sy) in sectors_coords.items():
            if len(sx) > 1:
                ax.plot(sx, sy,
                        color=SECTOR_COLORS[sector_key],
                        linewidth=6,
                        solid_capstyle="round",
                        solid_joinstyle="round",
                        zorder=2)

        # ── Sector boundary dots ──────────────────────────────────────────────
        for boundary_idx in [s1_idx, s2_idx]:
            if 0 < boundary_idx < len(x_coords):
                ax.scatter(x_coords[boundary_idx], y_coords[boundary_idx],
                           color="white", s=60, zorder=5,
                           edgecolors="#0f0f0f", linewidths=1.2)

        # ── Start / finish marker ─────────────────────────────────────────────
        ax.scatter(x_coords[0], y_coords[0],
                   color=driver_color, s=120, marker="D",
                   zorder=6, edgecolors="white", linewidths=1.2)

        # ── Sector time annotations ───────────────────────────────────────────
        # Place the label at the midpoint of each sector
        for sector_key, (sx, sy) in sectors_coords.items():
            if len(sx) < 2:
                continue
            mid   = len(sx) // 2
            lx, ly = sx[mid], sy[mid]
            t_val  = sector_times[sector_key]

            # Format as M:SS.mmm if >= 60s, else just SS.mmm
            if t_val >= 60:
                time_str = f"{int(t_val//60)}:{t_val%60:06.3f}"
            else:
                time_str = f"{t_val:.3f}s"

            ax.annotate(
                f"{sector_key}  {time_str}",
                xy=(lx, ly),
                fontsize=7.5,
                fontweight="bold",
                color="white",
                ha="center",
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.4",
                    facecolor=SECTOR_COLORS[sector_key],
                    edgecolor="white",
                    linewidth=0.8,
                    alpha=0.93,
                ),
                zorder=7,
            )

        ax.axis("equal")
        ax.axis("off")
        ax.set_title(driver_name, color="white", fontsize=11, fontweight="bold", pad=6)

    # ── Draw both maps side by side ───────────────────────────────────────────
    try:
        fig, axes = plt.subplots(1, 2, figsize=(16, 7))

        _draw_circuit_map(
            ax=axes[0],
            lap=lap1, tel=tel1,
            driver_color=color1, driver_name=d1,
            s1_t=s1_times[0], s2_t=s1_times[1], s3_t=s1_times[2],
        )

        _draw_circuit_map(
            ax=axes[1],
            lap=lap2, tel=tel2,
            driver_color=color2, driver_name=d2,
            s1_t=s2_times[0], s2_t=s2_times[1], s3_t=s2_times[2],
        )

        # Shared legend for sector colours
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=SECTOR_COLORS["S1"], label="Sector 1"),
            Patch(facecolor=SECTOR_COLORS["S2"], label="Sector 2"),
            Patch(facecolor=SECTOR_COLORS["S3"], label="Sector 3"),
        ]
        fig.legend(
            handles=legend_elements,
            loc="lower center",
            ncol=3,
            fontsize=9,
            facecolor="#1a1a1a",
            edgecolor="#333333",
            labelcolor="white",
            framealpha=0.9,
        )

        fig.suptitle(
            f"Circuit Map — Sector Times on Fastest Lap\n"
            f"{session.event['EventName']} {session.event.year} Qualifying",
            color="white", fontsize=12, fontweight="bold"
        )
        plt.tight_layout(rect=[0, 0.06, 1, 1])  # leave room for legend at bottom
        show_figure(fig)

    except Exception as e:
        st.warning(f"Could not draw circuit maps: {e}")

    # ── Sector delta summary table ─────────────────────────────────────────────
    # Shows the time difference per sector so it's easy to read at a glance
    delta_rows = []
    for label, t1, t2 in zip(labels, s1_times, s2_times):
        diff = t1 - t2   # negative = d1 faster, positive = d2 faster
        faster = d1 if diff < 0 else d2
        delta_rows.append({
            "Sector":  label,
            d1:        f"{t1:.3f}s",
            d2:        f"{t2:.3f}s",
            "Delta":   f"{abs(diff):.3f}s",
            "Faster":  faster,
        })
    st.dataframe(
        pd.DataFrame(delta_rows),
        use_container_width=True,
        hide_index=True,
    )

    # ── 5B. DELTA TO SESSION FASTEST ──────────────────────────────────────────
    section_header("Gap to Session Best", "How far each driver is from the overall fastest lap")

    session_best = laps.pick_quicklaps()["LapTime"].dt.total_seconds().min()
    gap1 = t1_s - session_best
    gap2 = t2_s - session_best

    col1, col2 = st.columns(2)
    with col1:
        st.metric(d1, format_laptime(lap1["LapTime"]), delta=f"+{gap1:.3f}s vs pole")
    with col2:
        st.metric(d2, format_laptime(lap2["LapTime"]), delta=f"+{gap2:.3f}s vs pole")

    # Delta between the two drivers
    delta = t1_s - t2_s
    winner = d1 if delta < 0 else d2
    st.info(f"**{winner}** is faster by **{abs(delta):.3f}s**")

    # ── 5C. DELTA LAP TIME (DRIVER vs DRIVER across distance) ─────────────────
    section_header("Delta Time Across Lap", "Where on the track each driver gains or loses time")

    # Interpolate onto a common distance axis
    dist_common = np.linspace(
        0,
        min(tel1["Distance"].max(), tel2["Distance"].max()),
        1000
    )
    time1 = np.interp(dist_common, tel1["Distance"], tel1["SessionTime"].dt.total_seconds())
    time2 = np.interp(dist_common, tel2["Distance"], tel2["SessionTime"].dt.total_seconds())
    delta_arr = (time1 - time1[0]) - (time2 - time2[0])

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.axhline(0, color="#444444", linewidth=0.8, linestyle="--")
    ax.fill_between(dist_common, delta_arr, 0,
                    where=(delta_arr < 0), color=color1, alpha=0.4, label=f"{d1} faster")
    ax.fill_between(dist_common, delta_arr, 0,
                    where=(delta_arr > 0), color=color2, alpha=0.4, label=f"{d2} faster")
    ax.plot(dist_common, delta_arr, color="white", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel(f"Δ time (s)\n← {d1} faster | {d2} faster →")
    ax.set_title(f"Lap Delta — {d1} vs {d2}")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    show_figure(fig)

    # ── 5D. SPEED TRAP ────────────────────────────────────────────────────────
    section_header("Speed Trap", "Maximum speed recorded on each driver's fastest lap")

    max1 = tel1["Speed"].max()
    max2 = tel2["Speed"].max()

    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"{d1} — Top speed", f"{max1:.1f} km/h")
    with col2:
        st.metric(f"{d2} — Top speed", f"{max2:.1f} km/h",
                  delta=f"{max2 - max1:+.1f} km/h vs {d1}")

    # ── 5E. FULL TELEMETRY COMPARISON ─────────────────────────────────────────
    section_header("Full Telemetry — Fastest Lap", "Speed, throttle, brake, and gear across the lap")

    import matplotlib.gridspec as gridspec

    fig = plt.figure(figsize=(13, 14))
    gs  = gridspec.GridSpec(5, 1, figure=fig, hspace=0.08,
                            height_ratios=[2, 2, 1.2, 1.2, 1.2])
    axes = [fig.add_subplot(gs[i]) for i in range(5)]

    channels = [
        ("Speed",    "Speed (km/h)"),
        ("Throttle", "Throttle %"),
    ]

    # Speed
    axes[0].plot(tel1["Distance"], tel1["Speed"], color=color1, linewidth=1.2, label=d1)
    axes[0].plot(tel2["Distance"], tel2["Speed"], color=color2, linewidth=1.2, label=d2, linestyle="--")
    axes[0].set_ylabel("Speed (km/h)")
    axes[0].legend(fontsize=8)
    axes[0].tick_params(labelbottom=False)

    # Throttle
    axes[1].plot(tel1["Distance"], tel1["Throttle"], color=color1, linewidth=1.0, alpha=0.9)
    axes[1].plot(tel2["Distance"], tel2["Throttle"], color=color2, linewidth=1.0, alpha=0.9, linestyle="--")
    axes[1].set_ylabel("Throttle %")
    axes[1].set_ylim(-5, 105)
    axes[1].tick_params(labelbottom=False)

    # Brake
    axes[2].fill_between(tel1["Distance"], tel1["Brake"].astype(int)*100,
                          alpha=0.5, color=color1, step="mid")
    axes[2].fill_between(tel2["Distance"], tel2["Brake"].astype(int)*100,
                          alpha=0.4, color=color2, step="mid")
    axes[2].set_ylabel("Brake")
    axes[2].set_yticks([0, 100])
    axes[2].set_yticklabels(["off", "on"])
    axes[2].tick_params(labelbottom=False)

    # Gear
    axes[3].step(tel1["Distance"], tel1["nGear"], color=color1, linewidth=1.0, where="post")
    axes[3].step(tel2["Distance"], tel2["nGear"], color=color2, linewidth=1.0, where="post", linestyle="--")
    axes[3].set_ylabel("Gear")
    axes[3].set_ylim(0, 9)
    axes[3].set_yticks(range(1, 9))
    axes[3].tick_params(labelbottom=False)

    # DRS
    drs1 = (tel1["DRS"] >= 8).astype(int)
    drs2 = (tel2["DRS"] >= 8).astype(int)
    axes[4].fill_between(tel1["Distance"], drs1, alpha=0.6, color=color1, step="mid", label=d1)
    axes[4].fill_between(tel2["Distance"], drs2 * -1, alpha=0.5, color=color2, step="mid", label=d2)
    axes[4].axhline(0, color="#444444", linewidth=0.5)
    axes[4].set_ylabel("DRS")
    axes[4].set_yticks([-1, 0, 1])
    axes[4].set_yticklabels([d2, "", d1])
    axes[4].set_xlabel("Distance (m)")

    for ax in axes:
        ax.grid(axis="x", alpha=0.2)
        ax.set_facecolor("#1a1a1a")

    fig.suptitle(
        f"Telemetry Comparison — {d1} ({format_laptime(lap1['LapTime'])}) "
        f"vs {d2} ({format_laptime(lap2['LapTime'])})",
        color="white", fontsize=12, fontweight="bold"
    )
    plt.tight_layout()
    show_figure(fig)


# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  SECTION 6 — HEAD TO HEAD: RACE                                             │
# └─────────────────────────────────────────────────────────────────────────────┘

def show_h2h_race(session, d1: str, d2: str):
    """
    Head-to-head race comparison between two drivers:
      6A. Start vs Finish positions
      6B. Lap time comparison (rolling average only)
      6C. Consistency (boxplot)
      6D. Tyre strategy comparison
      6E. Position comparison over laps
      6F. Sector pace circuit maps (average clean sector times)
    """

    st.markdown(f"## Head to Head — Race: {d1} vs {d2}")

    laps   = session.laps
    color1 = get_driver_color(d1, session)
    color2 = get_driver_color(d2, session)

    valid = clean_laps(laps).copy()
    valid["LapTime_s"] = valid["LapTime"].dt.total_seconds()

    d1_laps = valid[valid["Driver"] == d1].sort_values("LapNumber")
    d2_laps = valid[valid["Driver"] == d2].sort_values("LapNumber")

    # ── 6A. START vs FINISH POSITIONS ─────────────────────────────────────────
    section_header("Race Summary", "Grid position, finishing position and points scored")

    results = session.results
    def get_driver_summary(drv):
        row = results[results["Abbreviation"] == drv]
        if row.empty:
            return {}
        row = row.iloc[0]
        grid   = int(row["GridPosition"]) if pd.notna(row["GridPosition"]) else "N/A"
        finish = int(row["Position"])     if pd.notna(row["Position"])     else "N/A"
        gained = (grid - finish) if isinstance(grid, int) and isinstance(finish, int) else 0
        return {
            "Driver":        drv,
            "Team":          row.get("TeamName", ""),
            "Grid":          grid,
            "Finish":        finish,
            "Positions gained": gained,
            "Points":        int(row["Points"]) if pd.notna(row["Points"]) else 0,
            "Status":        row.get("Status", ""),
        }

    summary_d1 = get_driver_summary(d1)
    summary_d2 = get_driver_summary(d2)

    # Metric cards row
    col1, col2 = st.columns(2)
    for col, summary, color in [(col1, summary_d1, color1), (col2, summary_d2, color2)]:
        with col:
            gained = summary.get("Positions gained", 0)
            gained_str = f"+{gained}" if gained > 0 else str(gained)
            st.markdown(
                f"""
                <div style="border:1px solid {color}; border-radius:10px;
                            padding:14px 18px; margin-bottom:8px;">
                  <div style="font-size:20px; font-weight:700;
                              color:{color};">{summary['Driver']}</div>
                  <div style="font-size:12px; color:{color}; margin-bottom:10px;">
                      {summary['Team']}</div>
                  <table style="width:100%; font-size:13px; border-collapse:collapse;">
                    <tr>
                      <td style="padding:4px 0; color:black;">Grid</td>
                      <td style="padding:4px 0; font-weight:600;
                                 text-align:right;">P{summary['Grid']}</td>
                    </tr>
                    <tr>
                      <td style="padding:4px 0; color:black;">Finish</td>
                      <td style="padding:4px 0; font-weight:600;
                                 text-align:right;">P{summary['Finish']}</td>
                    </tr>
                    <tr>
                      <td style="padding:4px 0; color:black;">Positions gained</td>
                      <td style="padding:4px 0; font-weight:600;
                                 color:{'#00e676' if gained > 0 else '#ff5252' if gained < 0 else '#aaa'};
                                 text-align:right;">{gained_str}</td>
                    </tr>
                    <tr>
                      <td style="padding:4px 0; color:black;">Points</td>
                      <td style="padding:4px 0; font-weight:600;
                                 text-align:right;">{summary['Points']}</td>
                    </tr>
                    <tr>
                      <td style="padding:4px 0; color:black;">Status</td>
                      <td style="padding:4px 0; font-weight:600;
                                 text-align:right;">{summary['Status']}</td>
                    </tr>
                  </table>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── 6B. LAP TIME COMPARISON — rolling average only (FIXED) ─────────────────────
    section_header("Race Pace", "5-lap rolling average lap time — smoothed to show true pace")

    window = 5
    fig, ax = plt.subplots(figsize=(13, 5))

    for drv, drv_laps, color in [(d1, d1_laps, color1), (d2, d2_laps, color2)]:
        if len(drv_laps) < 2:
            continue

        # Ensure proper sorting + clean numeric arrays
        drv_laps = drv_laps.sort_values("LapNumber")
        x = drv_laps["LapNumber"].to_numpy()
        y = drv_laps["LapTime_s"].to_numpy()

        # Rolling average (centered smoothing)
        rolling = pd.Series(y).rolling(window, center=True, min_periods=1).mean().to_numpy()

        ax.plot(
            x, rolling,
            color=color, linewidth=2.5, label=drv, alpha=0.95
        )

        # Proper fill_between (fixes weird shading / flat look)
        ax.fill_between(
            x, rolling, np.nanmin(rolling),
            color=color, alpha=0.08
        )

    # Tight y-limits so lines aren't squashed at the top
    all_vals = []
    for drv_laps in [d1_laps, d2_laps]:
        if len(drv_laps) > 0:
            all_vals.extend(drv_laps["LapTime_s"].values)

    if all_vals:
        ymin, ymax = min(all_vals), max(all_vals)
        margin = (ymax - ymin) * 0.2
        ax.set_ylim(ymin - margin, ymax + margin)

    ax.set_xlabel("Lap number")
    ax.set_ylabel("Lap time (s)")
    ax.set_title(f"Race Pace — {d1} vs {d2} ({window}-lap rolling avg, clean laps only)")

    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    show_figure(fig)

    # ── 6C. CONSISTENCY COMPARISON ────────────────────────────────────────────
    section_header("Pace Consistency", "Spread of clean lap times — tighter box = more consistent")

    fig, ax = plt.subplots(figsize=(6, 5))
    data_to_plot = [
        d1_laps["LapTime_s"].dropna().values,
        d2_laps["LapTime_s"].dropna().values,
    ]
    bp = ax.boxplot(
        data_to_plot, labels=[d1, d2], patch_artist=True, widths=0.5,
        medianprops=dict(color="white", linewidth=2),
        whiskerprops=dict(color="#aaaaaa"),
        capprops=dict(color="#aaaaaa"),
    )
    bp["boxes"][0].set_facecolor(color1)
    bp["boxes"][0].set_alpha(0.7)
    bp["boxes"][1].set_facecolor(color2)
    bp["boxes"][1].set_alpha(0.7)

    for i, (data, drv) in enumerate(zip(data_to_plot, [d1, d2]), start=1):
        if len(data) == 0:
            continue
        med = np.median(data)
        ax.text(i, med + 0.05, f"Med: {med:.2f}s",
                ha="center", va="bottom", fontsize=8, color="white")

    ax.set_ylabel("Lap time (s)")
    ax.set_title("Pace Consistency Comparison")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    show_figure(fig)

    # ── 6D. TYRE STRATEGY COMPARISON ──────────────────────────────────────────
    section_header("Tyre Strategy", "When each driver pitted and which compounds they used")

    COMPOUND_COLORS = {
        "SOFT": "#e8002d", "MEDIUM": "#ffd700", "HARD": "#f0f0f0",
        "INTER": "#39b54a", "WET": "#0067ff", "UNKNOWN": "#888888",
    }

    strat_all = laps[["Driver", "Stint", "Compound", "LapNumber"]].dropna().copy()
    strat_all["Compound"] = strat_all["Compound"].str.upper().fillna("UNKNOWN")

    fig, ax = plt.subplots(figsize=(12, 2.5))
    for y_pos, (driver, color) in enumerate([(d1, color1), (d2, color2)]):
        d = strat_all[strat_all["Driver"] == driver]
        for stint_num in sorted(d["Stint"].unique()):
            stint_laps = d[d["Stint"] == stint_num]["LapNumber"]
            compound   = d[d["Stint"] == stint_num]["Compound"].iloc[0]
            bar_color  = COMPOUND_COLORS.get(compound, "#888888")
            start  = stint_laps.min()
            length = stint_laps.max() - start + 1
            ax.barh(y_pos, length, left=start, color=bar_color,
                    edgecolor="#333333", height=0.5, alpha=0.9)
            if length >= 4:
                ax.text(start + length/2, y_pos, compound[0],
                        ha="center", va="center", fontsize=8, fontweight="bold",
                        color="black" if compound in ["MEDIUM", "HARD"] else "white")

    ax.set_yticks([0, 1])
    ax.set_yticklabels([d1, d2])
    ax.set_xlabel("Lap number")
    ax.set_title("Tyre Strategy Comparison")
    ax.grid(axis="x", alpha=0.3)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=c, edgecolor="#333333", label=k)
        for k, c in COMPOUND_COLORS.items() if k != "UNKNOWN"
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=7)
    plt.tight_layout()
    show_figure(fig)

    # ── 6E. POSITION COMPARISON ───────────────────────────────────────────────
    section_header("Race Position Battle", "Head-to-head position over every lap")

    all_laps = laps[["Driver", "LapNumber", "Position"]].dropna(subset=["Position"]).copy()
    all_laps["Position"]  = all_laps["Position"].astype(int)
    all_laps["LapNumber"] = all_laps["LapNumber"].astype(int)

    d1_pos = all_laps[all_laps["Driver"] == d1].sort_values("LapNumber")
    d2_pos = all_laps[all_laps["Driver"] == d2].sort_values("LapNumber")

    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(d1_pos["LapNumber"], d1_pos["Position"],
            color=color1, linewidth=1.8, label=d1)
    ax.plot(d2_pos["LapNumber"], d2_pos["Position"],
            color=color2, linewidth=1.8, label=d2, linestyle="--")
    ax.invert_yaxis()
    ax.set_xlabel("Lap")
    ax.set_ylabel("Position")
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax.set_title(f"Position — {d1} vs {d2}")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    show_figure(fig)

    # ── 6F. SECTOR PACE CIRCUIT MAPS ──────────────────────────────────────────
    section_header(
        "Sector Pace — Circuit Map",
        "Average clean sector time per driver plotted on the track layout. "
        "Out-laps and pit laps removed."
    )

    try:
        ref_lap = laps.pick_fastest()
        ref_tel = ref_lap.get_telemetry().add_distance()
    except Exception as e:
        st.warning(f"Could not load telemetry for circuit map: {e}")
        return

    def avg_sector_times(drv):
        d = valid[valid["Driver"] == drv].copy()
        out_lap_nums = laps[
            laps["PitOutTime"].notna() & (laps["Driver"] == drv)
        ]["LapNumber"].values
        d = d[~d["LapNumber"].isin(out_lap_nums)]

        if d.empty:
            return None, None, None

        s1 = d["Sector1Time"].dt.total_seconds().mean()
        s2 = d["Sector2Time"].dt.total_seconds().mean()
        s3 = d["Sector3Time"].dt.total_seconds().mean()
        return s1, s2, s3

    s1_d1, s2_d1, s3_d1 = avg_sector_times(d1)
    s1_d2, s2_d2, s3_d2 = avg_sector_times(d2)

    if any(v is None for v in [s1_d1, s1_d2]):
        st.warning("Not enough clean lap data to build sector maps.")
        return

    try:
        s1_end_time = ref_lap["Sector1SessionTime"]
        s2_end_time = ref_lap["Sector2SessionTime"]
        s1_idx = (ref_tel["SessionTime"] - s1_end_time).abs().idxmin()
        s2_idx = (ref_tel["SessionTime"] - s2_end_time).abs().idxmin()
    except Exception:
        n = len(ref_tel)
        s1_idx = n // 3
        s2_idx = 2 * n // 3

    x_all = ref_tel["X"].values.astype(float)
    y_all = ref_tel["Y"].values.astype(float)

    sectors_xy = {
        "S1": (x_all[:s1_idx],       y_all[:s1_idx]),
        "S2": (x_all[s1_idx:s2_idx], y_all[s1_idx:s2_idx]),
        "S3": (x_all[s2_idx:],       y_all[s2_idx:]),
    }

    SECTOR_COLORS = {"S1": "#e8002d", "S2": "#ffd700", "S3": "#00d2be"}

    def _draw_race_sector_map(ax, driver_name, driver_color,
                               s1_t, s2_t, s3_t):
        sector_times = {"S1": s1_t, "S2": s2_t, "S3": s3_t}
        ax.plot(x_all, y_all, color="#2a2a2a", linewidth=14,
                solid_capstyle="round", solid_joinstyle="round", zorder=1)

        for sk, (sx, sy) in sectors_xy.items():
            if len(sx) > 1:
                ax.plot(sx, sy, color=SECTOR_COLORS[sk], linewidth=6,
                        solid_capstyle="round", solid_joinstyle="round", zorder=2)

        for bidx in [s1_idx, s2_idx]:
            if 0 < bidx < len(x_all):
                ax.scatter(x_all[bidx], y_all[bidx], color="white", s=60,
                           zorder=5, edgecolors="#0f0f0f", linewidths=1.2)

        ax.scatter(x_all[0], y_all[0], color=driver_color, s=120, marker="D",
                   zorder=6, edgecolors="white", linewidths=1.2)

        for sk, (sx, sy) in sectors_xy.items():
            if len(sx) < 2:
                continue
            mid  = len(sx) // 2
            lx, ly = sx[mid], sy[mid]
            t    = sector_times[sk]
            t_str = f"{int(t//60)}:{t%60:06.3f}" if t >= 60 else f"{t:.3f}s"

            ax.annotate(
                f"{sk}  avg {t_str}",
                xy=(lx, ly),
                fontsize=7.5, fontweight="bold", color="white",
                ha="center", va="center",
                bbox=dict(
                    boxstyle="round,pad=0.4",
                    facecolor=SECTOR_COLORS[sk],
                    edgecolor="white", linewidth=0.8, alpha=0.93,
                ),
                zorder=7,
            )

        ax.axis("equal")
        ax.axis("off")
        ax.set_title(driver_name, color="white", fontsize=11,
                     fontweight="bold", pad=6)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    _draw_race_sector_map(axes[0], d1, color1, s1_d1, s2_d1, s3_d1)
    _draw_race_sector_map(axes[1], d2, color2, s1_d2, s2_d2, s3_d2)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=SECTOR_COLORS["S1"], label="Sector 1"),
        Patch(facecolor=SECTOR_COLORS["S2"], label="Sector 2"),
        Patch(facecolor=SECTOR_COLORS["S3"], label="Sector 3"),
    ]
    fig.legend(
        handles=legend_elements, loc="lower center", ncol=3,
        fontsize=9, facecolor="#1a1a1a", edgecolor="#333333", labelcolor="white",
    )
    fig.suptitle(
        f"Average Sector Pace — Clean Race Laps Only\n"
        f"{session.event['EventName']} {session.event.year}",
        color="white", fontsize=12, fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0.06, 1, 1])
    show_figure(fig)

    sector_rows = []
    for sk, t1, t2 in [("S1", s1_d1, s1_d2), ("S2", s2_d1, s2_d2), ("S3", s3_d1, s3_d2)]:
        diff   = t1 - t2
        faster = d1 if diff < 0 else d2
        sector_rows.append({
            "Sector": sk,
            d1:       f"{t1:.3f}s",
            d2:       f"{t2:.3f}s",
            "Delta":  f"{abs(diff):.3f}s",
            "Faster": faster,
        })
    st.caption("Average clean-lap sector times — out-laps excluded")
    st.dataframe(pd.DataFrame(sector_rows), use_container_width=True, hide_index=True)
# ┌─────────────────────────────────────────────────────────────────────────────┐
# │  SECTION 7 — MAIN APP ROUTER                                                │
# │                                                                             │
# │  This is where everything is wired together.                                │
# │  Streamlit runs this file top-to-bottom every time the user interacts.      │
# └─────────────────────────────────────────────────────────────────────────────┘
def main():
    # ── App title ─────────────────────────────────────────────────────────────
    st.title("🏎️ F1 Analytics Dashboard")
    st.caption("Powered by FastF1 · Select a session in the sidebar to begin")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Session Settings")

        # Year
        year = st.selectbox("Year", YEAR_LIST)

        # Dynamic Grand Prix calendar
        with st.spinner("Loading calendar..."):
            schedule = get_race_schedule(year)

        # ── Filter out future races ────────────────────────────────────────────
        # today's date — races that haven't happened yet have no data in FastF1
        today = pd.Timestamp.now(tz="UTC").normalize()

        # Keep only races whose EventDate is in the past.
        # We add a 1-day buffer so a race happening TODAY is included
        # (it may have finished depending on timezone).
        schedule = schedule[
            pd.to_datetime(schedule["EventDate"], utc=True) <= today + pd.Timedelta(days=1)
        ].reset_index(drop=True)

        # Edge case: if NO races have happened yet for this year
        # (e.g. user picks a future year), show a friendly message and stop.
        if schedule.empty:
            st.warning(f"No races have taken place yet in {year}.")
            st.stop()   # st.stop() halts execution cleanly — no error shown

        schedule["Label"] = schedule.apply(
            lambda row: f"R{int(row['RoundNumber'])}  —  {row['EventName']}",
            axis=1,
        )
        label_to_name = dict(zip(schedule["Label"], schedule["EventName"]))
        selected_label = st.selectbox("Grand Prix", schedule["Label"].tolist())
        gp = label_to_name[selected_label]

        # Event info card
        event_row = schedule[schedule["EventName"] == gp].iloc[0]
        st.caption(
            f"📍 {event_row.get('Location', '')}  ·  {event_row.get('Country', '')}\n\n"
            f"📅 {pd.to_datetime(event_row['EventDate']).strftime('%d %b %Y')}"
        )

        # Session type
        session_type = st.selectbox("Session", ["Race", "Qualifying"])
        session_code = "R" if session_type == "Race" else "Q"

        st.markdown("---")

        # Mode
        mode = st.radio("Analysis Mode", ["Session Overview", "Head to Head"])

        # Driver selection — only for Head to Head
        driver_1 = driver_2 = None

        if mode == "Head to Head":
            st.markdown("---")
            st.subheader("Driver Selection")

            with st.spinner("Fetching drivers..."):
                available_drivers = get_available_drivers(year, gp, session_code)

            if not available_drivers:
                st.warning("Could not load driver list. Type abbreviations manually.")
                driver_1 = st.text_input("Driver 1 (e.g. VER)", value="VER").upper().strip()
                driver_2 = st.text_input("Driver 2 (e.g. HAM)", value="HAM").upper().strip()
            else:
                driver_1 = st.selectbox(
                    "Driver 1", available_drivers,
                    index=0,
                    key="driver1_select",
                )
                driver_2 = st.selectbox(
                    "Driver 2", available_drivers,
                    index=min(1, len(available_drivers) - 1),
                    key="driver2_select",
                )

            if driver_1 == driver_2:
                st.error("Please select two different drivers.")

        st.markdown("---")
        load_button = st.button(
            "Load Session", type="primary", use_container_width=True,
            disabled=(mode == "Head to Head" and driver_1 == driver_2),
        )

    # Show welcome screen until user clicks Load
    if not load_button:
        st.markdown("""
        ### Welcome!

        Use the **sidebar** on the left to:
        1. Select a year, Grand Prix, and session type
        2. Choose your analysis mode
        3. Click **Load Session**

        The app will download the data (first load takes ~30s, then it's cached)
        and display all charts automatically.
        """)
        return

    # Load the session
    with st.spinner(f"Loading {gp} {year} — {session_type}..."):
        session = load_session(year, gp, session_code)

    if session is None:
        return

    fastf1.plotting.setup_mpl(mpl_timedelta_support=False, color_scheme="fastf1")

    st.success(f"Loaded: {session.event['EventName']} {year} — {session_type}")

    if mode == "Session Overview":
        if session_code == "Q":
            show_qualifying_overview(session)
        else:
            show_race_overview(session)

    elif mode == "Head to Head":
        available = session.laps["Driver"].unique().tolist()

        if driver_1 not in available:
            st.error(f"'{driver_1}' not found. Available: {', '.join(sorted(available))}")
            return
        if driver_2 not in available:
            st.error(f"'{driver_2}' not found. Available: {', '.join(sorted(available))}")
            return
        if driver_1 == driver_2:
            st.error("Please select two different drivers.")
            return

        if session_code == "Q":
            show_h2h_qualifying(session, driver_1, driver_2)
        else:
            show_h2h_race(session, driver_1, driver_2)

# ── Entry point ───────────────────────────────────────────────────────────────
# Python runs this block when you execute: streamlit run f1_dashboard.py
if __name__ == "__main__":
    main()
