#!/usr/bin/env python3
"""
Tavily Web Search CLI

Search the web via Tavily API (https://tavily.com).
Requires TAVILY_API_KEY environment variable, or hardcode DEFAULT_API_KEY below.

Usage:
    python3 tavily_search.py "your search query"
    python3 tavily_search.py "query" --max-results 5
    python3 tavily_search.py "query" --topic news
    python3 tavily_search.py "query" --search-depth advanced
    python3 tavily_search.py "query" --include-answer
    python3 tavily_search.py "query" --raw
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


API_URL = "https://api.tavily.com/search"

# ← 手动填写你的 API key（推荐放到 ~/.env 里走 TAVILY_API_KEY，不修改这里）
DEFAULT_API_KEY = "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"


def _strip_env_value(value: str) -> str:
    """Return a simple dotenv value without surrounding quotes/comments."""
    value = value.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'}:
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
    return value.split(" #", 1)[0].strip().strip("'\"")


def _candidate_env_files() -> list[Path]:
    """Candidate .env files, without assuming a hard-coded install path."""
    candidates: list[Path] = []
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        candidates.append(Path(hermes_home).expanduser() / ".env")

    home = Path.home()
    candidates.extend([home / ".hermes" / ".env", home / ".env"])

    script_path = Path(__file__).resolve()
    for parent in script_path.parents[:6]:
        candidates.append(parent / ".env")

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def _load_api_key() -> str:
    """Load TAVILY_API_KEY from env -> .env candidates -> DEFAULT_API_KEY."""
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if api_key:
        return api_key

    for env_path in _candidate_env_files():
        if not env_path.is_file():
            continue
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "TAVILY_API_KEY":
                    val = _strip_env_value(v)
                    if val:
                        return val
        except Exception:
            continue

    if DEFAULT_API_KEY and DEFAULT_API_KEY != "tvly-YOUR_API_KEY":
        return DEFAULT_API_KEY
    return ""


def search(
    query: str,
    max_results: int = 10,
    search_depth: str = "basic",
    topic: str = "general",
    include_answer: bool = False,
) -> dict:
    """Call Tavily REST API. Returns parsed JSON response dict."""
    api_key = _load_api_key()
    if not api_key:
        raise SystemExit(
            "Error: TAVILY_API_KEY is not set. "
            "Set it in shell, ~/.env, or hardcode DEFAULT_API_KEY in this script."
        )

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "topic": topic,
        "include_answer": include_answer,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP Error {e.code}: {body}") from e


def _format_response(response: dict, query: str, include_answer: bool) -> str:
    results = response.get("results", []) or []
    lines = [f'=== Search Results for "{query}" ({len(results)} results) ===', ""]
    if include_answer and response.get("answer"):
        lines.append(f"Answer: {response['answer']}")
        lines.append("")
    for i, item in enumerate(results, 1):
        title = item.get("title") or "(no title)"
        url = item.get("url") or ""
        snippet = (item.get("content") or "").strip().replace("\n", " ")
        if len(snippet) > 200:
            snippet = snippet[:200] + "..."
        lines.append(f"{i}. {title}")
        lines.append(f"   {url}")
        lines.append(f"   {snippet}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tavily web search CLI")
    parser.add_argument("query", help="Search query string")
    parser.add_argument(
        "--max-results", type=int, default=10,
        help="Maximum number of results (default: 10, max: 20)",
    )
    parser.add_argument(
        "--search-depth", choices=["basic", "advanced"], default="basic",
        help="Search depth (default: basic; advanced is more thorough but slower)",
    )
    parser.add_argument(
        "--topic", choices=["general", "news"], default="general",
        help="Search topic (default: general)",
    )
    parser.add_argument(
        "--include-answer", action="store_true",
        help="Include a synthesized answer in the output",
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="Output raw JSON response (for piping/processing)",
    )
    args = parser.parse_args()

    response = search(
        query=args.query,
        max_results=args.max_results,
        search_depth=args.search_depth,
        topic=args.topic,
        include_answer=args.include_answer,
    )

    if args.raw:
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return

    print(_format_response(response, args.query, args.include_answer))


if __name__ == "__main__":
    main()
