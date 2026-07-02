"""
AgentScope 2.0.3 计划模式 (Plan) 测试脚本。

覆盖点：
1. 装配 4 个 plan 工具：TaskCreate / TaskGet / TaskList / TaskUpdate
2. 在 agent 首轮 reply 前预置 (seed) 两个带依赖关系的任务
3. 通过 reply_stream 观察 agent 如何继续创建/查询/更新任务
4. 结束后打印 agent.state.tasks_context 最终状态，验证：
   - 依赖边 (blocks / blocked_by) 是否对称
   - 任务状态流转 (pending -> in_progress -> completed)
   - 状态注入式工具 (is_state_injected=True) 直接读写同一份 tasks_context

后端：http://192.168.39.100:11806 上的 qwen3.6:35b (OpenAI 兼容)
"""

import asyncio

from agentscope.agent import Agent
from agentscope.tool import Toolkit, TaskCreate, TaskGet, TaskList, TaskUpdate
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.message import UserMsg
from agentscope.state import AgentState, Task
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.event import EventType


VL_MODEL_URL = "http://192.168.39.100:11806/v1"
VL_MODEL_NAME = "qwen3.6:35b"
VL_MODEL_TOKEN = "empty"  # 本地无鉴权，SDK 要求非空就用占位串


def print_tasks_context(state: AgentState) -> None:
    """打印当前 tasks_context 的所有任务及其依赖关系。"""
    tasks = state.tasks_context.tasks
    print("\n========== tasks_context 最终状态 ==========")
    if not tasks:
        print("(空)")
        return
    for t in tasks:
        print(f"  - id={t.id}  state={t.state:<11} subject={t.subject}")
        if t.blocks:
            print(f"      blocks    = {t.blocks}")
        if t.blocked_by:
            print(f"      blocked_by= {t.blocked_by}")
        if t.owner:
            print(f"      owner     = {t.owner}")
    print(f"  共 {len(tasks)} 个任务")
    print("=" * 46)


async def main() -> None:
    # BYPASS：plan 工具本身 check_permissions 即 ALLOW，但保持与 agent_local.py 一致
    state = AgentState(
        permission_context=PermissionContext(mode=PermissionMode.BYPASS)
    )

    agent = Agent(
        name="planner",
        system_prompt=(
            "You are a planning assistant. "
            "When asked to plan work, use the TaskCreate / TaskList / TaskGet / TaskUpdate "
            "tools to maintain an explicit, structured task list. "
            "Always mark a task in_progress before working on it, and completed when done."
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
            tools=[
                TaskCreate(),
                TaskGet(),
                TaskList(),
                TaskUpdate(),
            ]
        ),
        state=state,
    )

    # ---- 步骤 1：预置 (seed) 两个带依赖关系的任务 ----
    # 文档示例：先建任务 "1" 与 "2"，再让 "2" 依赖 "1"，
    # 通过手动维护反向边保持 blocks / blocked_by 对称。
    agent.state.tasks_context.tasks.extend(
        [
            Task(
                id="1",
                subject="Fetch project requirements",
                description=(
                    "Read README.md and CONTRIBUTING.md in the repo root, "
                    "summarize the core constraints."
                ),
                metadata={"source": "seed"},
            ),
            Task(
                id="2",
                subject="Draft an implementation plan",
                description=(
                    "Produce a step-by-step plan based on the requirements "
                    "fetched in task 1."
                ),
                blocked_by=["1"],
                metadata={"source": "seed"},
            ),
        ]
    )
    # 反向边：task 1 阻塞 task 2
    agent.state.tasks_context.tasks[0].blocks.append("2")

    print("[seed] 已预置 2 个任务，当前任务清单：")
    print_tasks_context(agent.state)

    # ---- 步骤 2：让 agent 在此基础上继续规划 ----
    # 给一个会触发 TaskCreate / TaskUpdate / TaskList 的复杂请求。
    user_prompt = (
        "我已经预置了两个任务（id=1, id=2）。"
        "请基于已有清单继续完善这份'实现一个 Python Web 爬虫'的项目计划：\n"
        "  1) 用 TaskList 看一下当前的任务清单\n"
        "  2) 用 TaskGet 查看任务 1 的详情\n"
        "  3) 把任务 1 标记为 in_progress，再补充 3~4 个新任务（如：选型、"
        "下载页面、解析 HTML、存储结果），并合理设置它们之间的依赖关系\n"
        "  4) 最后用 TaskList 再确认一次完整计划\n"
    )

    print("\n========== 事件流 ==========")
    tool_calls: dict[str, list[str]] = {}

    async for evt in agent.reply_stream(UserMsg("Tony", user_prompt)):
        match evt.type:
            case EventType.THINKING_BLOCK_DELTA:
                # 思考增量默认不打印，避免刷屏
                ...
            case EventType.TEXT_BLOCK_DELTA:
                print(getattr(evt, "delta", ""), end="", flush=True)
            case EventType.TEXT_BLOCK_END:
                print()
            case EventType.TOOL_CALL_START:
                tid = evt.tool_call_id
                tool_calls.setdefault(tid, []).append(evt.tool_call_name)
                print(f"\n[tool] {evt.tool_call_name} (id={tid[:8]})")
            case EventType.TOOL_CALL_DELTA:
                print(evt.delta, end="", flush=True)
                tool_calls.setdefault(evt.tool_call_id, []).append(evt.delta)
            case EventType.TOOL_CALL_END:
                print()
            case EventType.TOOL_RESULT_START:
                print(f"[result] {evt.tool_call_name}:")
            case EventType.TOOL_RESULT_TEXT_DELTA:
                chunk = evt.delta
                if len(chunk) > 300:
                    chunk = chunk[:300] + "...(truncated)"
                print(chunk, end="", flush=True)
            case EventType.TOOL_RESULT_END:
                ts = getattr(evt, "state", None)
                print(f"\n[result end] state={ts}")
            case EventType.MODEL_CALL_END:
                ti = getattr(evt, "input_tokens", 0)
                to = getattr(evt, "output_tokens", 0)
                print(f"[model] in={ti} out={to} total={ti + to}")
            case EventType.REPLY_END:
                print("\n[reply end]")
            case _:
                print(f"[event] {evt.type}")

    # ---- 步骤 3：检查最终 tasks_context ----
    # 这是文档强调的核心：plan 工具直接读写 agent.state.tasks_context，
    # LLM 调用结束后，状态变更可在循环外直接读到。
    print_tasks_context(agent.state)

    # ---- 步骤 4：序列化验证（plan 随 AgentState 一并持久化）----
    # 文档强调 tasks_context 是 AgentState 上的常规字段，
    # 因此用 Pydantic 的 model_dump / model_dump_json 即可整体保存。
    snap = agent.state.model_dump()
    n_in_snap = len(snap["tasks_context"]["tasks"])
    print(f"[model_dump]     序列化后任务数 = {n_in_snap}")

    json_str = agent.state.model_dump_json(indent=2)
    print(f"[model_dump_json] 长度 = {len(json_str)} 字符（前 200 字预览）：")
    print(json_str[:200] + ("..." if len(json_str) > 200 else ""))


if __name__ == "__main__":
    asyncio.run(main())
