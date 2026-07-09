"""
AgentScope Runtime 快速开始 Demo
参考：https://runtime.agentscope.io/zh/quickstart.html

运行前请先配置 API Key：
    export DASHSCOPE_API_KEY="your_api_key_here"

启动服务（监听 8090 端口）：
    python demo.py
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope.session import RedisSession

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.deployers import LocalDeployManager


# ---------- 步骤 2：生命周期函数 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """管理服务启动和关闭时的资源"""
    import fakeredis

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # 注意：FakeRedis 仅用于开发/测试；生产环境请替换为真实的 Redis 连接。
    app.state.session = RedisSession(connection_pool=fake_redis.connection_pool)

    yield  # 服务运行中

    print("AgentApp is shutting down...")


# ---------- 步骤 3：创建 Agent App ----------
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    lifespan=lifespan,
)


# ---------- 步骤 4：定义 Agent 查询逻辑 ----------
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=False)

    await agent_app.state.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    await agent_app.state.session.save_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )


# ---------- 步骤 7：使用 LocalDeployManager 部署 ----------
async def main():
    await agent_app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))


# ---------- 步骤 5：启动 Agent App ----------
if __name__ == "__main__":
    # 直接启动内置 API 服务（监听 8090 端口）
    # 如需同时启用内置 Web 对话界面：agent_app.run(host="0.0.0.0", port=8090, web_ui=True)
    agent_app.run(host="0.0.0.0", port=8090)