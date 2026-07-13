"""SSE 序列化工具：统一封装 workflow / agent 流式输出。"""

from __future__ import annotations

import json
from typing import Any, Dict


def sse_data(payload: Dict[str, Any]) -> str:
    """把 dict 转成 SSE `data:` 行。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def workflow_start(question: str) -> str:
    return sse_data({"type": "WORKFLOW_START", "question": question})


def workflow_done() -> str:
    return sse_data({"type": "WORKFLOW_DONE"})


def workflow_error(detail: str) -> str:
    return sse_data({"type": "ERROR", "detail": detail})


def workflow_msg(node: str, message: Dict[str, Any]) -> str:
    return sse_data({"type": "WORKFLOW_MSG", "node": node, "message": message})


def agent_event(event: Dict[str, Any]) -> str:
    """AgentScope AgentEvent 原样推送，供前端 appendEvent 使用。"""
    return sse_data(event)
