"""
本地 stdio 天气 MCP server。

依赖：
- mcp >= 1.28（FastMCP）
- Python 标准库 urllib（无需 httpx）

工具：
- get_weather(city: str) -> str  返回指定城市的当前天气
- list_supported_cities(prefix: str = "") -> str  演示用，列出匹配的城市

数据源：Open-Meteo（免费、免 key、无需鉴权）。

启动方式（被 agentscope 通过 StdioMCPConfig 拉起）：
    python weather_mcp_server.py
"""

import json
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP


GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather Code -> 人类可读描述（Open-Meteo 用的就是这套）
WMO_CODE = {
    0: "晴",
    1: "晴间多云",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "毛毛雨（轻度）",
    53: "毛毛雨（中度）",
    55: "毛毛雨（密集）",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨（轻度）",
    67: "冻雨（强烈）",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "米雪",
    80: "阵雨（轻度）",
    81: "阵雨（中度）",
    82: "阵雨（强烈）",
    85: "阵雪（轻度）",
    86: "阵雪（强烈）",
    95: "雷阵雨",
    96: "雷阵雨伴冰雹（轻度）",
    99: "雷阵雨伴冰雹（强烈）",
}


def _http_get_json(url: str, params: dict[str, Any], timeout: float = 8.0) -> Any:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _geocode(city: str) -> dict[str, Any]:
    """城市名 -> 经纬度等元信息。"""
    data = _http_get_json(GEO_URL, {"name": city, "count": 1, "language": "zh"})
    results = data.get("results") or []
    if not results:
        raise ValueError(f"找不到城市: {city!r}")
    return results[0]


def _fetch_weather(lat: float, lon: float) -> dict[str, Any]:
    data = _http_get_json(
        FORECAST_URL,
        {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "timezone": "Asia/Shanghai",
        },
    )
    return data["current_weather"]


mcp = FastMCP(name="weather-mcp")


@mcp.tool()
def get_weather(city: str) -> str:
    """查询指定城市的当前天气。

    Args:
        city: 城市名（支持中英文，例如 "重庆"、"Chongqing"、"Beijing"）

    Returns:
        人类可读的天气描述字符串，包含温度、风速、天气状况等。
    """
    try:
        geo = _geocode(city)
        w = _fetch_weather(geo["latitude"], geo["longitude"])
    except Exception as e:
        return f"查询 {city} 天气失败: {type(e).__name__}: {e}"

    code = w.get("weathercode")
    desc = WMO_CODE.get(code, f"未知代码 {code}")
    return (
        f"{geo.get('name', city)}（{geo.get('country', '')} {geo.get('admin1', '')}）"
        f" 当前天气：\n"
        f"  - 温度：{w.get('temperature')}°C\n"
        f"  - 风速：{w.get('windspeed')} km/h\n"
        f"  - 风向：{w.get('winddirection')}°\n"
        f"  - 状况：{desc}\n"
        f"  - 时间：{w.get('time')}（{geo.get('timezone', '')}）"
    )


@mcp.tool()
def list_supported_cities(prefix: str = "") -> str:
    """演示用：列出 Open-Meteo 支持的、名称以 prefix 开头的城市（最多 10 个）。

    Args:
        prefix: 城市名前缀，默认空（任意）
    """
    data = _http_get_json(GEO_URL, {"name": prefix or "a", "count": 10, "language": "zh"})
    results = data.get("results") or []
    if not results:
        return f"没有匹配 '{prefix}' 的城市"
    lines = [f"  - {r['name']}（{r.get('admin1', '')}, {r.get('country', '')}）" for r in results]
    return "匹配城市：\n" + "\n".join(lines)


if __name__ == "__main__":
    # stdio 模式：被 MCP client（如 agentscope）通过 stdin/stdout 调用
    mcp.run(transport="stdio")
