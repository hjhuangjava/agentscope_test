"""
LangGraph + AgentScope workflow API.

Graph: validate_input -> enrich_context -> prepare_prompt -> agent_reply
- 3 普通节点：校验、补充上下文、构造 agent 输入
- 1 agent 节点：通过 Workspace Manager 调用 AgentScope Agent

参考：
- langgraphtest.py   : Dict[str, Any] state 传递
- messagetest.py     : UserMsg / SystemMsg / AssistantMsg
- workspacemanagertest.py : LocalWorkspaceManager + Agent.reply_stream

启动：
    uvicorn workflow_app:app --host 0.0.0.0 --port 8092 --reload

流式接口：
    POST /api/workflow/chat/stream
    {"question": "大海为什么是蓝色的？", "user_id": "u1", "session_id": "s1"}

同步接口（返回全部 messages）：
    POST /api/workflow/chat
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from agentscope.agent import Agent
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.credential import OpenAICredential
from agentscope.event import EventType
from agentscope.message import AssistantMsg, SystemMsg, UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import Toolkit
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

BASEDIR = Path(__file__).parent / ".workflow-api"
SKILL_PATHS = [
    str(Path(__file__).parent / "skills" / "tavily-web-search"),
]
VL_MODEL_URL = os.getenv("VL_MODEL_URL", "http://192.168.39.100:11806/v1")
VL_MODEL_NAME = os.getenv("VL_MODEL_NAME", "qwen3.6:35b")
VL_MODEL_TOKEN = os.getenv("VL_MODEL_TOKEN", "empty")

_workspace_manager: Optional[LocalWorkspaceManager] = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def message_to_dict(msg: Any, *, node: str = "", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """将 AgentScope Message 或事件片段转为前端可消费的 dict。"""
    payload: Dict[str, Any] = {
        "node": node,
        "timestamp": _utc_now(),
    }
    if extra:
        payload.update(extra)

    if isinstance(msg, UserMsg):
        payload.update({"role": "user", "name": msg.name, "content": msg.get_text_content(), "kind": "user"})
    elif isinstance(msg, SystemMsg):
        payload.update({"role": "system", "name": msg.name, "content": msg.get_text_content(), "kind": "system"})
    elif isinstance(msg, AssistantMsg):
        payload.update({"role": "assistant", "name": msg.name, "content": msg.get_text_content(), "kind": "assistant"})
    elif isinstance(msg, dict):
        payload.update(msg)
    else:
        payload.update({"role": "system", "name": "workflow", "content": str(msg), "kind": "raw"})
    return payload


def _emit(state: Dict[str, Any], msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """追加 message 并通过 LangGraph custom stream 推送给前端。"""
    messages = list(state.get("messages", []))
    messages.append(msg)
    writer = get_stream_writer()
    writer({"event": "message", "message": msg})
    return messages


def validate_input(state: Dict[str, Any]) -> Dict[str, Any]:
    question = (state.get("user_input") or "").strip()
    if not question:
        raise ValueError("user_input 不能为空")

    user_msg = message_to_dict(
        UserMsg(name=state.get("user_id", "user"), content=question),
        node="validate_input",
        extra={"step": "receive_question"},
    )
    messages = _emit(state, user_msg)
    return {
        "user_input": question,
        "normalized_query": question,
        "messages": messages,
    }


def enrich_context(state: Dict[str, Any]) -> Dict[str, Any]:
    context = {
        "user_id": state.get("user_id", "anonymous"),
        "session_id": state.get("session_id", "default"),
        "received_at": _utc_now(),
        "topic_hint": "general_qa",
    }
    system_msg = message_to_dict(
        SystemMsg(
            name="workflow",
            content=(
                f"会话上下文已就绪。"
                f" user_id={context['user_id']}, session_id={context['session_id']}"
            ),
        ),
        node="enrich_context",
        extra={"step": "context_ready", "context": context},
    )
    messages = _emit(state, system_msg)
    return {"context": context, "messages": messages}


def prepare_prompt(state: Dict[str, Any]) -> Dict[str, Any]:
    prepared_prompt = (
        f"用户问题：{state['normalized_query']}\n"
        f"请结合已有上下文，用中文给出清晰、可执行的回答。"
        f"如需检索，可使用 workspace 中已加载的 skill。"
    )
    system_msg = message_to_dict(
        SystemMsg(name="workflow", content=f"Agent 输入已构造。\n{prepared_prompt}"),
        node="prepare_prompt",
        extra={"step": "prompt_ready"},
    )
    messages = _emit(state, system_msg)
    return {"prepared_prompt": prepared_prompt, "messages": messages}


async def agent_reply(state: Dict[str, Any]) -> Dict[str, Any]:
    manager = state["_workspace_manager"]
    if manager is None:
        raise RuntimeError("Workspace manager 未初始化")

    workspace = await manager.create_workspace(
        user_id=state.get("user_id", "anonymous"),
        agent_id="workflow-agent",
        session_id=state.get("session_id", "default"),
    )

    messages = list(state.get("messages", []))
    writer = get_stream_writer()
    writer({"event": "node_start", "node": "agent_reply"})

    try:
        agent = Agent(
            name="workflow-agent",
            system_prompt=(
                "You are a helpful assistant. Answer in Chinese. "
                "If web search is needed, use available skills in the workspace."
            ),
            model=OpenAIChatModel(
                credential=OpenAICredential(api_key=VL_MODEL_TOKEN, base_url=VL_MODEL_URL),
                model=VL_MODEL_NAME,
                stream=True,
                client_kwargs={"timeout": 120},
            ),
            toolkit=Toolkit(
                tools=await workspace.list_tools(),
                skills_or_loaders=await workspace.list_skills(),
            ),
            offloader=workspace,
            state=AgentState(permission_context=PermissionContext(mode=PermissionMode.BYPASS)),
        )

        text_buffer: List[str] = []
        async for evt in agent.reply_stream(UserMsg(state.get("user_id", "user"), state["prepared_prompt"])):
            match evt.type:
                case EventType.TEXT_BLOCK_DELTA:
                    delta = getattr(evt, "delta", "")
                    text_buffer.append(delta)
                    msg = message_to_dict(
                        {"role": "assistant", "name": "workflow-agent", "content": delta, "kind": "text_delta"},
                        node="agent_reply",
                        extra={"step": "streaming"},
                    )
                    messages.append(msg)
                    writer({"event": "message", "message": msg})
                case EventType.TOOL_CALL_START:
                    msg = message_to_dict(
                        {
                            "role": "assistant",
                            "name": "workflow-agent",
                            "content": f"[tool_call] {evt.tool_call_name}",
                            "kind": "tool_call",
                            "tool_call_id": evt.tool_call_id,
                        },
                        node="agent_reply",
                        extra={"step": "tool_call_start"},
                    )
                    messages.append(msg)
                    writer({"event": "message", "message": msg})
                case EventType.TOOL_RESULT_END:
                    msg = message_to_dict(
                        {
                            "role": "tool",
                            "name": evt.tool_call_name,
                            "content": f"[tool_result] state={getattr(evt, 'state', None)}",
                            "kind": "tool_result",
                        },
                        node="agent_reply",
                        extra={"step": "tool_result_end"},
                    )
                    messages.append(msg)
                    writer({"event": "message", "message": msg})
                case EventType.REPLY_END:
                    final_msg = message_to_dict(
                        AssistantMsg(name="workflow-agent", content="".join(text_buffer)),
                        node="agent_reply",
                        extra={"step": "reply_end"},
                    )
                    messages.append(final_msg)
                    writer({"event": "message", "message": final_msg})
                case _:
                    pass

        final_answer = "".join(text_buffer).strip() or "（Agent 未返回文本）"
    finally:
        await manager.close(workspace.workspace_id)
        writer({"event": "node_end", "node": "agent_reply"})

    return {"final_answer": final_answer, "messages": messages}


def create_workflow_graph() -> CompiledStateGraph:
    builder = StateGraph(Dict[str, Any])
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


workflow_graph = create_workflow_graph()


class WorkflowRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    user_id: str = Field(default="anonymous")
    session_id: str = Field(default="default")


class WorkflowResponse(BaseModel):
    question: str
    final_answer: str
    messages: List[Dict[str, Any]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _workspace_manager
    BASEDIR.mkdir(parents=True, exist_ok=True)
    _workspace_manager = LocalWorkspaceManager(
        basedir=str(BASEDIR),
        skill_paths=SKILL_PATHS,
        ttl=3600.0,
    )
    yield
    if _workspace_manager is not None:
        await _workspace_manager.close_all()
    _workspace_manager = None


app = FastAPI(title="AgentScope Workflow API", lifespan=lifespan)


def _build_input_state(req: WorkflowRequest) -> Dict[str, Any]:
    if _workspace_manager is None:
        raise HTTPException(status_code=503, detail="Workspace manager 尚未就绪")
    return {
        "user_input": req.question.strip(),
        "user_id": req.user_id,
        "session_id": req.session_id,
        "messages": [],
        "_workspace_manager": _workspace_manager,
    }


@app.post("/api/workflow/chat", response_model=WorkflowResponse)
async def run_workflow(req: WorkflowRequest) -> WorkflowResponse:
    result = await workflow_graph.ainvoke(_build_input_state(req))
    return WorkflowResponse(
        question=req.question,
        final_answer=result.get("final_answer", ""),
        messages=result.get("messages", []),
    )


@app.post("/api/workflow/chat/stream")
async def run_workflow_stream(req: WorkflowRequest) -> StreamingResponse:
    input_state = _build_input_state(req)

    async def event_generator() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'event': 'workflow_start', 'question': req.question}, ensure_ascii=False)}\n\n"
        final_state = dict(input_state)
        try:
            async for chunk in workflow_graph.astream(
                input_state,
                stream_mode=["custom", "updates"],
            ):
                if isinstance(chunk, tuple):
                    mode, data = chunk
                else:
                    mode, data = "custom", chunk

                if mode == "custom":
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                elif mode == "updates":
                    for node_name, update in data.items():
                        final_state.update(update)
                        payload = {
                            "event": "node_update",
                            "node": node_name,
                            "keys": list(update.keys()),
                        }
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0)

            yield f"data: {json.dumps({'event': 'workflow_done', 'final_answer': final_state.get('final_answer', ''), 'message_count': len(final_state.get('messages', []))}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'event': 'error', 'detail': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("workflow_app:app", host="0.0.0.0", port=8092, reload=False)
