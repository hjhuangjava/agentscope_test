"""
AgentScope 2.0.3 工作区 (Workspace) 测试脚本。

覆盖文档（https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/workspace）的四组接口：
1. 生命周期：initialize / close / async with
2. 资源列出：list_tools / list_mcps / list_skills / get_instructions
3. 上下文 offload：offload_context / offload_tool_result
4. 与 Agent 集成：toolkit 从 workspace 拿资源，agent 用 workspace 作 offloader

后端：LocalWorkspace（宿主文件系统），无需 Docker / E2B / MCP server。
后端模型：http://192.168.39.100:11806 上的 qwen3.6:35b (OpenAI 兼容)
"""

import asyncio
import os
import shutil
from pathlib import Path

from agentscope.agent import Agent
from agentscope.tool import Toolkit
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.message import UserMsg, AssistantMsg, ToolResultBlock
from agentscope.workspace import LocalWorkspace
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.state import AgentState
from agentscope.event import EventType
from agentscope.mcp import MCPClient
from agentscope.mcp._config import StdioMCPConfig


VL_MODEL_URL = "http://192.168.39.100:11806/v1"
VL_MODEL_NAME = "qwen3.6:35b"
VL_MODEL_TOKEN = "empty"

WORKDIR = Path(__file__).parent / ".workspace-test"
WEATHER_MCP_SERVER = Path(__file__).parent / "weather_mcp_server.py"
SKILL_PATHS = [
    str(Path(__file__).parent / "skills" / "shuyixin-openapi"),
    str(Path(__file__).parent / "skills" / "zhipu-web-search"),
    str(Path(__file__).parent / "skills" / "tavily-web-search"),
]


def print_section(title: str) -> None:
    print(f"\n========== {title} ==========")


def print_tree(path: Path, prefix: str = "", max_depth: int = 3, depth: int = 0) -> None:
    """简易目录树打印，避免依赖第三方库。"""
    if depth > max_depth or not path.exists():
        return
    if path.is_dir():
        print(f"{prefix}{path.name}/" if depth else f"{path}/")
        children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for i, child in enumerate(children):
            last = i == len(children) - 1
            branch = "└── " if last else "├── "
            if child.is_dir():
                print_tree(child, prefix + ("    " if last else "│   ") + branch.replace("└", "└").replace("├", "├"), max_depth, depth + 1)
            else:
                size = child.stat().st_size
                print(f"{prefix}{branch}{child.name}  ({size}B)")
    else:
        print(f"{prefix}{path.name}")


async def demo_lifecycle_and_list(workspace: LocalWorkspace) -> None:
    """演示第 1、2 组接口：生命周期 + 资源列出。"""
    print_section("步骤 1：生命周期 + 资源列出")
    await workspace.initialize()

    tools = await workspace.list_tools()
    mcps = await workspace.list_mcps()
    skills = await workspace.list_skills()
    instructions = await workspace.get_instructions()

    print(f"list_tools()   → {len(tools)} 个内置 tool")
    for t in tools[:8]:
        print(f"  - {getattr(t, 'tool_name', type(t).__name__)}")
    if len(tools) > 8:
        print(f"  ... 还有 {len(tools) - 8} 个")

    print(f"list_mcps()    → {len(mcps)} 个 MCP client")
    for m in mcps:
        print(f"  - {getattr(m, 'name', repr(m))}")

    print(f"list_skills()  → {len(skills)} 个 skill")
    for s in skills:
        print(f"  - {getattr(s, 'name', repr(s))}")

    print(f"\nget_instructions() 预览（前 220 字）：")
    print(instructions[:220] + ("..." if len(instructions) > 220 else ""))


async def demo_offload(workspace: LocalWorkspace) -> None:
    """演示第 3 组接口：上下文 offload。

    offload_context 会把压缩后的消息写到 sessions/<id>/context.jsonl，
    offload_tool_result 会把超大工具结果按 SHA-256 去重写到 data/。
    """
    print_section("步骤 2：上下文 offload")

    session_id = "demo-session-001"

    msgs = [
        UserMsg("Tony", "帮我写一个 Python Web 爬虫"),
        AssistantMsg("planner", "好的，我来规划一下任务步骤……"),
        AssistantMsg("planner", "（已规划完成，等待执行）"),
    ]
    ctx_ref = await workspace.offload_context(session_id, msgs)
    print(f"offload_context  → {ctx_ref}")

    fake_big_output = "x" * 5000  # 模拟一个超大的工具结果
    tool_result = ToolResultBlock(
        type="tool_result",
        id="call_demo_001",
        name="Bash",
        output=fake_big_output,
        state="success",
        metadata={"demo": True},
    )
    tool_ref = await workspace.offload_tool_result(session_id, tool_result)
    print(f"offload_tool_result → {tool_ref}")

    # 验证：再次 offload 相同内容，data/ 下应去重（同一份文件）
    tool_ref_2 = await workspace.offload_tool_result(session_id, tool_result)
    print(f"offload_tool_result (重复) → {tool_ref_2}")
    print("（若 data/ 下文件数不变，说明按 SHA-256 去重生效）")


async def demo_agent_integration(workspace: LocalWorkspace) -> None:
    """演示第 4 组接口：与 Agent 集成。

    workspace 同时承担两个角色：
    - 资源来源：Toolkit(tools=..., mcps=..., skills_or_loaders=...)
    - offloader：Agent(offloader=workspace)

    这次让 agent 真正调用 MCP 工具查询重庆天气。
    """
    print_section("步骤 3：与 Agent 集成（让 agent 调 MCP 工具查重庆天气）")

    state = AgentState(
        permission_context=PermissionContext(mode=PermissionMode.BYPASS)
    )

    agent = Agent(
        name="coder",
        system_prompt=(
            "You are a helpful assistant. "
            "When asked about weather, ALWAYS use the `get_weather` MCP tool "
            "to get real-time data — do not answer from memory."
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
            mcps=await workspace.list_mcps(),
            skills_or_loaders=await workspace.list_skills(),
        ),
        offloader=workspace,
        state=state,
    )

    async for evt in agent.reply_stream(
        UserMsg("Tony", "请帮我查一下重庆现在的天气情况。")
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

async def demo_skill_query(workspace: LocalWorkspace) -> None:
    """演示 skill 调用：让 agent 通过 shuyixin-openapi skill 查百度公司工商信息。"""
    print_section("步骤 3.5：让 agent 通过 skill 查百度公司工商信息")

    state = AgentState(
        permission_context=PermissionContext(mode=PermissionMode.BYPASS)
    )

    agent = Agent(
        name="researcher",
        system_prompt=(
            "You are a research assistant. "
            "When asked to query company info, use the `shuyixin-openapi` skill: "
            "first call the `Skill` tool to read its SKILL.md, "
            "then run its script with the `Bash` tool."
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
        UserMsg(
            "Tony",
            "用 tavily-web-search skill 查一下'百度在线网络技术（北京）有限公司'"
            "的工商信息，给我一个简短摘要：企业名称、法定代表人、注册资本、经营状态。",
        )
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


async def main() -> None:
    # 干净起步：清空旧的 workdir，便于观察目录结构变化
    if WORKDIR.exists():
        shutil.rmtree(WORKDIR)
    WORKDIR.mkdir(parents=True, exist_ok=True)

    print(f"workdir = {WORKDIR}")

    # 真实的 stdio MCP：本地 weather_mcp_server.py（Open-Meteo 免费数据源）
    weather_mcp = MCPClient(
        name="weather",
        is_stateful=True,  # stdio MCP 需要长连接
        mcp_config=StdioMCPConfig(
            command="python",
            args=[str(WEATHER_MCP_SERVER)],
            cwd=str(Path(__file__).parent),
        ),
    )

    workspace = LocalWorkspace(
        workdir=str(WORKDIR),
        default_mcps=[weather_mcp],
        skill_paths=SKILL_PATHS,
    )

    try:
        #await demo_lifecycle_and_list(workspace)

        #await demo_offload(workspace)

        #await demo_agent_integration(workspace)

        await demo_skill_query(workspace)

        print_section("步骤 4：workdir 最终目录结构")
        print_tree(WORKDIR, max_depth=3)

    finally:
        # 第 1 组接口的最后一环：close
        await workspace.close()
        print_section("步骤 5：workspace.close() 已调用，资源释放完成")
        print(f"（workdir 保留在 {WORKDIR}，可手动检查；下次运行会清空重建）")


if __name__ == "__main__":
    asyncio.run(main())
