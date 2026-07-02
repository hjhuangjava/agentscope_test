---
name: tavily-web-search
description: "Search the web for current information using the Tavily API. Returns structured results with titles, URLs, content snippets, and optional synthesized answer. Supports general/news topics and basic/advanced search depth."
version: 1.0.0
author: AgentScope Test
license: MIT
platforms: [linux, macos, windows]
required_environment_variables:
  - name: TAVILY_API_KEY
    prompt: Enter your Tavily API key
    help: https://app.tavily.com/
prerequisites:
  commands: [python3]
metadata:
  tags: [web, search, tavily, research, information-retrieval]
  related_skills: [zhipu-web-search]
---

# Tavily Web Search

Search the web via the [Tavily API](https://tavily.com) (`api.tavily.com`). Returns structured results with titles, URLs, content snippets, and an optional synthesized answer. Requires `TAVILY_API_KEY`.

## When to Use

- 网络搜索：current events、news、recent developments
- 需要最新的事实/数据（超出训练数据）
- 验证说法、找来源、收集背景资料
- 任何"让我搜一下"的天然场景

## Don't Use For

- 学术论文搜索 → 用专门的 arxiv skill
- 已知 URL 的页面抓取 → 用 web_extract / browser_navigate
- 本地文件搜索 → 用 search_files / Grep / Glob

## Quick Reference

| Action | Command |
|--------|---------|
| 基本搜索 | `python3 scripts/tavily_search.py "your query"` |
| 限制条数 | `python3 scripts/tavily_search.py "query" --max-results 5` |
| 新闻主题 | `python3 scripts/tavily_search.py "query" --topic news` |
| 深度搜索 | `python3 scripts/tavily_search.py "query" --search-depth advanced` |
| 附带 AI 答案 | `python3 scripts/tavily_search.py "query" --include-answer` |
| 原始 JSON | `python3 scripts/tavily_search.py "query" --raw` |

## API Details

**Endpoint:** `POST https://api.tavily.com/search`

**Auth:** Body field `"api_key": "<TAVILY_API_KEY>"`（不是 header）

**Request Body:**

```json
{
  "api_key": "<TAVILY_API_KEY>",
  "query": "search terms",
  "max_results": 10,
  "search_depth": "basic",
  "topic": "general",
  "include_answer": false
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | required | The search query |
| `max_results` | integer | `10` | Number of results (max 20) |
| `search_depth` | string | `basic` | `basic`（快） or `advanced`（更深、更慢） |
| `topic` | string | `general` | `general` or `news` |
| `include_answer` | boolean | `false` | 是否返回一个综合答案 |

### Response

```json
{
  "query": "...",
  "answer": "...(only if include_answer=true)",
  "response_time": 1.23,
  "results": [
    {"title": "...", "url": "...", "content": "...", "score": 0.95}
  ]
}
```

## Using curl Directly

```bash
curl -s -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "'"$TAVILY_API_KEY"'",
    "query": "your search query",
    "max_results": 10,
    "search_depth": "basic",
    "topic": "general"
  }' | python3 -m json.tool
```

## Equivalent SDK Usage (Reference)

If `tavily-python` is installed (`pip install tavily-python`), the same call looks like:

```python
from tavily import TavilyClient

tavily_client = TavilyClient(api_key="tvly-YOUR_API_KEY")
response = tavily_client.search("Who is Leo Messi?")
print(response)
```

The bundled `scripts/tavily_search.py` uses **stdlib only** (urllib) to avoid adding
the SDK dependency; the request/response shape is identical.

## Helper Script

`scripts/tavily_search.py` handles authentication, request formatting, and output parsing automatically. Key behaviors:

- `_load_api_key()` reads `TAVILY_API_KEY` from env first, then walks candidate `.env`
  files in order: `$HERMES_HOME/.env` → `~/.hermes/.env` → `~/.env` → 脚本父目录 6 层内的 `.env`
- If neither is set, falls back to the `DEFAULT_API_KEY` constant at the top of the script
  (replace `"tvly-YOUR_API_KEY"` with your real key, or leave as-is and rely on env)

### Examples

```bash
# 基本搜索
python3 scripts/tavily_search.py "latest AI news 2025"

# 只看前 5 条
python3 scripts/tavily_search.py "Python async tutorial" --max-results 5

# 新闻类
python3 scripts/tavily_search.py "breaking tech news" --topic news

# 让 Tavily 综合一个答案
python3 scripts/tavily_search.py "what is GRPO" --include-answer

# 原始 JSON（便于管道处理）
python3 scripts/tavily_search.py "query" --raw
```

### Output Format

默认输出人类可读：

```
=== Search Results for "latest AI news 2025" (5 results) ===

1. [标题]
   https://example.com/...
   Snippet text...

2. ...
```

加 `--raw` 输出完整 JSON，便于程序化处理。

## Common Pitfalls

1. **未设置 `TAVILY_API_KEY`**：脚本会立刻退出并提示。优先放 `~/.env`，不要硬编码进脚本（除非临时调试）。
2. **`max_results` 上限 20**：超过会被 API 拒绝。
3. **`advanced` 深度更慢但更全**：基本搜索 ~1-2 秒，深度搜索可能 5+ 秒。
4. **`topic=news` 只返回近期新闻**：跟 `general` 的召回源不同，不适合通用查询。
5. **速率限制**：免费套餐请求量有限，429 错误时等待几秒再重试。

## Verification Checklist

- [ ] `TAVILY_API_KEY` 已设置（环境变量、`~/.env` 或脚本内 `DEFAULT_API_KEY`）
- [ ] 脚本能用 stdlib 运行（无第三方依赖）
- [ ] 搜索返回包含 title / url / content 的结构化结果
- [ ] `--topic news` 和 `--search-depth advanced` 工作正常
