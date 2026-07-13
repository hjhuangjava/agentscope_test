/**
 * 最小前端订阅样例（对照官方文档）。
 *
 * 链路：fetch POST /api/agent/stream → 读 SSE → 每个 AgentEvent 用
 * AssistantMsg + appendEvent 增量重建 Msg → renderAssistantBubble 逐帧渲染。
 */
import {
  streamAgentEvents,
  isAgentEvent,
  isWorkflowDone,
  isWorkflowError,
  isWorkflowStart,
} from "./api/chatStream";
import {
  renderAssistantBubble,
  renderUserBubble,
  replaceNode,
} from "./ui/render";
import { AssistantMsg, appendEvent, type Msg } from "@agentscope-ai/agentscope/message";
import { EventType, type AgentEvent } from "@agentscope-ai/agentscope/event";
import "./style.css";

/** 一个事件 → 增量更新 Msg（REPLY_START 建空壳，其余 appendEvent）。 */
function applyAgentEvent(msg: Msg | null, event: AgentEvent): Msg | null {
  if (event.type === EventType.REPLY_START) {
    return AssistantMsg({ name: event.name, content: [], id: event.reply_id });
  }
  if (!msg) return null;
  return appendEvent(msg, event);
}

const root = document.querySelector<HTMLElement>("#app")!;
root.innerHTML = `
  <div class="app">
    <header class="header">
      <div>
        <h1>AgentScope SSE 订阅样例</h1>
        <p class="subtitle">fetch 订阅 /api/agent/stream · appendEvent 增量重建 Msg</p>
      </div>
      <div class="status" id="status">就绪</div>
    </header>
    <main class="chat" id="chat"></main>
    <footer class="composer">
      <textarea id="question" rows="3" placeholder="问点啥，例如：大海为什么是蓝色的？"></textarea>
      <div class="composer-actions">
        <button id="sendBtn" type="button">发送</button>
      </div>
    </footer>
  </div>
`;

const statusEl = root.querySelector<HTMLElement>("#status")!;
const chatEl = root.querySelector<HTMLElement>("#chat")!;
const questionEl = root.querySelector<HTMLTextAreaElement>("#question")!;
const sendBtn = root.querySelector<HTMLButtonElement>("#sendBtn")!;

function setStatus(text: string, mode = ""): void {
  statusEl.textContent = text;
  statusEl.className = `status ${mode}`.trim();
}

async function send(): Promise<void> {
  const question = questionEl.value.trim();
  if (!question || sendBtn.disabled) return;

  questionEl.value = "";
  sendBtn.disabled = true;
  chatEl.innerHTML = "";
  chatEl.appendChild(renderUserBubble(question));
  setStatus("订阅中...", "running");

  let msg: Msg | null = null;
  let node: HTMLElement | null = null;

  try {
    for await (const payload of streamAgentEvents({ question })) {
      if (isWorkflowStart(payload)) {
        setStatus("Agent 回复中...", "running");
        continue;
      }
      if (isWorkflowDone(payload)) {
        setStatus("完成");
        continue;
      }
      if (isWorkflowError(payload)) {
        throw new Error(payload.detail);
      }
      if (!isAgentEvent(payload)) continue;

      // 核心：每个 AgentEvent 都 appendEvent 到 Msg，逐帧重渲染
      msg = applyAgentEvent(msg, payload);
      if (!msg) continue;

      const bubble = renderAssistantBubble(msg);
      node = node ? replaceNode(node, bubble) : (chatEl.appendChild(bubble), bubble);
      chatEl.scrollTop = chatEl.scrollHeight;
    }
    setStatus(msg?.finished_at ? "完成" : "已断开");
  } catch (error) {
    setStatus(`错误: ${error instanceof Error ? error.message : String(error)}`, "error");
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", () => void send());
questionEl.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void send();
  }
});
