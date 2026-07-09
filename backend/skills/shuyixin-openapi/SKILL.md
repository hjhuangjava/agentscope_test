---
name: shuyixin-openapi
description: "Query corporate business registration data from Shuyixin (数宜信) Open API. Currently supports getFirmCommercialGeneral: comprehensive enterprise info including registration, shareholders, key personnel, branches, investments, equity pledges, mortgages, business changes, and more."
trigger: "When the user asks to query company/enterprise business registration info (工商信息), shareholder info (股东信息), or corporate data via Shuyixin/数宜信. Keywords: 数宜信, 工商查询, 企业信息, 股东信息, shuyixin, getFirmCommercialGeneral."
---

# Shuyixin Open API

Query corporate business registration data from Shuyixin (数宜信) Open API platform. The gateway accepts a single endpoint with `service` in the header to route to specific data interfaces.

## Supported Interfaces

| Service Code | Description | Mode |
|---|---|---|
| `getFirmCommercialGeneral` | 企业工商综合信息(专业版) — registration, shareholders, key personnel, branches, investments, equity pledges, mortgages, business changes, licenses, etc. | Sync |

## IMPORTANT: Must use venv Python

System python3 does NOT have `requests`. Always run with:

```
/opt/hermes/.venv/bin/python /opt/data/skills/research/shuyixin-openapi/scripts/shuyixin_query.py ...
```

## CLI Script

```bash
V=/opt/hermes/.venv/bin/python
S=/opt/data/skills/research/shuyixin-openapi/scripts/shuyixin_query.py

# Query a company by name or USCC code (生产环境, default)
$V $S "重庆正大软件（集团）有限公司"

# Explicitly use production environment
#$V $S "915000002028187597" --env prod

# Sandbox for testing
$V $S "915000002028187597" --env sandbox

# Specify a different service (interface)
$V $S "公司名称" --service getFirmCommercialGeneral

# Pretty-print full JSON response
$V $S "公司名称" --json

# Curl-only tester for debugging production gateway/appId issues
bash /opt/data/skills/research/shuyixin-openapi/scripts/shuyixin_curl.sh "公司名称" --verbose

# Hermes API-server/gateway smoke test: ask the agent to invoke this skill
curl http://localhost:8642/v1/chat/completions \
  -H "Authorization: Bearer change-me-local-dev" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"调用数宜信 skill 查询 腾讯科技（深圳）有限公司 的企业工商信息"}],"stream":true}'

# Custom requestNo (defaults to a random unique string)
$V $S "公司名称" --request-no "MY-REQ-001"
```

The keyword can be: 公司全称、统一社会信用代码、注册号.

## API Details

**Endpoint** (all interfaces share one URL):
- Sandbox: `https://sandbox.shuyixin.cn/gateway`
- Production: `https://openapi.shuyixin.cn/gateway`

**Method:** `POST application/json`

**Headers (公共参数):**
| Header | Required | Description |
|---|---|---|
| appId | Yes | 商户appId, assigned by Shuyixin platform |
| service | Yes | 接口编码, e.g. getFirmCommercialGeneral |
| requestNo | Yes | 请求流水号, 10-32 chars |
| timestamp | Yes | 毫秒级时间戳 (integer) |
| sign | No | 参数签名 — currently not enforced in sandbox |

**Request body** for getFirmCommercialGeneral:
```json
{"keyword": "公司全称或统一社会信用代码", "requestId": ""}
```

**Response body:**
```json
{"success": true, "code": "0000", "message": "查询成功", "data": {...}}
```

**Response codes:** 0000 成功 / 0001 无数据 / 1001 业务异常 / 1002 参数错误 / 1020 系统异常 / 9998 搜索词太宽泛 / 9999 系统异常

## Response Data Sections (getFirmCommercialGeneral)

`data` object contains these sections (arrays unless noted):

| Field | Description |
|---|---|
| commercialRegInfo | 基础信息 (object) — name, USCC, legalRep, regCap, opeScope, etc. |
| shareholderInfo | 股东信息 |
| keymanInfo | 主要人员 |
| firmBranchInfo | 分支机构 |
| investmentInfo | 对外投资 |
| equityPledgeInfo | 股权出质 |
| mortgageInfo | 动产抵押 |
| frozenInfo | 股权冻结 |
| doubleRandomCheck | 双随机抽查 |
| spotCheck | 抽查检查 |
| businessAlter | 变更记录 |
| admLicenInfo | 行政许可 |
| commercialAdmPenal | 行政处罚 |
| abnorOpeInfo | 经营异常 |
| simpleCancelInfo | 简易注销 |
| clearInfo | 清算信息 |
| seriousBreachTrust | 严重违法失信 |

## Environment Variables

All in `/opt/data/.env`:

| Variable | Description | Required |
|---|---|---|
| SHUYIXIN_APP_ID | 商户appId | Yes |
| SHUYIXIN_ENV | Default environment: sandbox or prod (default: prod) | No |

## Pitfalls

- **Production is the default**: `/opt/data/.env` is authoritative with `SHUYIXIN_ENV=prod` → `https://openapi.shuyixin.cn/gateway`. The script reloads `.env` to avoid stale inherited shell variables routing queries to the wrong environment. Sandbox testing uses `--env sandbox` → `https://sandbox.shuyixin.cn/gateway`.
- **Production `code=1001 未查询到商户信息` diagnosis**: Gateway auth passes (appId is valid) but no data returns. Two likely causes: (a) production appId has not been authorized for data access by Shuyixin platform — confirm with Shuyixin; (b) production requires `sign` header (SM2/RSA) which the script does not implement yet. Sandbox does not enforce signing.
- **No signature in sandbox**: Sandbox config does not enforce the `sign` header. Production may require it — if confirmed, signature logic must be added (SM2/RSA). The script has a `--sign` option reserved for this but does not implement signing yet.
- **Must use venv python**: System python3 lacks `requests`.
- **timestamp must be integer milliseconds**: Not a float, not seconds. The script auto-generates this correctly.
- **requestNo must be 10-32 chars**: The script auto-generates a unique ID if not provided.
- **Keyword accepts company name OR USCC code OR registration number**: Use whichever you have; USCC (统一社会信用代码) gives the most precise match.
- **Response can be large**: getFirmCommercialGeneral for an active company returns a big JSON (50KB+). Use `--json` to pretty-print or pipe to a file.

## References

- `references/fields.md` — Full field reference for getFirmCommercialGeneral response sections
- `scripts/shuyixin_curl.sh` — curl-only tester equivalent to the Python script, useful for isolating gateway/appId/signature issues
