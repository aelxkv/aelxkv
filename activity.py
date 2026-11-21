"""Writes a short "recent activity" list into README.md.

Uses only the Python standard library and GitHub's public events API, so
there is no third-party action to trust.
"""
import json
import os
import sys
import urllib.error
import urllib.request

USER = "aelxkv"
README = "README.md"
START, END = "<!--ACTIVITY:START-->", "<!--ACTIVITY:END-->"
MAX_LINES = 6


def fetch_events():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-activity",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"https://api.github.com/users/{USER}/events/public?per_page=50",
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def describe(event):
    repo = event["repo"]["name"]
    link = f"[{repo}](https://github.com/{repo})"
    kind = event["type"]
    payload = event.get("payload", {})
    if kind == "PushEvent":
        return f"Pushed code to {link}"
    if kind == "CreateEvent" and payload.get("ref_type") == "repository":
        return f"Created {link}"
    if kind == "PullRequestEvent":
        action = payload.get("action", "updated")
        merged = payload.get("pull_request", {}).get("merged")
        return f"{'Merged' if merged else action.capitalize()} a pull request in {link}"
    if kind == "ForkEvent":
        return f"Forked {link}"
    if kind == "IssuesEvent":
        return f"{payload.get('action', 'updated').capitalize()} an issue in {link}"
    return None


def build(events):
    lines, seen = [], set()
    for event in events:
        text = describe(event)
        if not text:
            continue
        day = event["created_at"][:10]
        key = (day, text)
        if key in seen:  # collapse repeats on the same day
            continue
        seen.add(key)
        lines.append(f"- `{day}` {text}")
        if len(lines) == MAX_LINES:
            break
    return "\n".join(lines) if lines else "_Nothing public to show yet._"


def main():
    try:
        body = build(fetch_events())
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        sys.exit(f"Could not fetch activity: {err}")

    with open(README, encoding="utf-8") as f:
        text = f.read()
    if START not in text or END not in text:
        sys.exit(f"Markers {START} / {END} not found in {README}")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    with open(README, "w", encoding="utf-8") as f:
        f.write(f"{head}{START}\n{body}\n{END}{tail}")


if __name__ == "__main__":
    main()
