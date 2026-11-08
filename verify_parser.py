"""Run from the project root with python verify_parser.py."""

import json
from pathlib import Path

from src.parser import parse_screenplay, parse_timestamp


def main():
    folder = Path(__file__).parent / "I Married a Broken Soldier. He was a Duke"
    episode = parse_screenplay(folder / "episode-043-Episode 1686803.txt")
    events = episode["events"]
    assert episode["episode_number"] == 43 and episode["logline"]
    assert not episode["warnings"], episode["warnings"]
    assert parse_timestamp("(00:14.20)") == 14.2
    assert events == sorted(events, key=lambda event: event["start_time"])
    assert all(event["end_time"] >= event["start_time"] for event in events)
    assert events[1]["speaker"] == "BLOND NOBLEMAN"
    assert events[1]["emotions"] == ["Hysterical", "Panicked"]
    assert episode["duration_sec"] == 114.96
    print(json.dumps(events[:5], indent=2))
    print(f"Episode 43: {len(events)} events, {episode['duration_sec']:.2f} seconds")


if __name__ == "__main__":
    main()
