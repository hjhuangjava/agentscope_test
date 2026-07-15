"""
深度集成样例：create_app(custom_agent_cls=LangGraphAgent)。

依赖：
- Redis（Storage）
- 可选 Redis MessageBus；默认用 InMemoryMessageBus 方便本地试

启动前请确保 Redis 可连，并先通过 AgentScope 控制台/API 创建 user/agent/session
与 chat model credential（本文件不负责初始化租户数据）。

启动：
    python langgraph_bridge_app.py
    → http://127.0.0.1:8000
    → OpenAPI: http://127.0.0.1:8000/docs

前端访问（Vite 已代理同名路径到 :8000）：
    /chat  /sessions  /agent  /credential  /model  /workspace  ...

说明：
- ChatService.run 每次对话用 custom_agent_cls 组装 Agent
- SSE / 持久化 / 中间件由 AgentScope 服务层接管
- 业务推理在 LangGraphAgent._reply_impl → LangGraph


✅ SSE 事件流（回放 + 实时 + 心跳），前端零改造
✅ Session / Agent / 消息的持久化
✅ 多租户、凭证管理
✅ 中间件系统（RAG、长期记忆、TTS、权限等钩子照常触发）
✅ 分布式锁、并发序列化
✅ HITL 人机协同
放弃（LangGraph 侧被绕过的能力）：

❌ LangGraph 的流式 astream_events 不会自动映射为 AgentScope 事件——需要你在 _reply 中手动 yield 对应的 AgentEvent
❌ LangGraph Studio / LangSmith 的可视化追踪（除非你额外接入）
❌ LangGraph 的 checkpoint 持久化（AgentScope 用自己的 Storage 管理 state）。你基于这个帮我写一个langgraph和agentscope结合的样例。
"""

from __future__ import annotations

from pathlib import Path

from agentscope.app import create_app
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import RedisStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from fastapi.middleware.cors import CORSMiddleware

from langgraph_agent import make_langgraph_agent_cls

WORKSPACE_BASE = Path(__file__).parent / ".agentscope-workspaces"

# RedisStorage 参数（写死，不从环境变量读取）
REDIS_HOST = "10.253.9.160"
REDIS_PORT = 63791
REDIS_DB = 0
REDIS_USERNAME = "dev_write"
REDIS_PASSWORD = "9uLW3JJJ5C%4Fr"


def build_app():
    WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)
    return create_app(
        storage=RedisStorage(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            username=REDIS_USERNAME,
        ),
        message_bus=InMemoryMessageBus(),
        workspace_manager=LocalWorkspaceManager(basedir=str(WORKSPACE_BASE)),
        custom_agent_cls=make_langgraph_agent_cls(),
        title="LangGraph × AgentScope Bridge",
    )


app = build_app()
# 允许前端（如 Vite :5173）跨域访问本 app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("langgraph_bridge_app:app", host="0.0.0.0", port=8000, reload=False)
