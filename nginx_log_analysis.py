import argparse
import gzip
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

LOG_PATTERN = re.compile(
    r'(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>[A-Z]+) (?P<target>[^"]+) (?P<protocol>[^"]+)" '
    r'(?P<status>\d{3}) (?P<bytes>\S+) "(?P<referer>[^"]*)" "(?P<user_agent>[^"]*)"'
)

BOT_MARKERS = ("bot", "spider", "crawler", "curl", "wget", "python-requests", "uptime")
BROWSER_MARKERS = ("mozilla", "safari", "chrome", "firefox", "edg", "iphone", "android")


def parse_log_line(line):
    """Parse one Nginx combined-format log line."""
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    payload = match.groupdict()
    split_target = urlsplit(payload["target"])
    payload["path"] = split_target.path
    payload["query"] = parse_qs(split_target.query)
    payload["status"] = int(payload["status"])
    payload["day"] = payload["timestamp"].split(":", 1)[0]
    return payload


def is_bot_user_agent(user_agent):
    user_agent = (user_agent or "").lower()
    return any(marker in user_agent for marker in BOT_MARKERS)


def is_browser_user_agent(user_agent):
    user_agent = (user_agent or "").lower()
    return any(marker in user_agent for marker in BROWSER_MARKERS) and not is_bot_user_agent(
        user_agent
    )


def iter_log_lines(path):
    """Yield log lines from plain text or gzip-compressed files."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        yield from handle


def expand_log_paths(patterns):
    """Expand provided files/globs into a sorted unique path list."""
    paths = []
    for pattern in patterns:
        candidate = Path(pattern)
        if any(char in pattern for char in "*?[]"):
            paths.extend(Path().glob(pattern))
        elif candidate.exists():
            paths.append(candidate)
    return sorted({path.resolve() for path in paths})


def analyze_logs(paths, top_n=10):
    """Aggregate request and user-oriented summary metrics."""
    totals = Counter()
    by_day = defaultdict(Counter)
    endpoint_counts = Counter()
    ip_counts = Counter()
    user_agent_counts = Counter()
    nearest_query_cells = Counter()
    estimated_users_by_day = defaultdict(set)
    bot_requests = 0
    malformed = 0

    for path in paths:
        for line in iter_log_lines(path):
            record = parse_log_line(line)
            if record is None:
                malformed += 1
                continue

            day = record["day"]
            ip = record["ip"]
            user_agent = record["user_agent"]
            endpoint = record["path"]

            totals["requests"] += 1
            by_day[day]["requests"] += 1
            endpoint_counts[endpoint] += 1
            ip_counts[ip] += 1
            user_agent_counts[user_agent] += 1

            if is_bot_user_agent(user_agent):
                bot_requests += 1
                by_day[day]["bot_requests"] += 1

            if endpoint == "/nearest":
                totals["nearest_requests"] += 1
                by_day[day]["nearest_requests"] += 1
                if record["status"] < 400:
                    totals["nearest_success"] += 1
                    by_day[day]["nearest_success"] += 1
                lat = record["query"].get("lat", [None])[0]
                lng = record["query"].get("lng", [None])[0]
                if lat and lng:
                    cell = f"{round(float(lat), 2)},{round(float(lng), 2)}"
                    nearest_query_cells[cell] += 1
                if record["status"] < 400 and is_browser_user_agent(user_agent) and lat and lng:
                    estimated_users_by_day[day].add((ip, user_agent))

    return {
        "totals": totals,
        "by_day": by_day,
        "endpoint_counts": endpoint_counts,
        "ip_counts": ip_counts,
        "user_agent_counts": user_agent_counts,
        "nearest_query_cells": nearest_query_cells,
        "estimated_users_by_day": {
            day: len(users) for day, users in estimated_users_by_day.items()
        },
        "bot_requests": bot_requests,
        "malformed_lines": malformed,
        "top_n": top_n,
    }


def format_summary(summary):
    """Render a compact text report."""
    lines = []
    totals = summary["totals"]
    lines.append("Overview")
    lines.append(f"  Requests: {totals['requests']}")
    lines.append(f"  /nearest requests: {totals['nearest_requests']}")
    lines.append(f"  Successful /nearest requests: {totals['nearest_success']}")
    lines.append(f"  Bot-like requests: {summary['bot_requests']}")
    lines.append(f"  Malformed lines skipped: {summary['malformed_lines']}")
    lines.append("")
    lines.append("Daily")
    for day in sorted(summary["by_day"]):
        counters = summary["by_day"][day]
        estimated_users = summary["estimated_users_by_day"].get(day, 0)
        lines.append(
            f"  {day}: requests={counters['requests']} "
            f"nearest={counters['nearest_requests']} "
            f"nearest_success={counters['nearest_success']} "
            f"estimated_users={estimated_users}"
        )
    lines.append("")
    lines.append("Top Endpoints")
    for endpoint, count in summary["endpoint_counts"].most_common(summary["top_n"]):
        lines.append(f"  {count:>6} {endpoint}")
    lines.append("")
    lines.append("Top IPs")
    for ip, count in summary["ip_counts"].most_common(summary["top_n"]):
        lines.append(f"  {count:>6} {ip}")
    lines.append("")
    lines.append("Top User Agents")
    for user_agent, count in summary["user_agent_counts"].most_common(summary["top_n"]):
        label = user_agent if user_agent else "<empty>"
        lines.append(f"  {count:>6} {label[:120]}")
    lines.append("")
    lines.append("Top /nearest Query Cells (rounded lat/lng)")
    for cell, count in summary["nearest_query_cells"].most_common(summary["top_n"]):
        lines.append(f"  {count:>6} {cell}")
    return "\n".join(lines)


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Analyze Nginx access logs for drzewo usage patterns."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["/var/log/nginx/access.log", "/var/log/nginx/access.log*.gz"],
        help="Log files or glob patterns to analyze.",
    )
    parser.add_argument(
        "--top", type=int, default=10, help="Number of top entries to display per section."
    )
    return parser


def main():
    parser = build_argument_parser()
    args = parser.parse_args()
    paths = expand_log_paths(args.paths)
    if not paths:
        raise SystemExit("No matching log files found.")
    summary = analyze_logs(paths, top_n=args.top)
    print(format_summary(summary))


if __name__ == "__main__":
    main()
