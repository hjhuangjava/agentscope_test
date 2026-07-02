"""
AgentScope 2.0.3 Workspace Manager 测试脚本。

参考文档：https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/workspace
对应章节：Workspace Manager

Manager 的职责（区别于单 workspace）：
- 分配：create_workspace(user_id, agent_id, session_id)
- 缓存 & TTL：以 workspace_id 为键缓存，空闲超 ttl 秒淘汰
- 隔离：内置 manager 都按 agent_id 隔离（workdir = <basedir>/<agent_id>）
- 回收：close(workspace_id) / close_all()

注意：文档里 `from agentscope.app._manager import LocalWorkspaceManager` 是过时路径，
真实路径是 `from agentscope.app.workspace_manager import LocalWorkspaceManager`。
需要 `pip install apscheduler`（agentscope.app.__init__ 强制加载 scheduler 子模块）。
"""

import asyncio
import shutil
from pathlib import Path

from agentscope.agent import Agent
from agentscope.tool import Toolkit
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.message import UserMsg
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.event import EventType
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.workspace import LocalWorkspace


BASEDIR = Path(__file__).parent / ".workspace-manager-test"
SKILL_PATHS = [
    str(Path(__file__).parent / "skills" / "shuyixin-openapi"),
    str(Path(__file__).parent / "skills" / "zhipu-web-search"),
    str(Path(__file__).parent / "skills" / "tavily-web-search"),
]

VL_MODEL_URL = "http://192.168.39.100:11806/v1"
VL_MODEL_NAME = "qwen3.6:35b"
VL_MODEL_TOKEN = "empty"


def print_section(title: str) -> None:
    print(f"\n========== {title} ==========")


async def demo_agent_via_manager(manager: LocalWorkspaceManager) -> None:
    """通过 manager 分配 workspace，让 agent 用 tavily-web-search skill 检索最新 AI 新闻。

    演示 Manager 模式下的 Agent 集成：
    - workspace 不再手动构造，而是 create_workspace 拿到（自带 skill seed）
    - 同一个 workspace 既给 toolkit 提供资源，又给 agent 当 offloader
    """
    print_section("步骤 4.5：通过 manager 分配 workspace + agent 集成（tavily-web-search）")

    workspace = await manager.create_workspace(
        user_id="user-1",
        agent_id="agent-42",
        session_id="session-agent-demo",
    )
    print(f"workspace_id = {workspace.workspace_id}")
    print(f"workdir      = {workspace.workdir}")

    state = AgentState(
        permission_context=PermissionContext(mode=PermissionMode.BYPASS)
    )

    agent = Agent(
        name="researcher",
        system_prompt=(
            "You are a helpful research assistant. "
            "When asked to search the web, ALWAYS use the `tavily-web-search` skill: "
            "first call the `Skill` tool to read its SKILL.md, "
            "then run its script with the `Bash` tool. "
            "Summarize findings in Chinese."
        ),
        model=OpenAIChatModel(
            credential=OpenAICredential(
                api_key=VL_MODEL_TOKEN,
                base_url=VL_MODEL_URL,
            ),
            model=VL_MODEL_NAME,
            stream=True,
            client_kwargs={"timeout": 120},
        ),
        toolkit=Toolkit(
            tools=await workspace.list_tools(),
            skills_or_loaders=await workspace.list_skills(),
        ),
        offloader=workspace,
        state=state,
    )

    async for evt in agent.reply_stream(
        UserMsg("Tony", "用 tavily-web-search skill 搜一下 2025 年最新的 AI 大模型进展，给我一个简短中文摘要。")
    ):
        match evt.type:
            case EventType.THINKING_BLOCK_DELTA:
                ...
            case EventType.TEXT_BLOCK_DELTA:
                print(getattr(evt, "delta", ""), end="", flush=True)
            case EventType.TEXT_BLOCK_END:
                print()
            case EventType.TOOL_CALL_START:
                print(f"\n[tool] {evt.tool_call_name} (id={evt.tool_call_id[:8]})")
            case EventType.TOOL_CALL_DELTA:
                print(evt.delta, end="", flush=True)
            case EventType.TOOL_CALL_END:
                print()
            case EventType.TOOL_RESULT_START:
                print(f"[result] {evt.tool_call_name}:")
            case EventType.TOOL_RESULT_TEXT_DELTA:
                chunk = evt.delta
                if len(chunk) > 400:
                    chunk = chunk[:400] + "...(truncated)"
                print(chunk, end="", flush=True)
            case EventType.TOOL_RESULT_END:
                print(f"\n[result end] state={getattr(evt, 'state', None)}")
            case EventType.MODEL_CALL_END:
                ti = getattr(evt, "input_tokens", 0)
                to = getattr(evt, "output_tokens", 0)
                print(f"[model] in={ti} out={to} total={ti + to}")
            case EventType.REPLY_END:
                print("[reply end]")
            case _:
                pass

    # 演示结束主动归还，让缓存里的 workspace 被 close
    await manager.close(workspace.workspace_id)
    print(f"已 close workspace（is_alive={workspace.is_alive}）")


async def main() -> None:
    # 干净起步
    if BASEDIR.exists():
        shutil.rmtree(BASEDIR)
    BASEDIR.mkdir(parents=True)

    print(f"basedir = {BASEDIR}")

    # ---- 构造 manager ----
    manager = LocalWorkspaceManager(
        basedir=str(BASEDIR),
        skill_paths=SKILL_PATHS,
        ttl=3600.0,
    )

    # ---- 步骤 1：create_workspace（首次创建）----
    print_section("步骤 1：create_workspace")
    ws1 = await manager.create_workspace(
        user_id="user-1",
        agent_id="agent-42",
        session_id="session-abc",
    )
    print(f"workspace_id      = {ws1.workspace_id}")
    print(f"workdir           = {ws1.workdir}")
    print(f"is_alive          = {ws1.is_alive}")
    print(f"基于 agent_id 隔离 = {BASEDIR / 'agent-42'}  （实际: {ws1.workdir}）")

    # 验证 workspace 内部资源（skill 已 seed）
    skills = await ws1.list_skills()
    mcps = await ws1.list_mcps()
    tools = await ws1.list_tools()
    print(f"list_skills       = {[s.name for s in skills]}")
    print(f"list_mcps         = {len(mcps)} 个")
    print(f"list_tools        = {[getattr(t, 'tool_name', type(t).__name__) for t in tools]}")

    # ---- 步骤 2：get_workspace 复用（缓存命中）----
    print_section("步骤 2：get_workspace（同一 workspace_id，应缓存命中）")
    ws2 = await manager.get_workspace(
        user_id="user-1",
        agent_id="agent-42",
        session_id="session-abc",
        workspace_id=ws1.workspace_id,
    )
    print(f"返回的 workspace_id = {ws2.workspace_id}")
    print(f"同一对象?           = {ws1 is ws2}  （缓存命中应 True）")

    # ---- 步骤 3：模拟缓存淘汰后的复用（从磁盘重建）----
    print_section("步骤 3：模拟缓存淘汰，验证从磁盘重建")
    await manager.close(ws1.workspace_id)
    print(f"close 后 is_alive   = {ws1.is_alive}")
    ws3 = await manager.get_workspace(
        user_id="user-1",
        agent_id="agent-42",
        session_id="session-abc",
        workspace_id=ws1.workspace_id,
    )
    print(f"重建后 workspace_id = {ws3.workspace_id}  （应与原来相同）")
    print(f"同一对象?           = {ws1 is ws3}  （磁盘重建应 False）")
    print(f"is_alive           = {ws3.is_alive}  （重建后应 True）")
    # 验证 .mcp 持久化文件还在
    mcp_file = Path(ws3.workdir) / ".mcp"
    print(f".mcp 持久化文件     = {mcp_file}（存在: {mcp_file.exists()}, 大小: {mcp_file.stat().st_size if mcp_file.exists() else 0}B）")

    # ---- 步骤 4：跨 agent 隔离 ----
    print_section("步骤 4：跨 agent_id 隔离")
    ws_other = await manager.create_workspace(
        user_id="user-1",
        agent_id="agent-99",   # 不同的 agent
        session_id="session-xyz",
    )
    print(f"agent-99 workdir = {ws_other.workdir}")
    print(f"agent-42 workdir = {ws1.workdir}")
    print(f"两者隔离?        = {ws_other.workdir != ws1.workdir}（应 True）")

    # ---- 步骤 4.5：通过 manager 分配 workspace + agent 集成 ----
    await demo_agent_via_manager(manager)

    # ---- 步骤 5：close_all ----
    print_section("步骤 5：close_all")
    await manager.close_all()
    print("所有 workspace 已关闭")

    # ---- 最终目录结构 ----
    print_section("步骤 6：basedir 最终目录结构")
    for agent_dir in sorted(BASEDIR.iterdir()):
        print(f"  {agent_dir.name}/")
        for child in sorted(agent_dir.iterdir()):
            size = child.stat().st_size if child.is_file() else "-"
            print(f"    {child.name}  ({size}B)")


if __name__ == "__main__":
    asyncio.run(main())
