---
name: zhipu-web-search
description: "Use when you need to search the web for current information, facts, news, or any topic requiring up-to-date data. Performs web search via ZhipuAI (智谱) Web Search API and returns structured results with titles, URLs, snippets, and source attribution."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
required_environment_variables:
  - name: GLM_API_KEY
    prompt: Enter your ZhipuAI/GLM API key
    help: https://open.bigmodel.cn/
prerequisites:
  commands: [python3, curl]
metadata:
  hermes:
    tags: [web, search, zhipu, glm, research, information-retrieval]
    related_skills: [arxiv, blogwatcher]
---

# ZhipuAI Web Search

Search the web via the ZhipuAI (智谱) Web Search API (`open.bigmodel.cn`). Returns structured results with titles, URLs, content snippets, and source domains. Requires `GLM_API_KEY` environment variable.

## When to Use

- User asks about current events, news, or recent developments
- You need up-to-date factual information beyond your training data
- Verifying claims, finding sources, or gathering context on a topic
- Research tasks that require web data
- Any question where "let me search for that" is the natural response

## Don't Use For

- Academic paper search → use `arxiv` skill
- Blog/RSS monitoring → use `blogwatcher` skill
- Accessing a known URL → use `web_extract` or `browser_navigate`
- Local file search → use `search_files`

## Quick Reference

| Action | Command |
|--------|---------|
| Basic search | `python3 scripts/web_search.py "your query"` |
| Limit results | `python3 scripts/web_search.py "query" --count 5` |
| Recent only | `python3 scripts/web_search.py "query" --recency oneDay` |
| Domain filter | `python3 scripts/web_search.py "query" --domain "zhihu.com"` |
| Raw JSON | `python3 scripts/web_search.py "query" --raw` |

## API Details

**Endpoint:** `POST https://open.bigmodel.cn/api/paas/v4/web_search`

**Auth:** `Authorization: Bearer <GLM_API_KEY>`

**Request Body:**

```json
{
  "search_query": "search terms",
  "search_engine": "search_std",
  "search_intent": false,
  "count": 10,
  "search_domain_filter": "",
  "search_recency_filter": "noLimit",
  "request_id": "",
  "user_id": ""
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search_query` | string | required | The search query string |
| `search_engine` | string | `search_std` | Search engine to use: `search_std` (standard) |
| `search_intent` | boolean | `false` | Whether to analyze search intent |
| `count` | integer | `10` | Number of results to return (max 50) |
| `search_domain_filter` | string | `""` | Restrict results to this domain (e.g. `"github.com"`) |
| `search_recency_filter` | string | `noLimit` | Time filter: `noLimit`, `oneDay`, `oneWeek`, `oneMonth`, `oneYear` |
| `request_id` | string | `""` | Optional request ID for tracking |
| `user_id` | string | `""` | Optional user ID for tracking |

### Recency Filter Values

| Value | Meaning |
|-------|---------|
| `noLimit` | No time restriction (default) |
| `oneDay` | Last 24 hours |
| `oneWeek` | Last 7 days |
| `oneMonth` | Last 30 days |
| `oneYear` | Last 12 months |

## Using curl Directly

For one-off searches where the script isn't available:

```bash
curl -s --request POST \
  --url https://open.bigmodel.cn/api/paas/v4/web_search \
  --header "Authorization: Bearer $GLM_API_KEY" \
  --header "Content-Type: application/json" \
  --data '{
    "search_query": "your search query",
    "search_engine": "search_std",
    "search_intent": false,
    "count": 10,
    "search_recency_filter": "noLimit"
  }' | python3 -m json.tool
```

## Helper Script

The `scripts/web_search.py` script handles authentication, request formatting, and output parsing automatically.

### Examples

```bash
# Basic search
python3 scripts/web_search.py "latest AI news 2025"

# Fewer results
python3 scripts/web_search.py "Python async tutorial" --count 5

# Recent news only (last 24 hours)
python3 scripts/web_search.py "breaking tech news" --recency oneDay

# Restrict to specific domain
python3 scripts/web_search.py "React hooks guide" --domain "react.dev"

# Get raw JSON output (for piping/processing)
python3 scripts/web_search.py "query" --raw
```

### Output Format

Default output is human-readable:

```
=== Search Results for "latest AI news 2025" (5 results) ===

1. [标题] URL
   Snippet text...
   Source: example.com

2. ...
```

With `--raw`, full JSON response is printed for programmatic processing.

## Integration with Other Tools

Combine web search with other Hermes tools for powerful workflows:

1. **Search → Read**: Search for a topic, then use `web_extract` to read full content from promising URLs
2. **Search → Summarize**: Search, extract key pages, then synthesize findings
3. **Search → Compare**: Run multiple searches with different queries, compare results
4. **Search → Cite**: Use search results as citations with source URLs

### Example Workflow

```
1. python3 scripts/web_search.py "GRPO reinforcement learning" --count 5
2. Pick the most relevant URL from results
3. web_extract(urls=["https://..."]) to read full content
4. Summarize and cite the source
```

## Common Pitfalls

1. **Missing GLM_API_KEY / gateway readiness mismatch**: The skill must declare `GLM_API_KEY` in frontmatter (`required_environment_variables`) so gateway/API-server loads do not mark it available without credentials. The helper script should first read `os.getenv("GLM_API_KEY")`, then try Hermes/profile `.env` locations such as `$HERMES_HOME/.env`, `~/.hermes/.env`, and parent `.env` files. Avoid hard-coding one deployment path like `/opt/data/.env` unless documenting this specific host.

2. **Never rewrite `.env` using `os.environ.get()` values**: If you need to modify `.env`, always read the existing file first and merge changes. The shell session may not have env vars exported, so `os.environ.get("GLM_API_KEY")` returns empty and overwrites the real key with garbage.

3. **Empty results**: The API may return empty results for very specific or non-English queries. Try broadening the query or switching `search_intent` to `true` to let the engine interpret intent.

4. **Rate limiting**: The ZhipuAI API has rate limits. If you get 429 errors, wait a few seconds and retry. Avoid sending many requests in rapid succession.

5. **Domain filter is exact**: `search_domain_filter` matches the domain exactly. `"github.com"` matches `github.com` but not `gist.github.com`. For subdomains, specify them explicitly.

6. **Recency filter may reduce results**: Using `oneDay` or `oneWeek` can significantly reduce the number of results. If you get too few, fall back to `noLimit` or `oneYear`.

7. **Chinese content bias**: The API tends to return more Chinese-language results for Chinese queries and English for English queries. Use the language that matches your desired result set.

## Gateway / API-Server Metadata Audit

When this skill is used through Hermes gateway or API server, check both the document and loader-facing metadata:

- `required_environment_variables` includes `GLM_API_KEY` so Hermes can mark setup-needed before runtime.
- `prerequisites.commands` lists command-line tools used by examples/scripts, e.g. `python3` and `curl`.
- Helper scripts can run with only Hermes `.env` configured; do not require a shell `export` in gateway contexts.
- If `skill_view` still returns `required_commands: []`, verify whether the current Hermes loader surfaces command prerequisites; do not assume the skill frontmatter is absent without checking SKILL.md.
- If command/API execution is blocked by Hermes approvals, distinguish skill readiness from command approval policy. The skill may be correctly configured while `approvals.mode: manual` still prompts for shell/API actions; `approvals.mode: smart` or `off` lives in `$HERMES_HOME/config.yaml`, not `auth.json`.

## Verification Checklist

- [ ] `skill_view("zhipu-web-search")` shows `required_environment_variables` containing `GLM_API_KEY`
- [ ] `GLM_API_KEY` is set in environment or a Hermes/profile `.env`
- [ ] Helper script runs without import errors (uses only stdlib)
- [ ] Script works when `GLM_API_KEY` is not exported but exists in `$HERMES_HOME/.env`
- [ ] Search returns results with titles, URLs, and snippets
- [ ] Recency and domain filters work as expected
