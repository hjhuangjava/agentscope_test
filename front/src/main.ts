import { streamChatEvents, isAgentEvent } from "./api/chatStream";
import { applyEvent } from "./message/rebuild";
import { renderAssistantBubble, renderUserBubble, replaceNode } from "./ui/render";
import type { Msg } from "@agentscope-ai/agentscope/message";
import "./style.css";

function createAppShell(): {
  statusEl: HTMLElement;
  chatEl: HTMLElement;
  questionEl: HTMLTextAreaElement;
  sendBtn: HTMLButtonElement;
  clearBtn: HTMLButtonElement;
} {
  const root = document.querySelector<HTMLElement>("#app");
  if (!root) throw new Error("#app not found");

  root.innerHTML = `
    <div class="app">
      <header class="header">
        <div>
          <h1>AgentScope Chat</h1>
          <p class="subtitle">前后端分离 · TypeScript · appendEvent 重建 Message</p>
        </div>
        <div class="status" id="status">就绪</div>
      </header>
      <main class="chat" id="chat"></main>
      <footer class="composer">
        <textarea id="question" rows="3" placeholder="输入你的问题，例如：大海为什么是蓝色的？"></textarea>
        <div class="composer-actions">
          <button id="sendBtn" type="button">发送</button>
          <button id="clearBtn" type="button" class="secondary">清空</button>
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
    "发送一个问题。前端会通过 @agentscope-ai/agentscope 的 appendEvent 从 SSE 事件流重建 assistant Msg。";
  chatEl.appendChild(empty);
}

function removeEmptyHint(): void {
  document.getElementById("emptyHint")?.remove();
}

async function main(): Promise<void> {
  const { statusEl, chatEl, questionEl, sendBtn, clearBtn } = createAppShell();
  let running = false;
  let abortController: AbortController | null = null;

  ensureEmptyHint(chatEl);

  async function sendQuestion(): Promise<void> {
    const question = questionEl.value.trim();
    if (!question || running) return;

    running = true;
    sendBtn.disabled = true;
    abortController = new AbortController();
    setStatus(statusEl, "Agent 思考中...", "running");
    removeEmptyHint();

    chatEl.appendChild(renderUserBubble(question));
    questionEl.value = "";

    let assistantMsg: Msg | null = null;
    let assistantNode = renderAssistantBubble({
      id: "pending",
      name: "assistant",
      role: "assistant",
      content: [],
      metadata: {},
      created_at: new Date().toISOString(),
    });
    chatEl.appendChild(assistantNode);
    chatEl.scrollTop = chatEl.scrollHeight;

    try {
      for await (const payload of streamChatEvents({ question }, abortController.signal)) {
        if (payload.type === "WORKFLOW_START") continue;
        if (payload.type === "WORKFLOW_DONE") {
          setStatus(statusEl, "完成");
          continue;
        }
        if (payload.type === "ERROR") {
          throw new Error(payload.detail);
        }
        if (!isAgentEvent(payload)) continue;

        assistantMsg = applyEvent(assistantMsg, payload);
        if (assistantMsg) {
          assistantNode = replaceNode(assistantNode, renderAssistantBubble(assistantMsg));
          chatEl.scrollTop = chatEl.scrollHeight;
        }
      }
      if (!assistantMsg?.finished_at) {
        setStatus(statusEl, "完成");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setStatus(statusEl, `错误: ${message}`, "error");
      assistantNode = replaceNode(
        assistantNode,
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
  questionEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion();
    }
  });
}

void main();
