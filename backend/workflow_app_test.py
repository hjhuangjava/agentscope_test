"""
最小 Agent 问答测试（无 LangGraph / 无 lifespan）。

用途：
    验证 AgentScope Agent 能否通过 FastAPI 正常接收问题并返回答案。
    参考 workspacemanagertest.py 的 Agent + reply_stream 用法。

启动后端：
    python workflow_app_test.py

启动前端（前后端分离）：
    cd front && pnpm install && pnpm dev

测试：
    POST /api/chat
    {"question": "大海为什么是蓝色的？"}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import AsyncIterator, Dict, Optional

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.event import EventType
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

# Agent 工作目录（文件读写、skill 等资源的本地沙箱）
WORKDIR = Path(__file__).parent / ".workflow-test-workspace"

# 模型服务配置，可通过环境变量覆盖（默认与 workspacemanagertest.py 一致）
VL_MODEL_URL = os.getenv("VL_MODEL_URL", "http://192.168.39.100:11806/v1")
VL_MODEL_NAME = os.getenv("VL_MODEL_NAME", "qwen3.6:35b")
VL_MODEL_TOKEN = os.getenv("VL_MODEL_TOKEN", "empty")

# 全局单例：首次请求时懒加载，避免模块 import 阶段执行 async 初始化
_agent: Optional[Agent] = None
_workspace: Optional[LocalWorkspace] = None


async def get_agent() -> Agent:
    """首次请求时创建 LocalWorkspace 和 Agent，后续请求复用同一实例。"""
    global _agent, _workspace
    if _agent is not None:
        return _agent

    WORKDIR.mkdir(parents=True, exist_ok=True)
    _workspace = LocalWorkspace(workdir=str(WORKDIR))
    await _workspace.initialize()  # 初始化 workspace 内部资源（tools / skills 等）

    _agent = Agent(
        name="test-agent",
        system_prompt="You are a helpful assistant. Answer clearly in Chinese.",
        model=OpenAIChatModel(
            credential=OpenAICredential(api_key=VL_MODEL_TOKEN, base_url=VL_MODEL_URL),
            model=VL_MODEL_NAME,
            stream=True,  # 开启流式，配合 reply_stream 逐块返回文本
            client_kwargs={"timeout": 120},
        ),
        toolkit=Toolkit(
            tools=await _workspace.list_tools(),
            skills_or_loaders=await _workspace.list_skills(),
        ),
        offloader=_workspace,  # Agent 的文件/命令操作委托给 workspace
        state=AgentState(permission_context=PermissionContext(mode=PermissionMode.BYPASS)),
    )
    return _agent


class ChatRequest(BaseModel):
    """请求体：用户问题。"""

    question: str = Field(..., min_length=1, description="用户问题")


class ChatResponse(BaseModel):
    """响应体：原问题 + Agent 完整回答。"""

    question: str
    answer: str


app = FastAPI(title="Agent Test API")

# 允许本地前端页面跨域访问 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """同步接口：等待 Agent 回答完毕后，一次性返回完整文本。"""
    agent = await get_agent()
    text_parts: list[str] = []
    async for evt in agent.reply_stream(UserMsg("user", req.question)):
        # 只收集文本增量，忽略 tool_call / thinking 等事件
        if evt.type == EventType.TEXT_BLOCK_DELTA:
            text_parts.append(getattr(evt, "delta", ""))
    return ChatResponse(question=req.question, answer="".join(text_parts).strip())


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """流式接口：通过 SSE 推送 AgentScope 原始事件，前端用 appendEvent 重建消息。"""
    agent = await get_agent()

    async def event_generator() -> AsyncIterator[str]:
        yield f"data: {json.dumps({'type': 'WORKFLOW_START', 'question': req.question}, ensure_ascii=False)}\n\n"
        try:
            async for evt in agent.reply_stream(UserMsg("user", req.question)):
                payload = evt.model_dump(mode="json")
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'WORKFLOW_DONE'}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'ERROR', 'detail': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health() -> Dict[str, str]:
    """健康检查，用于确认服务是否启动。"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("workflow_app_test:app", host="0.0.0.0", port=8092, reload=False)
