"""Score shortlisted screenplay clips in one request per episode."""

import json
import os
from urllib.request import Request, urlopen


DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


def enhance_episode(pairs, key, provider="gemini", *, model=None):
    """Use an OpenAI-compatible chat completions endpoint; validate before relabelling."""
    if not pairs:
        return []
    clips = [{"id": i, "start": promo["segment_start"], "end": promo["segment_end"],
              "events": events} for i, (promo, events) in enumerate(pairs)]
    if provider == "gemini":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        model = model or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
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
                                  "Evaluate each clip independently as screenplay data for a first-time viewer. "
                                  "Return a JSON object with a results array, one entry per clip. Copy its integer id. Include numeric hook_score and cliffhanger_score, each 1 to 10, "
                                  "for the first and last three seconds respectively. In why_it_works, "
                                  "explain in one sentence who wants what and what remains unresolved at "
                                  "the cut. If the stakes are unclear or the conflict is resolved, say so. "
                                  "Use only evidence within the clip boundaries.")},
                              {"role": "user", "content": json.dumps(clips)},
                          ],
                      }).encode())
    with urlopen(request, timeout=90) as response:
        payload = json.load(response)
    results = json.loads(payload["choices"][0]["message"]["content"])["results"]
    if not isinstance(results, list) or len(results) != len(pairs):
        raise ValueError("Incomplete episode scores")
    by_id = {}
    for result in results:
        clip_id = result["id"]
        if type(clip_id) is not int or not 0 <= clip_id < len(pairs) or clip_id in by_id:
            raise ValueError("Invalid clip id")
        by_id[clip_id] = scored_promo(pairs[clip_id][0], result, model)
    return [by_id[i] for i in range(len(pairs))]


def scored_promo(promo, result, model):
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
