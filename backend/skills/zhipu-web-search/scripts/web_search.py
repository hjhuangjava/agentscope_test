#!/usr/bin/env python3
"""
ZhipuAI Web Search CLI

Search the web via the ZhipuAI (智谱) Web Search API.
Requires GLM_API_KEY environment variable.

Usage:
    python3 web_search.py "your search query"
    python3 web_search.py "query" --count 5
    python3 web_search.py "query" --recency oneDay
    python3 web_search.py "query" --domain "github.com"
    python3 web_search.py "query" --raw
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import uuid
from datetime import datetime
from pathlib import Path


API_URL = "https://open.bigmodel.cn/api/paas/v4/web_search"
VALID_RECENCY = ["noLimit", "oneDay", "oneWeek", "oneMonth", "oneYear"]


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
    """Load GLM_API_KEY from env, then common Hermes/profile .env locations."""
    api_key = os.environ.get("GLM_API_KEY", "").strip()
    if api_key:
        return api_key

    for env_path in _candidate_env_files():
        if not env_path.is_file():
            continue
        try:
            lines = env_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = env_path.read_text(encoding="latin-1").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == "GLM_API_KEY":
                api_key = _strip_env_value(value)
                if api_key:
                    os.environ["GLM_API_KEY"] = api_key
                    return api_key
    return ""


def search(
    query: str,
    count: int = 10,
    recency: str = "noLimit",
    domain: str = "",
    search_intent: bool = False,
    request_id: str = "",
    user_id: str = "",
) -> dict:
    """Perform a web search via the ZhipuAI API.

    Returns the parsed JSON response dict.
    """
    api_key = _load_api_key()
    if not api_key:
        print("Error: GLM_API_KEY is not set.", file=sys.stderr)
        print("Set it in the shell environment or in your Hermes .env file.", file=sys.stderr)
        print("Hermes .env is resolved from $HERMES_HOME/.env, then common profile/home locations.", file=sys.stderr)
        sys.exit(1)

    if recency not in VALID_RECENCY:
        print(f"Error: Invalid recency filter '{recency}'. Must be one of: {VALID_RECENCY}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "search_query": query,
        "search_engine": "search_std",
        "search_intent": search_intent,
        "count": count,
        "search_domain_filter": domain,
        "search_recency_filter": recency,
    }

    # Add optional fields only if provided
    if request_id:
        payload["request_id"] = request_id
    else:
        payload["request_id"] = str(uuid.uuid4())

    if user_id:
        payload["user_id"] = user_id

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
        return response_data
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        if error_body:
            print(f"Response: {error_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network Error: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing API response: {e}", file=sys.stderr)
        sys.exit(1)


def format_results(query: str, data: dict) -> str:
    """Format API response into human-readable output."""
    lines = []

    # Extract the search results list
    # The API may return results under different keys depending on version
    results = data.get("search_result") or data.get("results") or data.get("data") or []

    if isinstance(results, dict):
        # Sometimes the results are nested
        results = results.get("search_result") or results.get("results") or []

    if not isinstance(results, list):
        # If we can't find a list, show the raw structure for debugging
        lines.append(f"=== Search Results for \"{query}\" ===")
        lines.append("(Unexpected response format, showing raw data)")
        lines.append("")
        lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        return "\n".join(lines)

    count = len(results)
    lines.append(f'=== Search Results for "{query}" ({count} result{"s" if count != 1 else ""}) ===')
    lines.append("")

    for i, item in enumerate(results, 1):
        title = item.get("title") or item.get("name") or "(No title)"
        url = item.get("url") or item.get("link") or item.get("href") or ""
        snippet = item.get("content") or item.get("snippet") or item.get("description") or item.get("abstract") or ""
        source = item.get("source") or item.get("domain") or ""
        media = item.get("media") or ""
        ref = item.get("refer") or ""
        icon = item.get("icon") or ""

        # Build the display line
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   URL: {url}")
        if snippet:
            # Truncate very long snippets
            display_snippet = snippet[:500] + "..." if len(snippet) > 500 else snippet
            lines.append(f"   {display_snippet}")
        if source:
            lines.append(f"   Source: {source}")
        if media:
            lines.append(f"   Media: {media}")
        lines.append("")

    if not results:
        lines.append("No results found. Try broadening your query or removing filters.")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Search the web via ZhipuAI Web Search API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "latest AI news"
  %(prog)s "Python tutorial" --count 5
  %(prog)s "breaking news" --recency oneDay
  %(prog)s "React guide" --domain react.dev
  %(prog)s "query" --raw

Recency options: noLimit (default), oneDay, oneWeek, oneMonth, oneYear
        """,
    )
    parser.add_argument("query", help="Search query string")
    parser.add_argument("--count", "-n", type=int, default=10, help="Number of results (default: 10, max: 50)")
    parser.add_argument("--recency", "-r", default="noLimit", choices=VALID_RECENCY, help="Recency filter (default: noLimit)")
    parser.add_argument("--domain", "-d", default="", help="Restrict results to this domain (e.g. 'github.com')")
    parser.add_argument("--intent", "-i", action="store_true", help="Enable search intent analysis")
    parser.add_argument("--raw", action="store_true", help="Output raw JSON response")
    parser.add_argument("--request-id", default="", help="Custom request ID for tracking")
    parser.add_argument("--user-id", default="", help="User ID for tracking")

    args = parser.parse_args()

    # Clamp count
    count = max(1, min(50, args.count))

    data = search(
        query=args.query,
        count=count,
        recency=args.recency,
        domain=args.domain,
        search_intent=args.intent,
        request_id=args.request_id,
        user_id=args.user_id,
    )

    if args.raw:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_results(args.query, data))


if __name__ == "__main__":
    main()
