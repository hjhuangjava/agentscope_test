import {
  streamBridgeChatEvents,
  isAgentEvent,
} from "./api/chatStream";
import {
  renderAssistantBubble,
  renderUserBubble,
  renderWorkflowNodeBubble,
  replaceNode,
} from "./ui/render";
import { AssistantMsg, appendEvent, type Msg } from "@agentscope-ai/agentscope/message";
import { EventType, type AgentEvent } from "@agentscope-ai/agentscope/event";
import { resetBridgeBootstrap } from "./api/bridgeClient";
import "./style.css";

function applyAgentEvent(msg: Msg | null, event: AgentEvent): Msg | null {
  if (event.type === EventType.REPLY_START) {
    return AssistantMsg({
      name: event.name,
      content: [],
      id: event.reply_id,
    });
  }
  if (!msg) return null;
  return appendEvent(msg, event);
}

function parseWorkflowHint(event: AgentEvent): { node: string; detail: string } | null {
  if (event.type !== EventType.HINT_BLOCK) return null;
  const hintEvent = event as AgentEvent & { hint?: string; source?: string | null };
  let node = "workflow";
  let detail = typeof hintEvent.hint === "string" ? hintEvent.hint : "[workflow node]";
  try {
    if (hintEvent.source) {
      const meta = JSON.parse(hintEvent.source) as {
        kind?: string;
        node?: string;
        detail?: string;
      };
      if (meta.kind !== "workflow_node") return null;
      if (meta.node) node = meta.node;
      if (meta.detail) detail = meta.detail;
    }
  } catch {
    /* keep defaults */
  }
  return { node, detail };
}

function createAppShell(): {
  statusEl: HTMLElement;
  chatEl: HTMLElement;
  questionEl: HTMLTextAreaElement;
  sendBtn: HTMLButtonElement;
  clearBtn: HTMLButtonElement;
  resetBtn: HTMLButtonElement;
} {
  const root = document.querySelector<HTMLElement>("#app");
  if (!root) throw new Error("#app not found");

  root.innerHTML = `
    <div class="app">
      <header class="header">
        <div>
          <h1>LangGraph × AgentScope Bridge</h1>
          <p class="subtitle">:8000 · HintBlock 节点进度 + appendEvent 重建回复</p>
        </div>
        <div class="status" id="status">就绪</div>
      </header>
      <main class="chat" id="chat"></main>
      <footer class="composer">
        <textarea id="question" rows="3" placeholder="输入你的问题，例如：大海为什么是蓝色的？"></textarea>
        <div class="composer-actions">
          <button id="sendBtn" type="button">发送</button>
          <button id="clearBtn" type="button" class="secondary">清空</button>
          <button id="resetBtn" type="button" class="secondary">重置会话</button>
        </div>
      </footer>
    </div>
  `;

  return {
    statusEl: root.querySelector("#status")!,
    chatEl: root.querySelector("#chat")!,
    questionEl: root.querySelector("#question") as HTMLTextAreaElement,
    sendBtn: root.querySelector("#sendBtn") as HTMLButtonElement,
    clearBtn: root.querySelector("#clearBtn") as HTMLButtonElement,
    resetBtn: root.querySelector("#resetBtn") as HTMLButtonElement,
  };
}

function setStatus(statusEl: HTMLElement, text: string, mode = ""): void {
  statusEl.textContent = text;
  statusEl.className = `status ${mode}`.trim();
}

function ensureEmptyHint(chatEl: HTMLElement): void {
  if (chatEl.children.length) return;
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.id = "emptyHint";
  empty.textContent =
    "发送问题。LangGraph 节点会以 workflow 气泡显示（HintBlock），Agent 回复通过 appendEvent 重建。";
  chatEl.appendChild(empty);
}

function removeEmptyHint(): void {
  document.getElementById("emptyHint")?.remove();
}

async function main(): Promise<void> {
  const { statusEl, chatEl, questionEl, sendBtn, clearBtn, resetBtn } = createAppShell();
  let running = false;
  let abortController: AbortController | null = null;

  ensureEmptyHint(chatEl);

  async function sendQuestion(): Promise<void> {
    const question = questionEl.value.trim();
    if (!question || running) return;

    running = true;
    sendBtn.disabled = true;
    abortController = new AbortController();
    setStatus(statusEl, "连接 SSE / 触发对话...", "running");
    removeEmptyHint();
    questionEl.value = "";

    chatEl.appendChild(renderUserBubble(question));

    let assistantMsg: Msg | null = null;
    let assistantNode: HTMLElement | null = null;

    try {
      for await (const payload of streamBridgeChatEvents({ question }, abortController.signal)) {
        if (!isAgentEvent(payload)) continue;

        const workflowHint = parseWorkflowHint(payload);
        if (workflowHint) {
          chatEl.appendChild(
            renderWorkflowNodeBubble(workflowHint.node, workflowHint.detail),
          );
          setStatus(statusEl, `节点 ${workflowHint.node}...`, "running");
          chatEl.scrollTop = chatEl.scrollHeight;
        }

        assistantMsg = applyAgentEvent(assistantMsg, payload);
        if (!assistantMsg) continue;

        if (payload.type === EventType.REPLY_END || assistantMsg.finished_at) {
          setStatus(statusEl, "完成");
        } else if (!workflowHint) {
          setStatus(statusEl, "生成中...", "running");
        }

        if (!assistantNode) {
          assistantNode = renderAssistantBubble(assistantMsg);
          chatEl.appendChild(assistantNode);
        } else {
          assistantNode = replaceNode(assistantNode, renderAssistantBubble(assistantMsg));
        }
        chatEl.scrollTop = chatEl.scrollHeight;
      }
      setStatus(statusEl, "完成");
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(statusEl, `错误: ${message}`, "error");
      chatEl.appendChild(
        renderAssistantBubble({
          id: "error",
          name: "assistant",
          role: "assistant",
          content: [{ type: "text", id: "error-text", text: `请求失败: ${message}` }],
          metadata: {},
          created_at: new Date().toISOString(),
          finished_at: new Date().toISOString(),
        }),
      );
    } finally {
      running = false;
      sendBtn.disabled = false;
      abortController = null;
      chatEl.scrollTop = chatEl.scrollHeight;
    }
  }

  sendBtn.addEventListener("click", () => void sendQuestion());
  clearBtn.addEventListener("click", () => {
    abortController?.abort();
    chatEl.innerHTML = "";
    ensureEmptyHint(chatEl);
    setStatus(statusEl, "就绪");
  });
  resetBtn.addEventListener("click", () => {
    resetBridgeBootstrap();
    setStatus(statusEl, "已重置 bootstrap，下次发送将重新创建 agent/session");
  });
  questionEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion();
    }
  });
}

void main();
