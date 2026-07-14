"""LangGraph workflow：编排预处理 + 用 AgentScope model 生成回答。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict

from agentscope.message import Msg, SystemMsg, UserMsg
from agentscope.model import ChatModelBase
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.config import get_config


class LangGraphBridgeState(TypedDict, total=False):
    user_input: str
    normalized_query: str
    context_note: str
    prepared_prompt: str
    final_answer: str
    node_logs: List[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_log(state: Dict[str, Any], line: str) -> List[str]:
    logs = list(state.get("node_logs", []))
    logs.append(line)
    return logs


def validate_input(state: Dict[str, Any]) -> Dict[str, Any]:
    question = (state.get("user_input") or "").strip()
    if not question:
        raise ValueError("user_input 不能为空")
    return {
        "normalized_query": question,
        "node_logs": _append_log(state, f"[validate_input] ok, len={len(question)}"),
    }


def enrich_context(state: Dict[str, Any]) -> Dict[str, Any]:
    note = f"session context ready at {_utc_now()}"
    return {
        "context_note": note,
        "node_logs": _append_log(state, f"[enrich_context] {note}"),
    }


def prepare_prompt(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state.get("normalized_query") or state.get("user_input", "")
    note = state.get("context_note", "")
    prepared = (
        f"用户问题：{query}\n"
        f"补充信息：{note}\n"
        f"请用中文给出清晰、简洁的回答。"
    )
    return {
        "prepared_prompt": prepared,
        "node_logs": _append_log(state, "[prepare_prompt] AgentScope model 输入已构造"),
    }


async def generate_answer(state: Dict[str, Any]) -> Dict[str, Any]:
    """调用挂在 runnable config 上的 AgentScope ChatModel。"""
    config = get_config() or {}
    configurable = config.get("configurable", {})
    model: ChatModelBase = configurable["agentscope_model"]
    system_prompt: str = configurable.get(
        "system_prompt",
        "You are a helpful assistant. Answer clearly in Chinese.",
    )

    messages: list[Msg] = [
        SystemMsg(name="system", content=system_prompt),
        UserMsg(name="user", content=state["prepared_prompt"]),
    ]

    from agentscope.model import ChatResponse

    response = await model(messages)
    if isinstance(response, ChatResponse):
        answer = "".join(
            block.text
            for block in response.content or []
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ).strip()
    else:
        # stream=True：AsyncGenerator[ChatResponse]
        text_parts: list[str] = []
        async for chunk in response:
            text = "".join(
                block.text
                for block in getattr(chunk, "content", []) or []
                if getattr(block, "type", None) == "text" and getattr(block, "text", None)
            )
            if text:
                text_parts.append(text)
        answer = "".join(text_parts).strip()

    if not answer:
        answer = "（模型未返回文本）"

    return {
        "final_answer": answer,
        "node_logs": _append_log(state, f"[generate_answer] chars={len(answer)}"),
    }


def create_langgraph_workflow() -> CompiledStateGraph:
    builder = StateGraph(LangGraphBridgeState)
    builder.add_node("validate_input", validate_input)
    builder.add_node("enrich_context", enrich_context)
    builder.add_node("prepare_prompt", prepare_prompt)
    builder.add_node("generate_answer", generate_answer)
    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "enrich_context")
    builder.add_edge("enrich_context", "prepare_prompt")
    builder.add_edge("prepare_prompt", "generate_answer")
    builder.add_edge("generate_answer", END)
    return builder.compile()
