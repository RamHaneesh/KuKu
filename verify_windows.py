"""Verify the heuristic window generator offline on Episode 43."""

from pathlib import Path

from src.parser import parse_screenplay
from src.windows import generate_windows, shortlist_windows


def timestamp(seconds):
    minute, ticks = divmod(round(seconds * 100), 6000)
    return f"{minute:02}:{ticks // 100:02}.{ticks % 100:02}"


def show(label, window):
    print(f"\n{label}: {timestamp(window['start_time'])} - {timestamp(window['end_time'])}"
          f" ({window['duration_sec']:.2f}s), score {window['composite_score']:.1f}/10")
    print(f"  Hook ({window['hook_score']}/10): {window['hook']}")
    print(f"  Cliffhanger ({window['cliffhanger_score']}/10): {window['cliffhanger']}")


def main():
    path = (Path(__file__).parent / "I Married a Broken Soldier. He was a Duke"
            / "episode-043-Episode 1686803.txt")
    events = parse_screenplay(path)["events"]
    windows = generate_windows(events)
    ranked = shortlist_windows(windows)
    keys = {(w["scene_id"], w["start_time"], w["end_time"]) for w in windows}
    assert len(keys) == len(windows)
    assert all(20 <= w["duration_sec"] <= 60 for w in windows)
    for scene, start, end in keys:
        assert all(not (e["start_time"] < t < e["end_time"])
                   for e in events if e["scene_id"] == scene and e["type"] == "DIALOGUE"
                   for t in (start, end))
    print(f"Episode 43: {len(windows)} raw windows")
    print(f"After heuristic filtering: {sum(w['composite_score'] > 0 for w in windows)}")
    print(f"After deduplication: {len(ranked)}")
    for rank, window in enumerate(ranked[:3], 1):
        show(f"Rank {rank}", window)
    show("Lowest before pruning", min(windows, key=lambda w: w["composite_score"]))


if __name__ == "__main__":
    main()
