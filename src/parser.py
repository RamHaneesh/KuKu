"""Read a timestamped microdrama screenplay into episode metadata and events."""

import logging
import re
from pathlib import Path


LOGGER = logging.getLogger(__name__)
TIMING = re.compile(r"Start:\s*\(([^()]+)\)\s*\|\s*End:\s*\(([^()]+)\)", re.I)
HEADER = re.compile(r"\*\*(.+?):\*\*")
NON_DIALOGUE = {"CAMERA", "ACTION", "SOUND FX"}


def parse_timestamp(value: str) -> float:
    """Convert MM:SS.ss with optional parentheses to episode-relative seconds."""
    value = value.strip().removeprefix("(").removesuffix(")")
    match = re.fullmatch(r"(\d{1,6}):([0-5]\d(?:\.\d+)?)", value)
    if not match:
        raise ValueError(f"Invalid timestamp {value!r}")
    return round(int(match[1]) * 60 + float(match[2]), 6)


def parse_screenplay(path: str | Path) -> dict:
    path = Path(path)
    return parse_text(path.read_text(encoding="utf-8-sig", errors="replace"), path.name)


def parse_text(text: str, name: str) -> dict:
    episode_number = None
    logline = ""
    scene_id = None
    duration = 0.0
    events = []
    warnings = []

    def warn(line_number, message):
        warning = f"{name}:{line_number}: {message}"
        warnings.append(warning)
        LOGGER.warning("%s", warning)

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        line_number = index
        if "\ufffd" in line:
            warn(line_number, "Invalid text encoding")
        upper = line.upper()
        if not line or upper.startswith(("--- SCRIPT", "CONTINUITY NOTES:", "SCENE HEADING:", "ACTIONS AND DIALOGUE:")):
            continue
        if line.startswith("EPISODE NUMBER:"):
            number = re.fullmatch(r"EPISODE NUMBER:\s*(?:Episode\s+)?(\d{1,9})", line, re.I)
            if number:
                episode_number = int(number[1])
            else:
                warn(line_number, "Invalid episode number")
            continue
        if line.startswith("EPISODE LOGLINE:"):
            logline = line.partition(":")[2].strip()
            continue
        scene = re.fullmatch(r"SCENE\s+(\d+)", line, re.I)
        if scene:
            scene_id = scene[1]
            continue
        if upper.startswith(("SCENE START:", "SCENE END:")):
            try:
                seconds = parse_timestamp(line.partition(":")[2])
                if upper.startswith("SCENE END:"):
                    duration = max(duration, seconds)
            except ValueError as error:
                warn(line_number, str(error))
            continue
        header = HEADER.fullmatch(line)
        if not header:
            warn(line_number, "Unexpected screenplay line")
            continue
        timing = TIMING.fullmatch(lines[index].strip()) if index < len(lines) else None
        if not timing:
            warn(line_number, "Missing or malformed event timing")
            continue
        index += 1
        body = []
        while index < len(lines):
            content = lines[index].strip()
            if not content or content.upper().startswith(("**", "--- SCRIPT", "SCENE ")):
                break
            if "\ufffd" in content:
                warn(index + 1, "Invalid text encoding")
            body.append(content)
            index += 1
        try:
            start, end = (parse_timestamp(value) for value in timing.groups())
            if end < start or not body:
                raise ValueError("Reversed event interval or missing event text")
        except ValueError as error:
            warn(line_number, str(error))
            continue
        label, _, tags = header[1].partition(" (")
        event_type = label if label in NON_DIALOGUE else "DIALOGUE"
        events.append({
            "scene_id": scene_id,
            "type": event_type,
            "speaker": label if event_type == "DIALOGUE" else None,
            "emotions": [tag.strip() for tag in tags.rstrip(")").split(",") if tag.strip()],
            "start_time": start,
            "end_time": end,
            "text": " ".join(body),
        })
        duration = max(duration, end)

    for missing, message in [(episode_number is None, "Missing episode number"),
                             (not logline, "Missing logline"), (not events, "No valid events")]:
        if missing:
            warn(1, message)
    events.sort(key=lambda event: event["start_time"])
    return {"episode_number": episode_number, "logline": logline, "events": events,
            "duration_sec": duration, "warnings": warnings}
