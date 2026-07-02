#!/usr/bin/env bash
set -euo pipefail

# Shuyixin (数宜信) OpenAPI curl tester
# 默认调用生产环境：getFirmCommercialGeneral 企业工商综合信息（专业版）
#
# Usage:
#   bash /opt/data/skills/research/shuyixin-openapi/scripts/shuyixin_curl.sh "腾讯科技（深圳）有限公司"
#   bash /opt/data/skills/research/shuyixin-openapi/scripts/shuyixin_curl.sh "915000002028187597" --verbose
#   SHUYIXIN_APP_ID=xxx bash shuyixin_curl.sh "公司名称"
#
# Env:
#   SHUYIXIN_APP_ID  商户 appId。默认按以下顺序从 .env 读取：
#                    /opt/data/.env → ~/.hermes/.env → ~/.env
#                    （与 shuyixin_query.py 保持一致）
#   SHUYIXIN_ENV     prod 或 sandbox，默认 prod。
#   SHUYIXIN_SERVICE 接口编码，默认 getFirmCommercialGeneral。

KEYWORD="${1:-}"
if [[ -z "$KEYWORD" || "$KEYWORD" == "-h" || "$KEYWORD" == "--help" ]]; then
  sed -n '1,24p' "$0"
  exit 0
fi
shift || true

VERBOSE=0
if [[ "${1:-}" == "--verbose" || "${1:-}" == "-v" ]]; then
  VERBOSE=1
fi

ENV_FILE=""
for candidate in "/opt/data/.env" "$HOME/.hermes/.env" "$HOME/.env"; do
  if [[ -f "$candidate" ]]; then
    ENV_FILE="$candidate"
    break
  fi
done
if [[ -n "$ENV_FILE" ]]; then
  # 只读取数宜信相关变量，不 source 整个 .env，避免执行/污染其他变量。
  while IFS='=' read -r key value; do
    [[ -z "${key:-}" || "$key" =~ ^[[:space:]]*# ]] && continue
    key="$(printf '%s' "$key" | xargs)"
    value="$(printf '%s' "${value:-}" | sed -e 's/^\s*//' -e 's/\s*$//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
    case "$key" in
      SHUYIXIN_APP_ID) export SHUYIXIN_APP_ID="$value" ;;
      SHUYIXIN_ENV) export SHUYIXIN_ENV="$value" ;;
    esac
  done < "$ENV_FILE"
fi

APP_ID="${SHUYIXIN_APP_ID:-}"
ENV_NAME="${SHUYIXIN_ENV:-sandbox}"
SERVICE="${SHUYIXIN_SERVICE:-getFirmCommercialGeneral}"

if [[ -z "$APP_ID" ]]; then
  echo "Error: SHUYIXIN_APP_ID is empty. Set it in ~/.env (or /opt/data/.env) or env." >&2
  exit 1
fi

case "$ENV_NAME" in
  prod|production) URL="https://openapi.shuyixin.cn/gateway" ;;
  sandbox) URL="https://sandbox.shuyixin.cn/gateway" ;;
  *) echo "Error: SHUYIXIN_ENV must be prod or sandbox, got: $ENV_NAME" >&2; exit 1 ;;
esac

REQUEST_NO="SYX$(date +%Y%m%d%H%M%S)$((RANDOM % 10000))"
# requestNo 要求 10-32 字符；上面通常 21 位。
TIMESTAMP="$(date +%s%3N)"
BODY=$(python3 - "$KEYWORD" <<'PY'
import json, sys
keyword = sys.argv[1]
print(json.dumps({"keyword": keyword, "requestId": ""}, ensure_ascii=False))
PY
)

if [[ "$VERBOSE" == "1" ]]; then
  echo "URL: $URL" >&2
  echo "service: $SERVICE" >&2
  echo "requestNo: $REQUEST_NO" >&2
  echo "timestamp: $TIMESTAMP" >&2
  echo "appId: ${APP_ID:0:6}...${APP_ID: -4}" >&2
  echo "body: $BODY" >&2
fi

curl --silent --show-error --location \
  --request POST "$URL" \
  --header "Content-Type: application/json" \
  --header "appId: $APP_ID" \
  --header "service: $SERVICE" \
  --header "requestNo: $REQUEST_NO" \
  --header "timestamp: $TIMESTAMP" \
  --data-raw "$BODY"

echo
