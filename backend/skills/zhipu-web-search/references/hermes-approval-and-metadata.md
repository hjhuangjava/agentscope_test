# Hermes approval and metadata notes for query skills

Use this when a Zhipu web search script works technically but Hermes still asks for approval, or when `skill_view` metadata looks inconsistent.

## Command approval vs skill readiness

- `skill_view` readiness checks skill metadata and required credentials such as `GLM_API_KEY`.
- Terminal/curl/API execution can still be gated by Hermes command approval policy.
- Approval config belongs in `$HERMES_HOME/config.yaml` (on this host `/opt/data/config.yaml`), not `auth.json`.
- Valid approval modes are:
  - `manual`: prompts for commands matching approval rules.
  - `smart`: auto-approves low-risk commands, denies dangerous commands, escalates uncertain cases.
  - `off`: disables approval prompts, equivalent to yolo except hard blacklists may still apply.

## Metadata mismatch pattern

If a skill declares:

```yaml
prerequisites:
  commands: [python3, curl]
```

but `skill_view` returns `required_commands: []`, inspect Hermes core before blaming the skill. In observed Hermes code, `tools/skills_tool.py` parsed `prerequisites.commands` via `_collect_prerequisite_values()` but the final response hard-coded:

```python
"required_commands": [],
"missing_required_commands": [],
```

The core fix is to collect the second return value from `_collect_prerequisite_values(frontmatter)`, check each command with `shutil.which()`, surface `required_commands` and `missing_required_commands`, and include missing commands in `setup_needed`.

## Verification pattern

To prove `.env` fallback works without leaking secrets, unset the shell env and summarize raw JSON instead of printing full credentials or headers:

```bash
HERMES_HOME=/opt/data env -u GLM_API_KEY \
python3 /opt/data/skills/research/zhipu-web-search/scripts/web_search.py \
"重庆 沙坪坝 人工智能" --count 1 --raw
```

Report only structure, result count, title/URL snippets, and whether the command exited successfully. Never print the API key.
