"""Build editor-facing promos and a globally ranked posting list."""

import re

from .windows import INTERRUPTION, KINETIC


def timestamp(seconds):
    minutes, ticks = divmod(round(seconds * 100), 6000)
    return f"{minutes:02}:{ticks // 100:02}.{ticks % 100:02}"


def edge_description(text, events):
    if not text:
        return "No timed beat in this interval"
    event = next(e for e in events if e["text"] == text)
    if event["speaker"]:
        return f"{event['speaker'].title()}: {text}"
    return text


def offline_reason(window, events):
    opening = next((e for e in events if e["text"] == window["hook"]), None)
    closing = window["cliffhanger"].strip()
    subject = "the opening image"
    if opening and opening["speaker"]:
        tone = ", ".join(opening["emotions"]).lower()
        subject = f"{opening['speaker'].title()}’s {tone + ' ' if tone else ''}line"
    elif opening and KINETIC.search(opening["text"]):
        subject = f"the opening movement ({KINETIC.search(opening['text'])[0].lower()})"
    if not closing:
        return f"The clip opens on {subject}, but its final three seconds contain no timed beat."
    if closing.endswith('?"'):
        ending = f"the question {closing}"
    elif INTERRUPTION.search(closing):
        ending = f"the unfinished reaction {closing}"
    else:
        ending = closing.removesuffix(".")
    return f"The clip opens on {subject} and cuts on {ending}."


def build_promo(episode, window):
    start, end = window["start_time"], window["end_time"]
    events = [e for e in episode["events"] if e["scene_id"] == window["scene_id"]
              and e["end_time"] > start and e["start_time"] < end]
    # A named exchange and an explicit conflict cue are proxies for cold-viewer clarity.
    speakers = {e["speaker"] for e in events if e["speaker"]}
    conflict = any(re.search(r"\b(?:arrest|betray\w*|kill|marry|refuse|accus\w*|threat\w*)\b",
                             e["text"], re.I) for e in events)
    promo = {
        "episode": episode["episode_number"], "segment_start": timestamp(start),
        "segment_end": timestamp(end), "duration_sec": window["duration_sec"],
        "hook": edge_description(window["hook"], events),
        "cliffhanger": edge_description(window["cliffhanger"], events),
        "why_it_works": offline_reason(window, events),
        "composite_score": window["composite_score"], "mode": window["mode"],
        "independence_score": int(len(speakers) >= 2) + int(conflict),
    }
    return promo, events


def posting_list(promos, limit=20):
    selected = []
    represented = set()
    pool = list(promos)
    def fingerprint(p):
        return tuple(set(re.findall(r"\w+", p[k].lower())) for k in ("hook", "cliffhanger"))

    fingerprints = {id(p): fingerprint(p) for p in pool}
    while pool and len(selected) < limit:
        def priority(p):
            return (-p["composite_score"], len(selected) < 10 and p["episode"] in represented,
                    not 25 <= p["duration_sec"] <= 45, -p["independence_score"],
                    p["episode"], p["segment_start"], p["segment_end"])
        best = min(pool, key=priority)
        fresh = best["episode"] not in represented
        preferred = 25 <= best["duration_sec"] <= 45
        reason = (f"{best['composite_score']:g}/10 composite; "
                  f"{'inside' if preferred else 'outside'} the preferred duration; "
                  f"{best['independence_score']}/2 standalone cues")
        if fresh and len(selected) < 10:
            reason += "; introduces a new episode to the posting list"
        selected.append({"rank": len(selected) + 1, **best, "ranking_reason": reason})
        represented.add(best["episode"])
        def duplicate(p):
            pairs = zip(fingerprints[id(best)], fingerprints[id(p)])
            return all(len(a & b) >= 0.8 * len(a | b) for a, b in pairs)
        pool = [p for p in pool if not duplicate(p)]
    return selected
