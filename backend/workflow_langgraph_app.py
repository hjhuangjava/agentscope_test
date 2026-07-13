"""
LangGraph + AgentScope workflow API。

图结构：
    validate_input -> enrich_context -> prepare_prompt -> agent_reply

启动后端：
    python workflow_langgraph_app.py

启动前端：
    cd front && pnpm dev
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.tool import Toolkit
from agentscope.workspace import LocalWorkspace
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from message_stream import agent_event, workflow_done, workflow_error, workflow_msg, workflow_start
from workflow_graph import create_workflow_graph

WORKDIR = Path(__file__).parent / ".workflow-langgraph-workspace"
VL_MODEL_URL = os.getenv("VL_MODEL_URL", "http://192.168.39.100:11806/v1")
VL_MODEL_NAME = os.getenv("VL_MODEL_NAME", "qwen3.6:35b")
VL_MODEL_TOKEN = os.getenv("VL_MODEL_TOKEN", "empty")

_agent: Optional[Agent] = None
_workspace: Optional[LocalWorkspace] = None
workflow_graph = create_workflow_graph()


async def get_agent() -> Agent:
    global _agent, _workspace
    if _agent is not None:
        return _agent

    WORKDIR.mkdir(parents=True, exist_ok=True)
    _workspace = LocalWorkspace(workdir=str(WORKDIR))
    await _workspace.initialize()

    _agent = Agent(
        name="workflow-agent",
        system_prompt="You are a helpful assistant. Answer clearly in Chinese.",
        model=OpenAIChatModel(
            credential=OpenAICredential(api_key=VL_MODEL_TOKEN, base_url=VL_MODEL_URL),
            model=VL_MODEL_NAME,
            stream=True,
            client_kwargs={"timeout": 120},
        ),
        toolkit=Toolkit(
            tools=await _workspace.list_tools(),
            skills_or_loaders=await _workspace.list_skills(),
        ),
        offloader=_workspace,
        state=AgentState(permission_context=PermissionContext(mode=PermissionMode.BYPASS)),
    )
    return _agent


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")


app = FastAPI(title="AgentScope LangGraph Workflow API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_input_state(req: ChatRequest) -> Dict[str, Any]:
    return {
        "user_input": req.question.strip(),
        "user_id": "user",
        "session_id": "default",
        "messages": [],
    }


@app.post("/api/workflow/chat/stream")
async def workflow_chat_stream(req: ChatRequest) -> StreamingResponse:
    agent = await get_agent()
    input_state = {**_build_input_state(req), "_agent": agent}

    async def event_generator() -> AsyncIterator[str]:
        yield workflow_start(req.question)
        try:
            async for chunk in workflow_graph.astream(
                input_state,
                stream_mode=["custom", "updates"],
            ):
                if isinstance(chunk, tuple):
                    mode, data = chunk
                else:
                    mode, data = "custom", chunk

                if mode == "custom" and isinstance(data, dict):
                    if data.get("type") == "WORKFLOW_MSG":
                        yield workflow_msg(data["node"], data["message"])
                    elif "type" in data:
                        yield agent_event(data)
                # updates 模式暂不推送到前端，避免噪音。
        except Exception as exc:
            yield workflow_error(str(exc))
            return
        yield workflow_done()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "workflow_langgraph"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("workflow_langgraph_app:app", host="0.0.0.0", port=8093, reload=False)
