"""Streamlit interface for selecting continuous screenplay promos."""

import hashlib
import os
from pathlib import Path

import streamlit as st

from run import load_project_env
from src.parser import parse_text
from src.ranker import build_promo, enhance, posting_list, timestamp
from src.windows import generate_windows, shortlist_windows


TITLE = "🎬 Kuku Promo Finder — AI Microdrama Ad Identifier"
PACK = Path(__file__).resolve().parent / "I Married a Broken Soldier. He was a Duke"

st.set_page_config(page_title="Kuku Promo Finder", page_icon="🎬", layout="wide")
st.title(TITLE)
episodes = sorted(PACK.glob("episode-*.txt"))
if not episodes:
    episodes = sorted((Path(__file__).resolve().parent / "demo").glob("*.txt"))
if len(episodes) > 1:
    selected = st.selectbox("Episode", episodes,
                            format_func=lambda p: ("Original demo · Station inspector" if p.parent.name == "demo"
                                                   else f"Episode {int(p.name.split('-')[1])}"))
else:
    selected = next(iter(episodes), None)
uploaded = st.file_uploader("Upload a screenplay", type=["txt"])
mode = st.radio("Scoring mode", ["HEURISTIC_OFFLINE", "LLM_ENHANCED"], horizontal=True)
if uploaded:
    data, name = uploaded.getvalue(), uploaded.name
elif selected:
    data, name = selected.read_bytes(), selected.name
else:
    st.info("Upload a timestamped screenplay (.txt) to find promos.")
    st.stop()

episode = parse_text(data.decode("utf-8-sig", errors="replace"), name)
if episode["warnings"]:
    with st.expander(f"Parser notes ({len(episode['warnings'])})"):
        st.text("\n".join(episode["warnings"][:20]))
if not episode["events"]:
    st.warning("No timed events found. Include scene numbers and event start and end times.")
    st.stop()

st.subheader(f"Episode {episode['episode_number'] or '—'}")
st.write(episode["logline"])
windows = generate_windows(episode["events"])
candidates = shortlist_windows(windows)
metrics = (("Episode Duration", timestamp(episode["duration_sec"])),
           ("Total Windows Evaluated", len(windows)),
           ("Filtered", sum(w["composite_score"] == 0 for w in windows)),
           ("Shortlisted", len(candidates)))
for column, (label, value) in zip(st.columns(4), metrics):
    column.metric(label, value)
if not candidates:
    st.info("No eligible promo passed the tension filter.")
    st.stop()

pairs = [build_promo(episode, candidate) for candidate in candidates]
promos = [promo for promo, _ in pairs]
offline_scores = {(p["segment_start"], p["segment_end"]): p["composite_score"] for p in promos}
if mode == "LLM_ENHANCED":
    load_project_env()
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    identity = (hashlib.sha256(data).hexdigest(), os.getenv("GEMINI_MODEL"))
    if key and st.button("Score shortlisted clips with Gemini", type="primary"):
        with st.spinner(f"Scoring {len(pairs)} shortlisted clips…"):
            enhanced = []
            issue = None
            for promo, events in pairs:
                try:
                    enhanced.append(enhance(promo, events, key))
                except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
                    issue = f"Gemini scoring stopped ({type(error).__name__}). Remaining clips use offline scores."
                    break
            st.session_state.gemini_run = (identity, enhanced + promos[len(enhanced):], issue)
    saved = st.session_state.get("gemini_run")
    if saved and saved[0] == identity:
        promos = saved[1]
        if saved[2]:
            st.warning(saved[2])
    elif key:
        st.info("Showing offline scores until you run Gemini.")
    else:
        st.warning("Gemini key unavailable. Showing offline scores.")

st.subheader("Top promos")
for promo in posting_list(promos, limit=3):
    with st.container(border=True):
        heading, score = st.columns([4, 1])
        heading.subheader(f"{promo['segment_start']} – {promo['segment_end']}")
        heading.caption(f"{promo['duration_sec']:.2f} seconds · {promo['mode']}")
        reviewed = promo["mode"] == "LLM_ENHANCED"
        baseline = offline_scores[promo["segment_start"], promo["segment_end"]]
        score.badge(f"Offline Score {baseline:g}/10", color="gray")
        if reviewed:
            score.badge(f"Gemini Score {promo['composite_score']:g}/10", color="green")
        for label, field in [("⚡ 3-Second Hook", "hook"), ("⏳ Cliffhanger Cut", "cliffhanger"),
                             ("💡 Why It Works", "why_it_works"), ("🏆 Ranking Reason", "ranking_reason")]:
            st.markdown(f"**{label}**")
            st.text(promo[field])
