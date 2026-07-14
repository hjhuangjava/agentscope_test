"""
可直接跑的桥接 Demo（无需 Redis / create_app）。

通过 LangGraphAgent.reply_stream 产出标准 AgentEvent，再用 FastAPI SSE 推送。
前端仍用 AssistantMsg + appendEvent 重建消息。

启动：
    python langgraph_bridge_demo.py

测试：
    POST /api/langgraph-agent/stream
    {"question": "大海为什么是蓝色的？"}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import AsyncIterator, Dict, Optional

from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from langgraph_agent import LangGraphAgent
from langgraph_workflow import create_langgraph_workflow

WORKDIR = Path(__file__).parent / ".langgraph-bridge-workspace"
VL_MODEL_URL = os.getenv("VL_MODEL_URL", "http://192.168.39.100:11806/v1")
VL_MODEL_NAME = os.getenv("VL_MODEL_NAME", "qwen3.6:35b")
VL_MODEL_TOKEN = os.getenv("VL_MODEL_TOKEN", "empty")

_agent: Optional[LangGraphAgent] = None
_workspace: Optional[LocalWorkspace] = None
_GRAPH = create_langgraph_workflow()


async def get_agent() -> LangGraphAgent:
    global _agent, _workspace
    if _agent is not None:
        return _agent

    WORKDIR.mkdir(parents=True, exist_ok=True)
    _workspace = LocalWorkspace(workdir=str(WORKDIR))
    await _workspace.initialize()

    _agent = LangGraphAgent(
        name="langgraph-bridge-agent",
        system_prompt="You are a helpful assistant. Answer clearly in Chinese.",
        model=OpenAIChatModel(
            credential=OpenAICredential(api_key=VL_MODEL_TOKEN, base_url=VL_MODEL_URL),
            model=VL_MODEL_NAME,
            stream=False,
            client_kwargs={"timeout": 120},
        ),
        toolkit=Toolkit(
            tools=await _workspace.list_tools(),
            skills_or_loaders=await _workspace.list_skills(),
        ),
        offloader=_workspace,
        state=AgentState(
            session_id="demo-session",
            permission_context=PermissionContext(mode=PermissionMode.BYPASS),
        ),
        graph=_GRAPH,
    )
    return _agent


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)


app = FastAPI(title="LangGraph × AgentScope Bridge Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/langgraph-agent/stream")
async def stream_chat(req: ChatRequest) -> StreamingResponse:
    agent = await get_agent()

    async def event_generator() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'WORKFLOW_START', 'question': req.question}, ensure_ascii=False)}\n\n"
        try:
            async for evt in agent.reply_stream(UserMsg("user", req.question)):
                yield f"data: {json.dumps(evt.model_dump(mode='json'), ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'WORKFLOW_DONE'}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'ERROR', 'detail': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "langgraph_bridge_demo"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("langgraph_bridge_demo:app", host="0.0.0.0", port=8096, reload=False)
