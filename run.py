"""Find continuous promos in a screenplay or directory of episode scripts."""

import argparse
import csv
import json
import logging
import os
import sys
from pathlib import Path
from time import perf_counter

from src.parser import parse_screenplay
from src.ranker import build_promo, enhance, posting_list
from src.windows import generate_windows, shortlist_windows


def load_project_env():
    path = Path(__file__).resolve().with_name(".env")
    if not path.is_file():
        return
    supported = {"GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL",
                 "OPENAI_API_KEY", "PROMO_MODEL", "PROMO_API_URL"}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        name = name.strip()
        if separator and name in supported:
            value = value.strip()
            if value.startswith(('"', "'")):
                value = value[1:].partition(value[0])[0]
            else:
                value = value.partition(" #")[0].rstrip()
            os.environ.setdefault(name, value)


def write_outputs(directory, promos, ranked):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "all_promos.json").write_text(
        json.dumps(promos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["rank", "episode", "segment_start", "segment_end", "duration_sec",
              "hook", "cliffhanger", "why_it_works", "composite_score", "mode",
              "independence_score", "ranking_reason"]
    with (directory / "top_ranked_promos.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(ranked)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    source = cli.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path)
    source.add_argument("--batch", type=Path)
    cli.add_argument("--mode", choices=["offline", "llm"], default="offline")
    cli.add_argument("--provider", choices=["gemini", "openai"], default="gemini")
    cli.add_argument("--output_dir", type=Path, default=Path("outputs"))
    args = cli.parse_args()
    if args.input and not args.input.is_file():
        cli.error("Input file does not exist")
    if args.batch and not args.batch.is_dir():
        cli.error("Batch directory does not exist")
    paths = [args.input] if args.input else sorted(args.batch.glob("*.txt"))
    if not paths:
        cli.error("No .txt files in batch directory")
    started = perf_counter()
    promos = []
    failures = warnings = processed = eligible = survivors = model_calls = enhanced = 0
    duration = 0.0
    key = None
    if args.mode == "llm":
        load_project_env()
        key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
               if args.provider == "gemini" else os.getenv("OPENAI_API_KEY"))
    if args.mode == "llm" and not key:
        logging.warning("%s API key unavailable; using offline scoring", args.provider)
    for path in paths:
        try:
            episode = parse_screenplay(path)
        except OSError as error:
            failures += 1
            logging.warning("%s: %s", path, error)
            continue
        warnings += len(episode["warnings"])
        if episode["episode_number"] is None or not episode["events"]:
            failures += 1
            continue
        processed += 1
        duration += episode["duration_sec"]
        windows = generate_windows(episode["events"])
        eligible += len(windows)
        survivors += sum(w["composite_score"] > 0 for w in windows)
        for window in shortlist_windows(windows):
            promo, events = build_promo(episode, window)
            if key:
                model_calls += 1
                try:
                    promo = enhance(promo, events, key, args.provider)
                    enhanced += 1
                except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
                    logging.warning("Model call failed (%s); using offline scoring for the rest of the run",
                                    type(error).__name__)
                    key = None
            promos.append(promo)
    ranked = posting_list(promos)
    write_outputs(args.output_dir, promos, ranked)
    if args.input:
        print(json.dumps(ranked[:3], indent=2))
    filtered = eligible - survivors
    ratio = 100 * filtered / eligible if eligible else 0
    print(f"Episodes processed: {processed}/{len(paths)}\nParse failures: {failures}"
          f"\nParse warnings: {warnings}\nShow duration: {duration:.2f} seconds"
          f"\nEligible windows: {eligible}\nFiltered by heuristics: {filtered}"
          f"\nHeuristic survivors: {survivors}\nHeuristic reduction: {ratio:.2f}%"
          f"\nFinal shortlisted promos: {len(promos)}\nPosting list: {len(ranked)}"
          f"\nModel requests: {model_calls}\nLLM-enhanced promos: {enhanced}"
          f"\nExecution time: {perf_counter() - started:.2f} seconds")
    return int(failures > 0)


if __name__ == "__main__":
    sys.exit(main())
