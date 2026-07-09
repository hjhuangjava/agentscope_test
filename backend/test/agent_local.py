"""
AgentScope 2.x Agent + 本地 vLLM 调试脚本。
- 后端：http://192.168.39.100:11806 上的 qwen3.6:35b (OpenAI 兼容)
- 工具：Bash / Grep / Glob / Read / Write / Edit
- 输出：事件流 (reply_stream)
"""

import asyncio

from agentscope.agent import Agent
from agentscope.tool import Toolkit, Bash, Grep, Glob, Read, Write, Edit
from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.message import UserMsg
from agentscope.state import AgentState
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.event import EventType


VL_MODEL_URL = "http://192.168.39.100:11806/v1"
VL_MODEL_NAME = "qwen3.6:35b"
VL_MODEL_TOKEN = "empty"  # 本地无鉴权，SDK 要求非空就用占位串


async def main() -> None:
    # BYPASS 模式跳过工具权限确认，否则 Read/Write/Edit/Bash 都会卡在
    # REQUIRE_USER_CONFIRM 事件等待用户授权。
    state = AgentState(permission_context=PermissionContext(mode=PermissionMode.BYPASS))

    agent = Agent(
        name="Friday",
        system_prompt="You're a helpful assistant named Friday.",
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
                Bash(),
                Grep(),
                Glob(),
                Read(),
                Write(),
                Edit(),
            ]
        ),
        state=state,
    )

    text_buf: list[str] = []
    # 缓存工具调用入参/结果，按 tool_call_id 聚合
    tool_args: dict[str, list[str]] = {}
    tool_results: dict[str, list[str]] = {}

    async for evt in agent.reply_stream(UserMsg("Tony", "列出当前目录下的 .py 文件，并告诉我 demo.py 一共有多少行。")):
        match evt.type:
            case EventType.THINKING_BLOCK_DELTA:
                # 思考增量默认不打印，避免刷屏；想看就解开下一行
                # print(getattr(evt, "delta", ""), end="", flush=True)
                ...
            case EventType.TEXT_BLOCK_DELTA:
                delta = getattr(evt, "delta", "")
                text_buf.append(delta)
                print(delta, end="", flush=True)
            case EventType.TEXT_BLOCK_END:
                print()  # 换行收尾
            case EventType.TOOL_CALL_START:
                tid = evt.tool_call_id
                tool_args.setdefault(tid, []).append(f"[tool] {evt.tool_call_name}")
                print(f"\n[tool] {evt.tool_call_name} (id={tid[:8]})")
            case EventType.TOOL_CALL_DELTA:
                # vLLM 工具入参以 delta 流式推送
                tid = evt.tool_call_id
                print(evt.delta, end="", flush=True)
                tool_args.setdefault(tid, []).append(evt.delta)
            case EventType.TOOL_CALL_END:
                print()  # 工具入参结束换行
            case EventType.TOOL_RESULT_START:
                print(f"[result] {evt.tool_call_name}:")
            case EventType.TOOL_RESULT_TEXT_DELTA:
                # 工具执行结果正文（截断超长输出，避免刷屏）
                chunk = evt.delta
                if len(chunk) > 200:
                    chunk = chunk[:200] + "...(truncated)"
                print(chunk, end="", flush=True)
            case EventType.TOOL_RESULT_END:
                state = getattr(evt, "state", None)
                print(f"\n[result end] state={state}")
            case EventType.MODEL_CALL_END:
                usage = getattr(evt, "input_tokens", 0) + getattr(evt, "output_tokens", 0)
                print(f"[model] in={getattr(evt,'input_tokens',0)} out={getattr(evt,'output_tokens',0)} total={usage}")
            case EventType.REPLY_END:
                print("\n[reply end]")
            case _:
                # 其他事件统一打一行，方便排查
                print(f"[event] {evt.type}")


if __name__ == "__main__":
    asyncio.run(main())
