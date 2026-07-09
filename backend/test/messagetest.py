from agentscope.message import UserMsg, SystemMsg, AssistantMsg

# 用户消息
user_msg = UserMsg(
	name="user",
	content="这张图片里有什么？"
)

# 系统消息，仅用于系统提示（System prompt）
system_msg = SystemMsg(
	name="system",
	content="你是一个名为 Friday 的 AI 助手。"
)

# 助手消息
assistant_msg = AssistantMsg(
	name="Friday",
	content="你好，有什么我可以帮你的吗？"
)

# 获取所有文本内容
text = user_msg.get_text_content()

print("========",text)
# 获取所有工具调用
tool_calls = user_msg.get_content_blocks("tool_call")

# 检查消息是否包含工具结果
if user_msg.has_content_blocks("tool_result"):
    print("消息包含工具结果")
else:
    print("消息不包含工具结果")