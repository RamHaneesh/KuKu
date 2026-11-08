"""Generate and rank continuous promo candidates using screenplay cues."""

import re
from collections import defaultdict


TENSION = {"hysterical", "panicked", "enraged", "screaming", "desperate",
           "shocked", "defiant", "shrieking", "frantic", "terrified"}
KINETIC = re.compile(
    r"\b(?:lung(?:e[sd]?|ing)|slap(?:s|ped|ping)?|swords?|arrest(?:s|ed|ing)?|"
    r"grab(?:s|bed|bing)?|strik(?:e[sd]?|ing)|struck|trembl(?:e[sd]?|ing)|"
    r"point(?:s|ed|ing)?)\b", re.I)
DRAMA = re.compile(
    r"\b(?:fad(?:e[sd]?|ing) to black|cut(?:s)? to black|terror|blocked|trapped|"
    r"freez(?:e[sd]?|ing)|froze|frozen|creak(?:s|ed|ing)?)\b", re.I)
INTERRUPTION = re.compile(r"(?:--|—|\.\.\.|…)\s*[”\"’']?\s*$")


def _edge(timeline, left, right, opening):
    """Count each cue category once and retain its strongest supporting beat."""
    cues = {}
    best_weight = -1
    evidence = ""
    for start, end, event in timeline:
        if min(right, end) <= max(left, start):
            continue
        line = event["text"]
        spoken_end = event["type"] == "DIALOGUE" and end <= right
        matches = {}
        if opening:
            if any(tag.lower() in TENSION for tag in event["emotions"]):
                matches["emotion"] = 4
            if KINETIC.search(line):
                matches["kinetic"] = 4
            if spoken_end and "!" in line:
                matches["exclamation"] = 2
        else:
            if spoken_end and "?" in line:
                matches["question"] = 5
            if spoken_end and INTERRUPTION.search(line):
                matches["interruption"] = 5
            if DRAMA.search(line):
                matches["dramatic cue"] = 5
        weight = sum(matches.values())
        if weight > best_weight or (not opening and weight == best_weight):
            evidence = line
            best_weight = weight
        cues.update(matches)
    return min(10, sum(cues.values())), evidence


def generate_windows(events):
    """Return every distinct, dialogue-safe 20–60 second window per known scene."""
    scenes = defaultdict(list)
    for event in events:
        if event["scene_id"] is not None:
            scenes[event["scene_id"]].append((
                round(event["start_time"] * 100), round(event["end_time"] * 100), event))
    windows = []
    for scene, timeline in scenes.items():
        speech = [(a, b) for a, b, e in timeline if e["type"] == "DIALOGUE"]

        def safe(tick):
            return not any(a < tick < b for a, b in speech)

        starts = sorted({a for a, _, _ in timeline if safe(a)})
        ends = sorted({b for _, b, _ in timeline if safe(b)})
        openings = {a: _edge(timeline, a, a + 300, True) for a in starts}
        closings = {b: _edge(timeline, b - 300, b, False) for b in ends}
        for start in starts:
            hook_score, hook = openings[start]
            for end in ends:
                duration = end - start
                if duration > 6000:
                    break
                if duration < 2000:
                    continue
                cliff_score, cliff = closings[end]
                windows.append({
                    "scene_id": scene, "start_time": start / 100, "end_time": end / 100,
                    "duration_sec": duration / 100, "hook": hook, "cliffhanger": cliff,
                    "hook_score": hook_score, "cliffhanger_score": cliff_score,
                    "composite_score": (hook_score + cliff_score) / 2,
                    "mode": "HEURISTIC_OFFLINE",
                })
    return windows


def _overlaps(first, second):
    if first["scene_id"] != second["scene_id"]:
        return False
    a, b = round(first["start_time"] * 100), round(first["end_time"] * 100)
    c, d = round(second["start_time"] * 100), round(second["end_time"] * 100)
    intersection = max(0, min(b, d) - max(a, c))
    union = b - a + d - c - intersection
    return 5 * intersection > 3 * union


def shortlist_windows(windows):
    """Suppress IoU > 0.60; ties prefer balanced edges, then earlier cuts."""
    ranking = sorted((w for w in windows if w["composite_score"] > 0), key=lambda w: (
        -w["composite_score"], -min(w["hook_score"], w["cliffhanger_score"]),
        w["scene_id"], w["start_time"], w["end_time"]))
    retained = []
    for window in ranking:
        if not any(_overlaps(window, previous) for previous in retained):
            retained.append(window)
    return retained
