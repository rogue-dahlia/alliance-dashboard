"""Alliance performance dashboard.

Reads a workbook with two raw-dump sheets (one with a `VS` column, one with a
`Power` column — both keyed by `player_name`), joins them, computes a
power-weighted geometric-mean composite, and renders sortable tables + a
scatter for the alliance.

Run locally:  streamlit run streamlit_app.py
Deploy:       push to a GitHub repo, point share.streamlit.io at it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Alliance Dashboard", layout="wide")
st.title("Alliance Stats")
st.caption(
    "VS = weekly damage. Power = total power. Composite = "
    "(power_pct ** wp) × (vs_pct ** wv) × 10000, where the two weights sum to 1. "
    "Each tab below is a different way of slicing the same data."
)


# ---------------------------------------------------------------------------
# Data load
# ---------------------------------------------------------------------------


def _find_sheets(xls: pd.ExcelFile) -> tuple[pd.DataFrame | None, pd.DataFrame | None, list[str], list[str]]:
    """Pick the most recent sheet containing a VS column and a Power column.

    A sheet contributes to a metric if it has `player_name` + that metric's
    column. A single combined sheet with all three columns will populate both
    the VS and Power tables. "Most recent" = last in workbook order.
    Returns (vs_df, power_df, vs_sheet_names_seen, power_sheet_names_seen).
    """
    vs_df = power_df = None
    vs_names: list[str] = []
    power_names: list[str] = []
    for name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=name)
        cols = set(df.columns)
        if "player_name" not in cols:
            continue
        if "VS" in cols:
            vs_df = df[["player_name", "VS"]].dropna(subset=["player_name", "VS"])
            vs_names.append(name)
        if "Power" in cols:
            power_df = df[["player_name", "Power"]].dropna(subset=["player_name", "Power"])
            power_names.append(name)
    return vs_df, power_df, vs_names, power_names


@st.cache_data(show_spinner=False)
def _load_from_bytes(data: bytes) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    xls = pd.ExcelFile(data)
    vs_df, power_df, vs_names, power_names = _find_sheets(xls)
    return vs_df, power_df, vs_names, power_names


@st.cache_data(show_spinner=False)
def _load_from_path(path: str, mtime: float) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    del mtime  # cache key only
    xls = pd.ExcelFile(path)
    return _find_sheets(xls)


# Data source: prefer file uploader, fall back to a committed data.xlsx.
default_path = Path(__file__).parent / "data.xlsx"
uploaded = st.sidebar.file_uploader("Upload alliance workbook (.xlsx)", type=["xlsx"])
if uploaded is not None:
    vs_df, power_df, vs_names, power_names = _load_from_bytes(uploaded.getvalue())
    source = f"uploaded: {uploaded.name}"
elif default_path.exists():
    vs_df, power_df, vs_names, power_names = _load_from_path(
        str(default_path), default_path.stat().st_mtime
    )
    source = f"repo: {default_path.name}"
else:
    st.info(
        "Upload an .xlsx with the data — either one sheet with columns "
        "`player_name`, `VS`, `Power`, or two sheets (one with `player_name` + "
        "`VS`, another with `player_name` + `Power`). Or commit a `data.xlsx` "
        "next to this script."
    )
    st.stop()

if vs_df is None or power_df is None:
    st.error(
        "Couldn't find both metrics. Need either one sheet with columns "
        "(`player_name`, `VS`, `Power`), or two sheets — one with "
        "(`player_name`, `VS`) and one with (`player_name`, `Power`)."
    )
    st.stop()

st.sidebar.caption(f"Source: {source}")
if len(vs_names) > 1:
    st.sidebar.warning(f"Multiple VS sheets found, using '{vs_names[-1]}'.")
if len(power_names) > 1:
    st.sidebar.warning(f"Multiple Power sheets found, using '{power_names[-1]}'.")


# ---------------------------------------------------------------------------
# Join + compute
# ---------------------------------------------------------------------------

vs_names_set = set(vs_df["player_name"])
power_names_set = set(power_df["player_name"])
only_vs = sorted(vs_names_set - power_names_set)
only_power = sorted(power_names_set - vs_names_set)

df = vs_df.merge(power_df, on="player_name", how="inner").copy()

power_weight_pct = st.sidebar.slider(
    "Power weight (%)",
    min_value=0,
    max_value=100,
    value=67,
    step=1,
    help=(
        "How much the composite weights power vs VS. 67 = power matters twice "
        "as much as VS (the 2:1 weighting). 50 = equal. 75 = 3:1 power."
    ),
)
wp = power_weight_pct / 100.0
wv = 1.0 - wp

df["vs_pct"] = df["VS"].rank(pct=True)
df["power_pct"] = df["Power"].rank(pct=True)
df["composite"] = (df["power_pct"] ** wp) * (df["vs_pct"] ** wv) * 10000
df["composite_rank"] = df["composite"].rank(method="min", ascending=False).astype(int)
df["vs_rank"] = df["VS"].rank(method="min", ascending=False).astype(int)
df["power_rank"] = df["Power"].rank(method="min", ascending=False).astype(int)
df["balance"] = df["power_pct"] - df["vs_pct"]
df = df.sort_values("composite", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Header metrics
# ---------------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Players matched", len(df))
c2.metric("Only in VS", len(only_vs))
c3.metric("Only in Power", len(only_power))
c4.metric("Power weight", f"{power_weight_pct}% / {100 - power_weight_pct}%")

if only_vs or only_power:
    with st.expander(
        f"⚠ Unmatched players ({len(only_vs) + len(only_power)}) — likely OCR dupes "
        "or missing from one of the captures"
    ):
        l, r = st.columns(2)
        with l:
            st.markdown(f"**Only in VS ({len(only_vs)}):**")
            st.write(only_vs or "—")
        with r:
            st.markdown(f"**Only in Power ({len(only_power)}):**")
            st.write(only_power or "—")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def _fmt(df_: pd.DataFrame) -> pd.io.formats.style.Styler:
    return df_.style.format(
        {
            "VS": "{:,.0f}",
            "Power": "{:,.0f}",
            "vs_pct": "{:.0%}",
            "power_pct": "{:.0%}",
            "composite": "{:,.0f}",
            "balance": "{:+.0%}",
        }
    )


composite_cols = ["composite_rank", "player_name", "VS", "Power", "vs_pct", "power_pct", "composite"]
vs_cols = ["vs_rank", "player_name", "VS", "vs_pct"]
power_cols = ["power_rank", "player_name", "Power", "power_pct"]
balance_cols = ["player_name", "VS", "Power", "vs_pct", "power_pct", "balance"]


tab_comp, tab_vs, tab_power, tab_balance, tab_scatter = st.tabs(
    ["Composite", "By VS", "By Power", "Balance", "Scatter"]
)

with tab_comp:
    st.markdown("Sorted by composite, descending.")
    st.dataframe(
        _fmt(df[composite_cols]), hide_index=True, use_container_width=True, height=600
    )

with tab_vs:
    st.markdown("Sorted by VS score, descending.")
    st.dataframe(
        _fmt(df.sort_values("VS", ascending=False)[vs_cols]),
        hide_index=True,
        use_container_width=True,
        height=600,
    )

with tab_power:
    st.markdown("Sorted by total power, descending.")
    st.dataframe(
        _fmt(df.sort_values("Power", ascending=False)[power_cols]),
        hide_index=True,
        use_container_width=True,
        height=600,
    )

with tab_balance:
    st.markdown(
        "`balance = power_pct − vs_pct`. Positive = power percentile is higher "
        "than VS percentile. Negative = VS percentile is higher than power "
        "percentile. Sorted by absolute imbalance, largest first."
    )
    st.dataframe(
        _fmt(df.reindex(df["balance"].abs().sort_values(ascending=False).index)[balance_cols]),
        hide_index=True,
        use_container_width=True,
        height=600,
    )

with tab_scatter:
    st.markdown("VS vs Power. Hover for player; colour = composite percentile.")
    fig = px.scatter(
        df,
        x="Power",
        y="VS",
        hover_name="player_name",
        color="composite",
        color_continuous_scale="Viridis",
    )
    fig.update_traces(marker=dict(size=10))
    fig.update_layout(coloraxis_colorbar_title="Composite", height=560)
    st.plotly_chart(fig, use_container_width=True)
