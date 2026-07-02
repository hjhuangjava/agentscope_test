#!/usr/bin/env python3
"""
Shuyixin (数宜信) Open API Query CLI

Query corporate business registration data from Shuyixin Open API.
Currently supports getFirmCommercialGeneral (企业工商综合信息专业版).

Usage:
    shuyixin_query.py "<keyword>" [--env sandbox|prod] [--service CODE]
                    [--json] [--request-no ID] [--keyword-only]

Environment:
    SHUYIXIN_APP_ID - 商户appId from Shuyixin platform
    SHUYIXIN_ENV    - default environment: sandbox or prod (configured default: sandbox)
"""

import argparse
import json
import os
import sys
import time
import uuid

try:
    import requests
except ImportError:
    print("Error: requests library not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)


GATEWAY_URLS = {
    "sandbox": "https://sandbox.shuyixin.cn/gateway",
    "prod": "https://openapi.shuyixin.cn/gateway",
}


def _load_env():
    """Load Shuyixin settings from .env.

    /opt/data/.env is the authoritative Shuyixin configuration for this
    profile. It intentionally overrides inherited shell variables so stale
    terminal exports do not route requests to the wrong gateway. Use the
    explicit --env flag for one-off overrides.
    """
    wanted = {"SHUYIXIN_APP_ID", "SHUYIXIN_ENV"}
    candidates = [
        "/opt/data/.env",
        os.path.expanduser("~/.hermes/.env"),
        os.path.join(os.path.expanduser("~"), ".env"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        key = k.strip()
                        if key in wanted:
                            os.environ[key] = v.strip()
            break


def get_app_id():
    #app_id = os.environ.get("SHUYIXIN_APP_ID", "")
    app_id = "5686a1ef4bd449e1b17a191cb77ab168"  # ← 临时硬编码，避免每次都要在 /opt/data/.env 里设置
    if not app_id:
        print("Error: SHUYIXIN_APP_ID is not set.", file=sys.stderr)
        print("Add it to /opt/data/.env: SHUYIXIN_APP_ID=your_app_id", file=sys.stderr)
        sys.exit(1)
    return app_id


def query(service, keyword, env="sandbox", request_no=None, extra_body=None):
    """Call a Shuyixin service. Returns parsed JSON response dict."""
    env = env if env in GATEWAY_URLS else "sandbox"
    url = GATEWAY_URLS[env]
    app_id = get_app_id()

    headers = {
        "appId": app_id,
        "service": service,
        "requestNo": request_no or uuid.uuid4().hex[:24],
        "timestamp": str(int(time.time() * 1000)),
        "Content-Type": "application/json",
    }

    body = {"keyword": keyword, "requestId": ""}
    if extra_body:
        body.update(extra_body)

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
    except requests.exceptions.ConnectionError as e:
        print("Connection error: " + str(e), file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Request timed out", file=sys.stderr)
        sys.exit(1)

    try:
        result = resp.json()
    except ValueError:
        print("Non-JSON response (HTTP " + str(resp.status_code) + "):", file=sys.stderr)
        print(resp.text[:500], file=sys.stderr)
        sys.exit(1)

    return result, resp.status_code, headers


# ---- Pretty-printing ----

SECTION_LABELS = [
    ("commercialRegInfo", "基础信息"),
    ("shareholderInfo", "股东信息"),
    ("keymanInfo", "主要人员"),
    ("firmBranchInfo", "分支机构"),
    ("investmentInfo", "对外投资"),
    ("equityPledgeInfo", "股权出质"),
    ("mortgageInfo", "动产抵押"),
    ("frozenInfo", "股权冻结"),
    ("doubleRandomCheck", "双随机抽查"),
    ("spotCheck", "抽查检查"),
    ("businessAlter", "变更记录"),
    ("admLicenInfo", "行政许可"),
    ("commercialAdmPenal", "行政处罚"),
    ("abnorOpeInfo", "经营异常"),
    ("simpleCancelInfo", "简易注销"),
    ("clearInfo", "清算信息"),
    ("seriousBreachTrust", "严重违法失信"),
]


def print_summary(data):
    """Print a concise human-readable summary of the query result."""
    if "commercialRegInfo" in data and data["commercialRegInfo"]:
        info = data["commercialRegInfo"]
        print("=" * 60)
        print("基础信息")
        print("=" * 60)
        fields = [
            ("firmName", "企业名称"),
            ("uscCode", "统一社会信用代码"),
            ("legalRep", "法定代表人"),
            ("estDate", "成立日期"),
            ("regCap", "注册资本"),
            ("recCap", "实缴资本"),
            ("regCapCur", "币种"),
            ("opeStatus", "经营状态"),
            ("firmType", "企业类型"),
            ("indEconName", "行业"),
            ("regAddress", "注册地址"),
            ("regAgency", "登记机关"),
            ("opeScope", "经营范围"),
        ]
        for key, label in fields:
            val = info.get(key)
            if val:
                line = label + ": " + str(val)
                print(line if len(line) <= 120 else line[:117] + "...")

    for key, label in SECTION_LABELS:
        if key == "commercialRegInfo":
            continue
        section = data.get(key)
        if not section:
            continue
        if isinstance(section, list):
            count = len(section)
            print("")
            print("-" * 60)
            print(label + " (" + str(count) + "条)")
            print("-" * 60)
            _print_section_list(key, section)
        elif isinstance(section, dict):
            print("")
            print("-" * 60)
            print(label)
            print("-" * 60)
            _print_dict_brief(section)


def _print_section_list(key, items):
    """Print a compact view of each item in a section list."""
    # Per-section field selection for concise display
    display = {
        "shareholderInfo": ["shaName", "holdRatio", "shaType", "cumulativeAmt"],
        "keymanInfo": ["admPrimName", "admPrimPosition"],
        "firmBranchInfo": ["brName", "brStatus", "brPrincipal", "brEstDate"],
        "investmentInfo": ["invName", "invRatio", "invAmt", "invRegStatus"],
        "equityPledgeInfo": ["pledgeNo", "pledgeStatus", "pledgorName", "pledgeeName", "pledgeAmt"],
        "businessAlter": ["altItem", "altDate"],
        "admLicenInfo": ["licenseContent", "licenseAgency", "licenseStartDate", "licenseEndDate"],
    }
    fields = display.get(key, None)
    for i, item in enumerate(items):
        if fields:
            parts = []
            for f in fields:
                v = item.get(f)
                if v:
                    parts.append(str(v))
            if parts:
                print("  " + str(i + 1) + ". " + " | ".join(parts))
        else:
            # Generic: show first few non-empty string fields
            parts = []
            for f, v in item.items():
                if v and isinstance(v, (str, int, float)) and len(parts) < 4:
                    parts.append(str(f) + "=" + str(v))
            if parts:
                print("  " + str(i + 1) + ". " + " ".join(parts))


def _print_dict_brief(d):
    for f, v in d.items():
        if v:
            print("  " + str(f) + ": " + str(v))


def main():
    _load_env()

    parser = argparse.ArgumentParser(description="Shuyixin Open API Query CLI")
    parser.add_argument("keyword", help="公司全称、统一社会信用代码、或注册号")
    parser.add_argument("--env", default=None,
                        choices=["sandbox", "prod"],
                        help="Environment (default: SHUYIXIN_ENV or sandbox)")
    parser.add_argument("--service", default="getFirmCommercialGeneral",
                        help="Service/interface code (default: getFirmCommercialGeneral)")
    parser.add_argument("--json", action="store_true",
                        help="Output full pretty-printed JSON")
    parser.add_argument("--request-no", default=None,
                        help="Custom requestNo (10-32 chars, auto-generated if omitted)")
    parser.add_argument("--keyword-only", action="store_true",
                        help="Only show the request keyword, do not call API (dry-run)")
    args = parser.parse_args()

    env = args.env or os.environ.get("SHUYIXIN_ENV", "sandbox")

    if args.keyword_only:
        print("keyword: " + args.keyword)
        print("env: " + env)
        print("service: " + args.service)
        return

    result, status, headers = query(
        args.service, args.keyword, env=env, request_no=args.request_no)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Check for error response
    if not result.get("success"):
        print("查询失败 (code=" + str(result.get("code", "?")) + "): "
              + result.get("message", "unknown"), file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    data = result.get("data") or {}
    if not data:
        print("查询成功但无数据 (code=" + str(result.get("code")) + "): "
              + result.get("message", ""), file=sys.stderr)
        sys.exit(0)

    print_summary(data)


if __name__ == "__main__":
    main()
