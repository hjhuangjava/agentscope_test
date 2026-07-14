"""
深度集成样例：create_app(custom_agent_cls=LangGraphAgent)。

依赖：
- Redis（Storage）
- 可选 Redis MessageBus；默认用 InMemoryMessageBus 方便本地试

启动前请确保 Redis 可连，并先通过 AgentScope 控制台/API 创建 user/agent/session
与 chat model credential（本文件不负责初始化租户数据）。

启动：
    set REDIS_URL=redis://localhost:6379/0
    python langgraph_bridge_app.py

说明：
- ChatService.run 每次对话用 custom_agent_cls 组装 Agent
- SSE / 持久化 / 中间件由 AgentScope 服务层接管
- 业务推理在 LangGraphAgent._reply_impl → LangGraph


得到（AgentScope 基础设施自动生效）：

✅ SSE 事件流（回放 + 实时 + 心跳），前端零改造
✅ Session / Agent / 消息的持久化
✅ 多租户、凭证管理
✅ 中间件系统（RAG、长期记忆、TTS、权限等钩子照常触发）
✅ 分布式锁、并发序列化
✅ HITL 人机协同
放弃（LangGraph 侧被绕过的能力）：

❌ LangGraph 的流式 astream_events 不会自动映射为 AgentScope 事件——需要你在 _reply 中手动 yield 对应的 AgentEvent
❌ LangGraph Studio / LangSmith 的可视化追踪（除非你额外接入）
❌ LangGraph 的 checkpoint 持久化（AgentScope 用自己的 Storage 管理 state）
"""

from __future__ import annotations

import os
from pathlib import Path

from agentscope.app import create_app
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.storage import RedisStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager

from langgraph_agent import make_langgraph_agent_cls

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WORKSPACE_BASE = Path(__file__).parent / ".agentscope-workspaces"

# redis://host:port/db → RedisStorage 参数
_redis_host = "localhost"
_redis_port = 6379
_redis_db = 0
if REDIS_URL.startswith("redis://"):
    body = REDIS_URL[len("redis://") :]
    host_port, _, db_part = body.partition("/")
    if ":" in host_port:
        _redis_host, port_s = host_port.rsplit(":", 1)
        _redis_port = int(port_s)
    else:
        _redis_host = host_port or "localhost"
    if db_part:
        _redis_db = int(db_part)


def build_app():
    WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)
    return create_app(
        storage=RedisStorage(host=_redis_host, port=_redis_port, db=_redis_db),
        message_bus=InMemoryMessageBus(),
        workspace_manager=LocalWorkspaceManager(basedir=str(WORKSPACE_BASE)),
        custom_agent_cls=make_langgraph_agent_cls(),
        title="LangGraph × AgentScope Bridge",
    )


app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("langgraph_bridge_app:app", host="0.0.0.0", port=8000, reload=False)
