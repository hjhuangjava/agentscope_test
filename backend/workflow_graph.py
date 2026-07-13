"""LangGraph workflow：3 个普通节点 + 1 个 agent 节点。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict

from agentscope.agent import Agent
from agentscope.event import ReplyStartEvent
from agentscope.message import AssistantMsg, Msg, SystemMsg, UserMsg
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph


class WorkflowState(TypedDict, total=False):
    """LangGraph 状态：每个字段独立 channel，节点可只返回部分更新。"""

    user_input: str
    user_id: str
    session_id: str
    normalized_query: str
    context: Dict[str, Any]
    prepared_prompt: str
    messages: List[Any]
    final_answer: str
    assistant_msg: Dict[str, Any]
    _agent: Agent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_message(state: Dict[str, Any], msg: Msg) -> List[Msg]:
    messages = list(state.get("messages", []))
    messages.append(msg)
    return messages


def _emit_workflow_msg(node: str, msg: Msg) -> None:
    writer = get_stream_writer()
    writer(
        {
            "type": "WORKFLOW_MSG",
            "node": node,
            "message": msg.model_dump(mode="json"),
        }
    )


def validate_input(state: Dict[str, Any]) -> Dict[str, Any]:
    question = (state.get("user_input") or "").strip()
    if not question:
        raise ValueError("user_input 不能为空")

    user_msg = UserMsg(name=state.get("user_id", "user"), content=question)
    _emit_workflow_msg("validate_input", user_msg)

    system_msg = SystemMsg(
        name="workflow",
        content=f"[validate_input] 输入校验通过，问题长度={len(question)}",
    )
    _emit_workflow_msg("validate_input", system_msg)

    state_after_user = {**state, "messages": _append_message(state, user_msg)}
    return {
        "user_input": question,
        "normalized_query": question,
        "messages": _append_message(state_after_user, system_msg),
    }


def enrich_context(state: Dict[str, Any]) -> Dict[str, Any]:
    context = {
        "user_id": state.get("user_id", "anonymous"),
        "session_id": state.get("session_id", "default"),
        "received_at": _utc_now(),
        "topic_hint": "general_qa",
    }
    system_msg = SystemMsg(
        name="workflow",
        content=(
            f"[enrich_context] 上下文已就绪。"
            f" user_id={context['user_id']}, session_id={context['session_id']}"
        ),
    )
    _emit_workflow_msg("enrich_context", system_msg)
    return {
        "context": context,
        "messages": _append_message(state, system_msg),
    }


def prepare_prompt(state: Dict[str, Any]) -> Dict[str, Any]:
    query = state.get("normalized_query") or state.get("user_input", "")
    prepared_prompt = (
        f"用户问题：{query}\n"
        f"请结合已有上下文，用中文给出清晰、可执行的回答。"
    )
    system_msg = SystemMsg(
        name="workflow",
        content=f"[prepare_prompt] Agent 输入已构造。\n{prepared_prompt}",
    )
    _emit_workflow_msg("prepare_prompt", system_msg)
    return {
        "prepared_prompt": prepared_prompt,
        "messages": _append_message(state, system_msg),
    }


async def agent_reply(state: Dict[str, Any]) -> Dict[str, Any]:
    agent: Agent = state["_agent"]
    writer = get_stream_writer()

    start_msg = SystemMsg(name="workflow", content="[agent_reply] 开始调用 Agent.reply_stream")
    _emit_workflow_msg("agent_reply", start_msg)
    messages = _append_message(state, start_msg)

    msg: Msg | None = None
    async for event in agent.reply_stream(
        UserMsg(name=state.get("user_id", "user"), content=state["prepared_prompt"])
    ):
        if isinstance(event, ReplyStartEvent):
            msg = AssistantMsg(name=event.name, content=[], id=event.reply_id)
        elif msg is not None:
            msg.append_event(event)

        writer(event.model_dump(mode="json"))

    if msg is None:
        msg = AssistantMsg(name="workflow-agent", content="（Agent 未返回内容）")

    end_msg = SystemMsg(
        name="workflow",
        content=f"[agent_reply] 完成，answer_chars={len(msg.get_text_content() or '')}",
    )
    _emit_workflow_msg("agent_reply", end_msg)

    return {
        "final_answer": (msg.get_text_content() or "").strip(),
        "assistant_msg": msg.model_dump(mode="json"),
        "messages": _append_message({**state, "messages": messages}, end_msg),
    }


def create_workflow_graph() -> CompiledStateGraph:
    builder = StateGraph(WorkflowState)
    builder.add_node("validate_input", validate_input)
    builder.add_node("enrich_context", enrich_context)
    builder.add_node("prepare_prompt", prepare_prompt)
    builder.add_node("agent_reply", agent_reply)
    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "enrich_context")
    builder.add_edge("enrich_context", "prepare_prompt")
    builder.add_edge("prepare_prompt", "agent_reply")
    builder.add_edge("agent_reply", END)
    return builder.compile()
