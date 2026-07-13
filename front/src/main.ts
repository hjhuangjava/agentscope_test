import {
  streamWorkflowEvents,
  isAgentEvent,
  isWorkflowMsgEvent,
  isWorkflowDone,
  isWorkflowError,
  isWorkflowStart,
} from "./api/chatStream";
import { applyEvent } from "./message/rebuild";
import { renderAssistantBubble, renderWorkflowBubble, replaceNode } from "./ui/render";
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
          <h1>AgentScope Workflow</h1>
          <p class="subtitle">LangGraph 节点状态 · WORKFLOW_MSG + appendEvent 重建 Agent 回复</p>
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
    "发送一个问题。workflow 节点消息以 WORKFLOW_MSG 展示，Agent 回复通过 appendEvent 从事件流重建。";
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
    setStatus(statusEl, "Workflow 执行中...", "running");
    removeEmptyHint();
    questionEl.value = "";

    let assistantMsg: Msg | null = null;
    let assistantNode: HTMLElement | null = null;

    try {
      for await (const payload of streamWorkflowEvents({ question }, abortController.signal)) {
        if (isWorkflowStart(payload)) {
          setStatus(statusEl, "Workflow 已启动...", "running");
          continue;
        }
        if (isWorkflowDone(payload)) {
          setStatus(statusEl, "完成");
          continue;
        }
        if (isWorkflowError(payload)) {
          throw new Error(payload.detail);
        }
        if (isWorkflowMsgEvent(payload)) {
          chatEl.appendChild(renderWorkflowBubble(payload.node, payload.message));
          chatEl.scrollTop = chatEl.scrollHeight;
          continue;
        }
        if (!isAgentEvent(payload)) continue;

        assistantMsg = applyEvent(assistantMsg, payload);
        if (!assistantMsg) continue;

        if (!assistantNode) {
          assistantNode = renderAssistantBubble(assistantMsg);
          chatEl.appendChild(assistantNode);
        } else {
          assistantNode = replaceNode(assistantNode, renderAssistantBubble(assistantMsg));
        }
        chatEl.scrollTop = chatEl.scrollHeight;
      }
      if (!assistantMsg?.finished_at) {
        setStatus(statusEl, "完成");
      }
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
  questionEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendQuestion();
    }
  });
}

void main();
