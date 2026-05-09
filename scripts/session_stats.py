#!/usr/bin/env python3
"""
Optionally injects shields.io badge markup into a README.md between
<!-- CLAUDE_STATS_START --> and <!-- CLAUDE_STATS_END --> markers.

Usage:
    python3 session_stats.py <session_dir> <output_path> [--readme <readme_path>]

Arguments:
    session_dir  — path to ~/.claude/projects/C--code-voice-forge/
    output_path  — where to write the .md report
    --readme     — path to README.md to inject badges into (optional)
"""

import json
import os
import re
import sys
import glob
from datetime import datetime
from urllib.parse import quote


def parse_session(fpath):
    """Parse a single .jsonl session file and return a stats dict."""
    session_id = os.path.basename(fpath).replace(".jsonl", "")

    stats = {
        "id": session_id,
        "short_id": session_id[:8],
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read": 0,
        "cache_creation": 0,
        "api_calls": 0,
        "user_prompts": 0,
        "duration_ms": 0,
        "first_ts": None,
        "last_ts": None,
        "model": None,
        "date": None,
    }

    with open(fpath, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            ts = obj.get("timestamp")
            if ts:
                if stats["first_ts"] is None:
                    stats["first_ts"] = ts
                stats["last_ts"] = ts

            msg_type = obj.get("type")

            if msg_type == "assistant":
                msg = obj.get("message", {})
                if isinstance(msg, dict):
                    usage = msg.get("usage", {})
                    if usage:
                        stats["api_calls"] += 1
                        stats["input_tokens"] += usage.get("input_tokens", 0)
                        stats["output_tokens"] += usage.get("output_tokens", 0)
                        stats["cache_read"] += usage.get("cache_read_input_tokens", 0)
                        stats["cache_creation"] += usage.get("cache_creation_input_tokens", 0)
                    if not stats["model"]:
                        stats["model"] = msg.get("model", "unknown")

            elif msg_type == "user" and obj.get("message"):
                msg = obj["message"]
                if isinstance(msg, (str, dict)):
                    stats["user_prompts"] += 1

            elif msg_type == "system" and obj.get("durationMs"):
                stats["duration_ms"] = obj["durationMs"]

    # Derive wall-clock time
    stats["wall_ms"] = 0
    if stats["first_ts"] and stats["last_ts"]:
        try:
            t1 = datetime.fromisoformat(stats["first_ts"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(stats["last_ts"].replace("Z", "+00:00"))
            stats["wall_ms"] = int((t2 - t1).total_seconds() * 1000)
            stats["date"] = t1.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    return stats


def estimate_cost(input_t, output_t, cache_read_t, cache_create_t):
    """Estimate API cost in USD using Sonnet 4 pricing."""
    return (
        (input_t / 1_000_000) * 3.00
        + (output_t / 1_000_000) * 15.00
        + (cache_read_t / 1_000_000) * 0.30
        + (cache_create_t / 1_000_000) * 3.75
    )


def fmt_duration(ms):
    """Format milliseconds as human-readable duration."""
    if ms <= 0:
        return "n/a"
    seconds = ms / 1000
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def fmt_tokens(n):
    """Format token count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def generate_report(sessions):
    """Generate the Markdown report string."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Grand totals
    totals = {
        "sessions": len(sessions),
        "api_calls": sum(s["api_calls"] for s in sessions),
        "user_prompts": sum(s["user_prompts"] for s in sessions),
        "input_tokens": sum(s["input_tokens"] for s in sessions),
        "output_tokens": sum(s["output_tokens"] for s in sessions),
        "cache_read": sum(s["cache_read"] for s in sessions),
        "cache_creation": sum(s["cache_creation"] for s in sessions),
        "thinking_ms": sum(s["duration_ms"] for s in sessions),
        "wall_ms": sum(s["wall_ms"] for s in sessions),
    }
    totals["all_tokens"] = (
        totals["input_tokens"]
        + totals["output_tokens"]
        + totals["cache_read"]
        + totals["cache_creation"]
    )
    totals["cost"] = estimate_cost(
        totals["input_tokens"],
        totals["output_tokens"],
        totals["cache_read"],
        totals["cache_creation"],
    )

    thinking_ratio = (
        (totals["thinking_ms"] / totals["wall_ms"] * 100)
        if totals["wall_ms"] > 0
        else 0
    )

    lines = []
    lines.append("# VoiceForge — Claude Code Session Stats")
    lines.append("")
    lines.append(f"*Last updated: {now}*")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Sessions | {totals['sessions']} |")
    lines.append(f"| API calls | {totals['api_calls']:,} |")
    lines.append(f"| User prompts | {totals['user_prompts']:,} |")
    lines.append(f"| Claude thinking time | {fmt_duration(totals['thinking_ms'])} |")
    lines.append(f"| Wall-clock time | {fmt_duration(totals['wall_ms'])} |")
    lines.append(f"| Thinking/wall ratio | {thinking_ratio:.1f}% |")
    lines.append(f"| Total tokens | {fmt_tokens(totals['all_tokens'])} |")
    lines.append(f"| Output tokens | {fmt_tokens(totals['output_tokens'])} |")
    lines.append(f"| Cache read tokens | {fmt_tokens(totals['cache_read'])} |")
    lines.append(f"| Estimated API cost | ${totals['cost']:.2f} |")
    lines.append("")

    # Per-session table
    lines.append("## Per-Session Breakdown")
    lines.append("")
    lines.append(
        "| Date | Session | Model | API Calls | Output Tokens | Cache Read | Thinking | Wall Time | Est. Cost |"
    )
    lines.append(
        "|------|---------|-------|----------:|--------------:|-----------:|---------:|----------:|----------:|"
    )

    for s in sorted(sessions, key=lambda x: x["first_ts"] or ""):
        cost = estimate_cost(
            s["input_tokens"], s["output_tokens"], s["cache_read"], s["cache_creation"]
        )
        date = s["date"] or "unknown"
        lines.append(
            f"| {date} | `{s['short_id']}` | {s['model'] or '?'} "
            f"| {s['api_calls']} | {fmt_tokens(s['output_tokens'])} "
            f"| {fmt_tokens(s['cache_read'])} | {fmt_duration(s['duration_ms'])} "
            f"| {fmt_duration(s['wall_ms'])} | ${cost:.2f} |"
        )

    lines.append("")

    # Daily aggregation
    daily = {}
    for s in sessions:
        d = s["date"] or "unknown"
        if d not in daily:
            daily[d] = {
                "sessions": 0,
                "api_calls": 0,
                "output_tokens": 0,
                "thinking_ms": 0,
                "wall_ms": 0,
                "cost": 0,
            }
        daily[d]["sessions"] += 1
        daily[d]["api_calls"] += s["api_calls"]
        daily[d]["output_tokens"] += s["output_tokens"]
        daily[d]["thinking_ms"] += s["duration_ms"]
        daily[d]["wall_ms"] += s["wall_ms"]
        daily[d]["cost"] += estimate_cost(
            s["input_tokens"], s["output_tokens"], s["cache_read"], s["cache_creation"]
        )

    lines.append("## Daily Totals")
    lines.append("")
    lines.append(
        "| Date | Sessions | API Calls | Output Tokens | Thinking | Wall Time | Est. Cost |"
    )
    lines.append(
        "|------|:--------:|----------:|--------------:|---------:|----------:|----------:|"
    )
    for d in sorted(daily.keys()):
        v = daily[d]
        lines.append(
            f"| {d} | {v['sessions']} | {v['api_calls']} "
            f"| {fmt_tokens(v['output_tokens'])} | {fmt_duration(v['thinking_ms'])} "
            f"| {fmt_duration(v['wall_ms'])} | ${v['cost']:.2f} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*Cost estimates use Claude Sonnet 4 API pricing: "
        "$3/M input, $15/M output, $0.30/M cache read, $3.75/M cache write. "
        "Actual cost depends on your plan.*"
    )
    lines.append("")

    return "\n".join(lines)


def badge(label, value, color, logo=None):
    """Generate a shields.io badge URL in Markdown."""
    label_enc = quote(label, safe="")
    value_enc = quote(str(value), safe="")
    url = f"https://img.shields.io/badge/{label_enc}-{value_enc}-{color}?style=for-the-badge"
    if logo:
        url += f"&logo={logo}&logoColor=white"
    return f"![{label}: {value}]({url})"


def generate_badges(sessions):
    """Generate a block of shields.io badge Markdown from session stats."""
    totals = {
        "sessions": len(sessions),
        "api_calls": sum(s["api_calls"] for s in sessions),
        "output_tokens": sum(s["output_tokens"] for s in sessions),
        "thinking_ms": sum(s["duration_ms"] for s in sessions),
        "wall_ms": sum(s["wall_ms"] for s in sessions),
        "cost": estimate_cost(
            sum(s["input_tokens"] for s in sessions),
            sum(s["output_tokens"] for s in sessions),
            sum(s["cache_read"] for s in sessions),
            sum(s["cache_creation"] for s in sessions),
        ),
    }
    all_tokens = sum(
        s["input_tokens"] + s["output_tokens"] + s["cache_read"] + s["cache_creation"]
        for s in sessions
    )

    badges = [
        badge("sessions", totals["sessions"], "1a1b27", "anthropic"),
        badge("API calls", f"{totals['api_calls']:,}", "7aa2f7", "anthropic"),
        badge("tokens", fmt_tokens(all_tokens), "bb9af7", "anthropic"),
        badge("thinking time", fmt_duration(totals["thinking_ms"]), "7dcfff", "anthropic"),
        badge("wall clock", fmt_duration(totals["wall_ms"]), "3d59a1", "anthropic"),
        badge("est. cost", f"${totals['cost']:.2f}", "73daca", "anthropic"),
    ]

    lines = [
        "<!-- CLAUDE_STATS_START -->",
        "#### Claude Code Stats",
        "",
        " ".join(badges),
        "<!-- CLAUDE_STATS_END -->",
    ]
    return "\n".join(lines)


def inject_badges_into_readme(readme_path, badge_block):
    """Replace content between CLAUDE_STATS markers in README, or append."""
    with open(readme_path, "r") as f:
        content = f.read()

    pattern = r"<!-- CLAUDE_STATS_START -->.*?<!-- CLAUDE_STATS_END -->"
    if re.search(pattern, content, re.DOTALL):
        updated = re.sub(pattern, badge_block, content, flags=re.DOTALL)
    else:
        # Insert after the first heading block (# Title + ### Subtitle)
        heading_pattern = r"(#[^\n]+\n\n###[^\n]+\n)"
        match = re.search(heading_pattern, content)
        if match:
            insert_pos = match.end()
            updated = content[:insert_pos] + "\n" + badge_block + "\n" + content[insert_pos:]
        else:
            updated = badge_block + "\n\n" + content

    with open(readme_path, "w") as f:
        f.write(updated)


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <session_dir> <output_path> [--readme <path>]", file=sys.stderr)
        sys.exit(1)

    session_dir = sys.argv[1]
    output_path = sys.argv[2]

    readme_path = None
    if "--readme" in sys.argv:
        idx = sys.argv.index("--readme")
        if idx + 1 < len(sys.argv):
            readme_path = sys.argv[idx + 1]

    jsonl_files = sorted(glob.glob(os.path.join(session_dir, "*.jsonl")))
    if not jsonl_files:
        print(f"No .jsonl files found in {session_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {len(jsonl_files)} session files...")
    sessions = [parse_session(f) for f in jsonl_files]

    report = generate_report(sessions)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report written to {output_path}")

    if readme_path and os.path.exists(readme_path):
        badge_block = generate_badges(sessions)
        inject_badges_into_readme(readme_path, badge_block)
        print(f"Badges injected into {readme_path}")

    total_tokens = sum(
        s["input_tokens"] + s["output_tokens"] + s["cache_read"] + s["cache_creation"]
        for s in sessions
    )
    print(f"Sessions: {len(sessions)}, Total tokens: {fmt_tokens(total_tokens)}")


if __name__ == "__main__":
    main()
