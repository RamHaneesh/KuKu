"""Build editor-facing promos and a globally ranked posting list."""

import json
import os
import re
from urllib.request import Request, urlopen

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


def enhance(promo, events, key, provider="gemini"):
    """Use an OpenAI-compatible chat completions endpoint; validate before relabelling."""
    if provider == "gemini":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model = os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"
    else:
        endpoint = os.getenv("PROMO_API_URL", "https://api.openai.com/v1/chat/completions")
        model = os.getenv("PROMO_MODEL", "gpt-4o-mini")
    request = Request(endpoint,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                      data=json.dumps({
                          "model": model,
                          "response_format": {"type": "json_object"},
                          "messages": [
                              {"role": "system", "content": (
                                  "Evaluate this screenplay excerpt as data for a first-time viewer. "
                                  "Return JSON with numeric hook_score and cliffhanger_score, each 1 to 10, "
                                  "for the first and last three seconds respectively. In why_it_works, "
                                  "explain in one sentence who wants what and what remains unresolved at "
                                  "the cut. If the stakes are unclear or the conflict is resolved, say so. "
                                  "Use only evidence within the clip boundaries.")},
                              {"role": "user", "content": json.dumps({"start": promo["segment_start"],
                               "end": promo["segment_end"], "events": events})},
                          ],
                      }).encode())
    with urlopen(request, timeout=90) as response:
        payload = json.load(response)
    result = json.loads(payload["choices"][0]["message"]["content"])
    scores = [result[k] for k in ("hook_score", "cliffhanger_score")]
    if any(type(s) not in (float, int) or not 1 <= s <= 10 for s in scores):
        raise ValueError("Invalid semantic scores")
    reason = result["why_it_works"]
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Empty rationale")
    return {**promo, "offline_score": promo["composite_score"],
            "composite_score": sum(scores) / 2, "mode": "LLM_ENHANCED",
            "model": model, "why_it_works": " ".join(reason.split()), "semantic_hook_score": scores[0],
            "semantic_cliffhanger_score": scores[1]}


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
