"""
最小端到端样例：后端 SSE 推送 AgentScope AgentEvent，前端订阅并 appendEvent 重建。

对照官方文档《消息与事件 → 示例：流式界面》最朴素写法，不依赖 LangGraph：

    async for event in agent.reply_stream(user_msg):
        yield sse(event.model_dump(mode="json"))

运行：
    python agent_stream_app.py        # 监听 :8095
然后启动前端（npm run dev）打开 /agent-demo.html 即可订阅。

事件流说明（前端据此区分）：
    WORKFLOW_START / WORKFLOW_DONE / ERROR   —— 控制事件（message_stream.py 产出）
    REPLY_START / TEXT_BLOCK_DELTA / ...      —— AgentScope AgentEvent，前端 appendEvent 重建 Msg
"""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, Optional

from agentscope.agent import Agent
from agentscope.credential import OpenAICredential
from agentscope.message import UserMsg
from agentscope.model import OpenAIChatModel
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from message_stream import agent_event, workflow_done, workflow_error, workflow_start

# 复用现有环境变量；按需改成你自己的模型
VL_MODEL_URL = os.getenv("VL_MODEL_URL", "http://192.168.39.100:11806/v1")
VL_MODEL_NAME = os.getenv("VL_MODEL_NAME", "qwen3.6:35b")
VL_MODEL_TOKEN = os.getenv("VL_MODEL_TOKEN", "empty")

_agent: Optional[Agent] = None


async def get_agent() -> Agent:
    """懒加载一个纯对话 Agent（无工具、无 workspace），保证最小可跑。"""
    global _agent
    if _agent is not None:
        return _agent

    _agent = Agent(
        name="stream-agent",
        system_prompt="You are a helpful assistant. Answer clearly in Chinese.",
        model=OpenAIChatModel(
            credential=OpenAICredential(api_key=VL_MODEL_TOKEN, base_url=VL_MODEL_URL),
            model=VL_MODEL_NAME,
            stream=True,
            client_kwargs={"timeout": 120},
        ),
        state=AgentState(permission_context=PermissionContext(mode=PermissionMode.BYPASS)),
    )
    return _agent


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")


app = FastAPI(title="AgentScope Agent SSE Demo")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/agent/stream")
async def agent_stream(req: ChatRequest) -> StreamingResponse:
    """订阅入口：把 agent.reply_stream 的每个 AgentEvent 原样 SSE 推出。"""
    agent = await get_agent()

    async def event_generator() -> AsyncIterator[str]:
        # 1) 起始控制事件，前端据此切状态
        yield workflow_start(req.question)
        try:
            # 2) 核心：消费事件流 → model_dump → SSE 推送
            user_msg = UserMsg(name="user", content=req.question)
            async for event in agent.reply_stream(user_msg):
                yield agent_event(event.model_dump(mode="json"))
        except Exception as exc:
            yield workflow_error(str(exc))
            return
        # 3) 结束控制事件
        yield workflow_done()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "agent_stream_demo"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_stream_app:app", host="0.0.0.0", port=8095, reload=False)
