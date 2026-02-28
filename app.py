import math
import pandas as pd
import numpy as np
import streamlit as st
import folium
import os
import base64
import mimetypes
from streamlit_folium import st_folium

st.set_page_config(page_title="Urban Memory Layer", layout="wide")

# -----------------------------
# Styling (mobile/editorial vibe)
# -----------------------------
st.markdown("""
<style>
body { background-color: #f4f1ed; }
.container { max-width: 980px; margin: 0 auto; }
.header-title { font-size: 34px; font-weight: 800; margin: 6px 0 0 0; }
.header-sub { color:#666; margin: 6px 0 18px 0; font-size: 15px; }
.card {
    background: white;
    padding: 26px;
    border-radius: 18px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}
.route-title { font-size: 26px; font-weight: 750; margin: 2px 0 4px 0; }
.route-desc { color:#555; font-size: 16px; margin: 0 0 12px 0; }
.stop-title { font-size: 23px; font-weight: 750; margin: 6px 0 10px 0; }
.meta { font-size: 13px; color:#666; margin: 6px 0 12px 0; }
.badge {
    display:inline-block; padding: 6px 10px; border-radius: 999px;
    background:#f2f2f2; font-size: 12px; margin-right: 8px;
}
.callout {
    background:#faf7f2; border: 1px solid #eee2d4;
    padding: 12px 14px; border-radius: 14px; margin-top: 14px;
    font-size: 15px; line-height: 1.55;
}
.small { font-size: 13px; color:#666; }
hr { border: none; border-top: 1px solid #e9e4dc; margin: 18px 0; }
.pill {
    display:inline-block;
    padding: 8px 12px;
    border-radius: 999px;
    background: #f2f2f2;
    font-size: 13px;
    margin-right: 8px;
    margin-top: 8px;
    border: 1px solid #e6e6e6;
}
.diagram {
    background: white;
    padding: 18px 18px;
    border-radius: 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    font-size: 14px;
    line-height: 1.6;
}
.diagram .row { display:flex; flex-wrap:wrap; gap:10px; margin-top: 10px; }
.diagram .box {
    padding: 10px 12px;
    border-radius: 14px;
    border: 1px solid #eee2d4;
    background: #faf7f2;
    font-weight: 600;
}

.audio-card {
    position: relative;
    border-radius: 18px;
    overflow: hidden;
    margin-bottom: 12px;
}

.audio-card img {
    width: 100%;
    filter: brightness(0.65) contrast(1.05);
}

.audio-overlay {
    position: absolute;
    bottom: 14px;
    left: 18px;
    color: white;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.3px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Helpers / Constants
# -----------------------------
MODE_TO_COL = {
    "Explorer": "summary_explorer",
    "Deep Dive": "summary_deepdive",
    "Behind the Scenes": "summary_bts",
}

REQUIRED = [
    "id","title","year_start","year_end","latitude","longitude","theme","layer_type",
    "route_id","route_name","route_description","route_duration_min","route_cover_image_url","route_order",
    "summary_explorer","summary_deepdive","summary_bts",
    "what_to_notice","did_you_know","source_url"
]

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Distance between two lat/lon points in meters."""
    R = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def fmt_years(y1, y2):
    y1 = int(y1)
    y2 = int(y2)
    return f"{y1}" if y1 == y2 else f"{y1}–{y2}"

def fmt_distance(meters: float) -> str:
    if meters < 1000:
        return f"~{int(round(meters/10)*10)} m"
    return f"~{meters/1000:.1f} km"

@st.cache_data
def load_data():
    df = pd.read_csv("data/city_dataset.csv")

    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")

    for c in ["year_start","year_end","latitude","longitude","route_order","route_duration_min"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["theme"] = df["theme"].astype(str).str.strip().str.lower()
    df["layer_type"] = df["layer_type"].astype(str).str.strip().str.lower()
    df["route_id"] = df["route_id"].astype(str).str.strip()
    df["route_name"] = df["route_name"].astype(str).str.strip()

    df = df.dropna(subset=["latitude","longitude","route_order","year_start","year_end"])
    return df

def img_to_data_uri(path: str) -> str | None:
    """Convert local image file to data URI for HTML rendering. Returns None if not found."""
    if not path:
        return None
    path = path.strip()

    # If it's already a URL, return as-is (browser can load it)
    if path.startswith("http://") or path.startswith("https://"):
        return path

    # Local file path
    if not os.path.exists(path):
        return None

    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/jpeg"

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime};base64,{b64}"

def neighbor_density(points_df: pd.DataFrame, radius_m: float = 250.0) -> list[int]:
    """
    For each point, count how many points are within radius_m (including itself).
    Returns a list of counts aligned to points_df order.
    """
    coords = points_df[["latitude", "longitude"]].astype(float).values.tolist()
    counts = []
    for (lat1, lon1) in coords:
        c = 0
        for (lat2, lon2) in coords:
            if haversine_m(lat1, lon1, lat2, lon2) <= radius_m:
                c += 1
        counts.append(c)
    return counts

# -----------------------------
# Load Data
# -----------------------------
df = load_data()

routes = (
    df[["route_id","route_name","route_description","route_duration_min","route_cover_image_url"]]
    .drop_duplicates()
    .sort_values("route_name")
)

# -----------------------------
# Header
# -----------------------------
st.markdown("<div class='container'>", unsafe_allow_html=True)
st.markdown("<div class='header-title'>Urban Memory Layer</div>", unsafe_allow_html=True)
st.markdown("<div class='header-sub'>A prototype spatial narrative engine for adaptive, multi-layered urban storytelling.</div>", unsafe_allow_html=True)

# -----------------------------
# Controls
# -----------------------------
c1, c2, c3 = st.columns([1.25, 1, 1])
with c1:
    route_name = st.selectbox("Choose a route", routes["route_name"].tolist())
with c2:
    narrative_mode = st.selectbox("Narrative depth", list(MODE_TO_COL.keys()), index=0)
with c3:
    show_stop_list = st.toggle("Show stop list", value=False)

route_row = routes[routes["route_name"] == route_name].iloc[0]
route_id = route_row["route_id"]

route_df = (
    df[df["route_id"] == route_id]
    .sort_values("route_order")
    .reset_index(drop=True)
)

# -----------------------------
# Session state
# -----------------------------
if "active_route_id" not in st.session_state:
    st.session_state.active_route_id = route_id
if "story_index" not in st.session_state:
    st.session_state.story_index = 0
if "started" not in st.session_state:
    st.session_state.started = False

# remember the chosen "lens" (layer filter)
if "lens_layer" not in st.session_state:
    st.session_state.lens_layer = "All"

# Reset when route changes
if st.session_state.active_route_id != route_id:
    st.session_state.active_route_id = route_id
    st.session_state.story_index = 0
    st.session_state.started = False

def start_route():
    st.session_state.started = True
    st.session_state.story_index = 0

def restart_route():
    st.session_state.story_index = 0

def next_stop():
    st.session_state.story_index = min(st.session_state.story_index + 1, len(route_df) - 1)

def prev_stop():
    st.session_state.story_index = max(st.session_state.story_index - 1, 0)

def go_to_route_picker():
    st.session_state.started = False

def set_lens(layer: str):
    st.session_state.lens_layer = layer
    st.session_state.started = False
    st.session_state.story_index = 0

# -----------------------------
# Start Route screen (onboarding)
# -----------------------------
if not st.session_state.started:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='route-title'>{route_name}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='route-desc'>{route_row['route_description']}</div>", unsafe_allow_html=True)

    # Lens status (SAFE here: computed from route_df only)
    total_stops = len(route_df)
    active_lens_label = st.session_state.lens_layer
    if active_lens_label == "All":
        lens_stops = total_stops
        st.caption(f"Active lens: **All layers** • Stops visible: **{lens_stops}/{total_stops}**")
    else:
        lens_stops = int((route_df["layer_type"].astype(str).str.lower() == active_lens_label.lower()).sum())
        st.caption(f"Active lens: **{active_lens_label.title()}** • Stops visible: **{lens_stops}/{total_stops}**")

    cover = str(route_row.get("route_cover_image_url", "")).strip()
    if cover:
        try:
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.image(cover, width=700)

            ROUTE_CAPTIONS = {
                "R1": "Where water became wealth.",
                "R2": "Where the street became a voice.",
                "R3": "Where the city remembers itself."
            }

            st.markdown(
                f"<div class='small' style='margin-top:8px; font-style:italic;'>"
                f"{ROUTE_CAPTIONS.get(route_id, '')}"
                f"</div>",
                unsafe_allow_html=True
            )

        except Exception:
            st.caption("Cover image could not be loaded (check the file path).")

    approx_stops = len(route_df)
    duration = int(route_row["route_duration_min"]) if not np.isnan(route_row["route_duration_min"]) else None
    duration_txt = f"{duration} min" if duration else "—"
    st.markdown(
        f"<div class='meta'>Stops: <b>{approx_stops}</b> • Approx duration: <b>{duration_txt}</b> • Depth: <b>{narrative_mode}</b></div>",
        unsafe_allow_html=True
    )

    # Lens selector
    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown("**Choose a lens (optional):**")
    lens_cols = st.columns(4)
    with lens_cols[0]:
        st.button("All", on_click=set_lens, args=("All",), use_container_width=True)
    with lens_cols[1]:
        st.button("Economic", on_click=set_lens, args=("economic",), use_container_width=True)
    with lens_cols[2]:
        st.button("Social", on_click=set_lens, args=("social",), use_container_width=True)
    with lens_cols[3]:
        st.button("Political", on_click=set_lens, args=("political",), use_container_width=True)

    st.caption(f"Active lens: **{st.session_state.lens_layer}**")

    if show_stop_list:
        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown("**Stops**")
        for _, r in route_df.iterrows():
            st.write(f"• **{int(r.route_order)}. {r.title}**  _({fmt_years(r.year_start, r.year_end)})_")

    st.markdown("<hr/>", unsafe_allow_html=True)
    st.button("Start Route →", on_click=start_route, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Map preview centered on first stop
    first = route_df.iloc[0]
    m = folium.Map(location=[float(first.latitude), float(first.longitude)], zoom_start=13, tiles="CartoDB positron")
    pts = route_df[["latitude","longitude"]].astype(float).values.tolist()
    if len(pts) >= 2:
        folium.PolyLine(pts, weight=5, opacity=0.65).add_to(m)
    st_folium(m, use_container_width=True, height=420)

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# -----------------------------
# Story screen
# -----------------------------
lens = st.session_state.lens_layer
lens_df = route_df.copy()
if isinstance(lens, str) and lens != "All":
    lens_df = lens_df[lens_df["layer_type"].astype(str).str.lower() == lens.lower()].reset_index(drop=True)
    if len(lens_df) == 0:
        st.warning(f"No stops match the lens '{lens}'. Showing full route instead.")
        lens_df = route_df.copy()

# clamp index in case lens reduces list
st.session_state.story_index = min(int(st.session_state.story_index), max(len(lens_df) - 1, 0))

idx = int(st.session_state.story_index)
current = lens_df.iloc[idx]
summary_col = MODE_TO_COL[narrative_mode]

years = fmt_years(current.year_start, current.year_end)

# distance to next stop (within lens list)
distance_txt = None
if idx < len(lens_df) - 1:
    nxt = lens_df.iloc[idx + 1]
    meters = haversine_m(float(current.latitude), float(current.longitude), float(nxt.latitude), float(nxt.longitude))
    distance_txt = fmt_distance(meters)

badges = (
    f"<span class='badge'>{str(current.theme).title()}</span>"
    f"<span class='badge'>{str(current.layer_type).title()}</span>"
)

st.markdown("<div class='card'>", unsafe_allow_html=True)
st.markdown(f"<div class='route-title'>{route_name}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='route-desc'>{route_row['route_description']}</div>", unsafe_allow_html=True)

# Lens status (Story screen – the important one)
total_stops = len(route_df)
lens_stops = len(lens_df)
active_lens_label = st.session_state.lens_layer
if active_lens_label == "All":
    st.caption(f"Active lens: **All layers** • Stops visible: **{lens_stops}/{total_stops}**")
else:
    st.caption(f"Active lens: **{active_lens_label.title()}** • Stops visible: **{lens_stops}/{total_stops}**")

meta_bits = [
    f"Stop <b>{idx+1}</b> of <b>{len(lens_df)}</b>",
    f"Year: <b>{years}</b>",
]
if distance_txt:
    meta_bits.append(f"Next: <b>{distance_txt}</b>")

st.markdown(f"<div class='meta'>{' • '.join(meta_bits)}</div>", unsafe_allow_html=True)
st.progress((idx + 1) / max(len(lens_df), 1))

if show_stop_list:
    with st.expander("Stops in this route", expanded=False):
        for i, r in lens_df.iterrows():
            marker = "➡️" if i == idx else "•"
            st.write(f"{marker} **{int(r.route_order)}. {r.title}**  _({fmt_years(r.year_start, r.year_end)})_")

# NOTE: Removed redundant stop image block here.
# Images are shown only inside the audio card (for the 3 audio stops).

st.markdown(f"<div>{badges}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='stop-title'>{current.title}</div>", unsafe_allow_html=True)

st.markdown(
    f"<div style='font-size:18px; line-height:1.65;'>{str(current.get(summary_col,'')).strip()}</div>",
    unsafe_allow_html=True
)

# Callouts
what_to_notice = str(current.get("what_to_notice", "")).strip()
did_you_know = str(current.get("did_you_know", "")).strip()

if what_to_notice:
    st.markdown(f"<div class='callout'><b>What to notice:</b><br/>{what_to_notice}</div>", unsafe_allow_html=True)

if did_you_know:
    st.markdown(f"<div class='callout'><b>Did you know?</b><br/>{did_you_know}</div>", unsafe_allow_html=True)

# Explore this place through (layer branching signal)
st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown("### Explore this place through")
layer_choices = ["All", "economic", "social", "political", "spatial", "institutional"]
layer_cols = st.columns(3)
for i, layer in enumerate(layer_choices):
    with layer_cols[i % 3]:
        label = "All layers" if layer == "All" else f"{layer.title()} layer"
        st.button(label, on_click=set_lens, args=(layer,), use_container_width=True)

st.markdown("<hr/>", unsafe_allow_html=True)

# Navigation
nav1, nav2, nav3, nav4 = st.columns([1, 1, 1, 1])
with nav1:
    st.button("← Previous", on_click=prev_stop, disabled=(idx == 0), use_container_width=True)
with nav2:
    st.button("Restart", on_click=restart_route, use_container_width=True)
with nav3:
    st.button("Next →", on_click=next_stop, disabled=(idx >= len(lens_df)-1), use_container_width=True)
with nav4:
    st.button("Change route", on_click=go_to_route_picker, use_container_width=True)

# Source + Listen
link1, link2 = st.columns([1, 1])
with link1:
    st.link_button("Open source reference", str(current.source_url), use_container_width=True)

with link2:
    audio_url = str(current.get("audio_url", "")).strip()
    img = str(current.get("image_url", "")).strip()

    if audio_url:
        st.markdown("**Listen (audio)**")

        # Show image card (optional)
        if img:
            img_src = img_to_data_uri(img)
            if img_src:
                st.markdown(
                    f"""
                    <div class="audio-card">
                        <img src="{img_src}">
                        <div class="audio-overlay">Now Listening</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.caption("Image currently not available.")
        else:
            st.caption("Image currently not available.")

        # Play audio
        try:
            if audio_url.startswith("http://") or audio_url.startswith("https://"):
                st.audio(audio_url)
            else:
                with open(audio_url, "rb") as f:
                    audio_bytes = f.read()
                st.audio(audio_bytes, format="audio/mp3")
        except Exception:
            st.caption("Audio currently not available.")
    else:
        st.button("Listen (audio) — coming soon", disabled=True, use_container_width=True)

# Contributor (optional)
cn = str(current.get("contributor_name", "")).strip()
ct = str(current.get("contributor_type", "")).strip()
if cn:
    st.markdown(f"<div class='small'>Contributor: {cn}{(' ('+ct+')') if ct else ''}</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr/>", unsafe_allow_html=True)

# -----------------------------
# Map (support layer)
# -----------------------------
m = folium.Map(location=[float(current.latitude), float(current.longitude)], zoom_start=14, tiles="CartoDB positron")

# Density layer (circles behind markers)
densities = neighbor_density(route_df, radius_m=250.0)
min_d, max_d = min(densities), max(densities)

for d, row in zip(densities, route_df.itertuples(index=False)):
    if max_d == min_d:
        radius = 110
    else:
        radius = 70 + (d - min_d) * (180 - 70) / (max_d - min_d)

    folium.Circle(
        location=[float(row.latitude), float(row.longitude)],
        radius=float(radius),
        color="#111",
        weight=1,
        fill=True,
        fill_opacity=0.12,
        tooltip=f"Local density: {d} stops nearby"
    ).add_to(m)

# Route path (always show full route path)
pts = route_df[["latitude","longitude"]].astype(float).values.tolist()
if len(pts) >= 2:
    folium.PolyLine(pts, weight=5, opacity=0.65).add_to(m)

# Numbered markers (show full route markers; highlight current stop if id matches)
current_id = current["id"]
for _, row in route_df.iterrows():
    is_current = (row["id"] == current_id)
    label = str(int(row.route_order))
    icon = folium.DivIcon(html=f"""
    <div style="
        width: 26px; height: 26px; border-radius: 999px;
        display:flex; align-items:center; justify-content:center;
        font-weight:800; font-size:12px;
        background:{'#111' if is_current else '#fff'};
        color:{'#fff' if is_current else '#111'};
        border: 2px solid #111;
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
    ">{label}</div>
    """)
    folium.Marker(
        location=[float(row.latitude), float(row.longitude)],
        tooltip=f"{int(row.route_order)}. {row.title}",
        icon=icon
    ).add_to(m)

st_folium(m, use_container_width=True, height=520)
st.caption("Density circles indicate areas with higher concentration of route activity (within ~250m).")

st.markdown("<div class='small'>Story leads. Map supports. Routes turn history into a walkable experience.</div>", unsafe_allow_html=True)

# -----------------------------
# Conceptual Architecture Diagram (next-gen signal)
# -----------------------------
st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown("## Narrative Infrastructure Model")

st.markdown("""
<div class="diagram">
<b>Urban Memory Layer Architecture</b><br/>
A speculative next-gen layer for open-air museum storytelling platforms.<br/><br/>

<div class="row">
  <div class="box">Cultural Node (place)</div>
  <div class="box">Theme + Layer Type</div>
  <div class="box">Adaptive Narrative Depth</div>
  <div class="box">Route Sequencing</div>
  <div class="box">Spatial Walking Context</div>
</div>

<br/>
<b>Key idea:</b> the same place can be reused across routes and reinterpreted through different layers (economic, social, political, spatial, institutional),
without rewriting the story from scratch.
</div>
""", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)