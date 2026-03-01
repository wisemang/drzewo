from collections import Counter

import nginx_log_analysis


def test_parse_log_line_extracts_path_and_query():
    line = (
        '203.0.113.10 - - [01/Mar/2026:02:10:00 +0000] '
        '"GET /nearest?lat=43.65&lng=-79.38&limit=40 HTTP/1.1" '
        '200 123 "-" '
        '"Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"'
    )

    record = nginx_log_analysis.parse_log_line(line)

    assert record["ip"] == "203.0.113.10"
    assert record["path"] == "/nearest"
    assert record["query"]["lat"] == ["43.65"]
    assert record["status"] == 200


def test_analyze_logs_counts_estimated_users_and_nearest_cells(tmp_path):
    log_path = tmp_path / "access.log"
    log_path.write_text(
        "\n".join(
            [
                '203.0.113.10 - - [01/Mar/2026:02:10:00 +0000] '
                '"GET /nearest?lat=43.65&lng=-79.38 HTTP/1.1" 200 123 "-" '
                '"Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)"',
                '198.51.100.8 - - [01/Mar/2026:02:11:00 +0000] '
                '"GET / HTTP/1.1" 200 456 "-" '
                '"Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0)"',
                '192.0.2.77 - - [01/Mar/2026:02:12:00 +0000] '
                '"GET /nearest?lat=43.65&lng=-79.38 HTTP/1.1" 200 123 "-" '
                '"curl/8.0.1"',
            ]
        ),
        encoding="utf-8",
    )

    summary = nginx_log_analysis.analyze_logs([log_path], top_n=5)

    assert summary["totals"]["requests"] == 3
    assert summary["totals"]["nearest_requests"] == 2
    assert summary["estimated_users_by_day"]["01/Mar/2026"] == 1
    assert summary["nearest_query_cells"]["43.65,-79.38"] == 2


def test_format_summary_includes_core_sections():
    summary = {
        "totals": {"requests": 1, "nearest_requests": 1, "nearest_success": 1},
        "by_day": {"01/Mar/2026": {"requests": 1, "nearest_requests": 1, "nearest_success": 1}},
        "endpoint_counts": Counter({"/nearest": 1}),
        "ip_counts": Counter({"203.0.113.10": 1}),
        "user_agent_counts": Counter({"Mozilla/5.0": 1}),
        "nearest_query_cells": Counter({"43.65,-79.38": 1}),
        "estimated_users_by_day": {"01/Mar/2026": 1},
        "bot_requests": 0,
        "malformed_lines": 0,
        "top_n": 5,
    }

    output = nginx_log_analysis.format_summary(summary)

    assert "Overview" in output
    assert "Top Endpoints" in output
    assert "Top /nearest Query Cells" in output
