import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  askAssistant,
  sendFeedback,
  type ChatMessage,
  type Conversation,
  type Feedback,
  type SavedQuery,
} from "@/lib/api";

const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

function deriveTitle(text: string) {
  const t = text.trim().replace(/\s+/g, " ");
  return t.length > 48 ? t.slice(0, 48) + "…" : t || "Untitled query";
}

interface AssistantState {
  conversations: Conversation[];
  activeId: string | null;
  saved: SavedQuery[];
  theme: "light" | "dark";
  sidebarOpen: boolean;

  active: () => Conversation | null;
  newConversation: () => void;
  selectConversation: (id: string) => void;
  deleteConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;
  send: (prompt: string) => Promise<void>;
  editAssistantSql: (messageId: string, sql: string) => void;
  setFeedback: (messageId: string, value: Exclude<Feedback, null>) => Promise<void>;
  saveQuery: (title: string, sql: string) => void;
  removeSaved: (id: string) => void;
  toggleTheme: () => void;
  toggleSidebar: () => void;
}

export const useAssistant = create<AssistantState>()(
  persist(
    (set, get) => ({
      conversations: [],
      activeId: null,
      saved: [],
      theme: "light",
      sidebarOpen: true,

      active: () => {
        const { conversations, activeId } = get();
        return conversations.find((c) => c.id === activeId) ?? null;
      },

      newConversation: () => {
        const id = uid();
        const conv: Conversation = {
          id,
          title: "New conversation",
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
          sessionId: undefined,
        };
        set((s) => ({ conversations: [conv, ...s.conversations], activeId: id }));
      },

      selectConversation: (id) => set({ activeId: id }),

      deleteConversation: (id) =>
        set((s) => {
          const remaining = s.conversations.filter((c) => c.id !== id);
          return {
            conversations: remaining,
            activeId: s.activeId === id ? remaining[0]?.id ?? null : s.activeId,
          };
        }),

      renameConversation: (id, title) =>
        set((s) => ({
          conversations: s.conversations.map((c) => (c.id === id ? { ...c, title } : c)),
        })),

      send: async (prompt) => {
        let { activeId } = get();
        if (!activeId) {
          get().newConversation();
          activeId = get().activeId!;
        }

        const userMsg: ChatMessage = {
          id: uid(), role: "user", content: prompt, createdAt: Date.now(),
        };
        const loadingMsg: ChatMessage = {
          id: uid(), role: "assistant", content: "", createdAt: Date.now(),
          isLoading: true, stage: "understanding",
        };

        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === activeId
              ? {
                  ...c,
                  title: c.messages.length === 0 ? deriveTitle(prompt) : c.title,
                  messages: [...c.messages, userMsg, loadingMsg],
                  updatedAt: Date.now(),
                }
              : c,
          ),
        }));

        const updateStage = (stage: ChatMessage["stage"]) =>
          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === activeId
                ? { ...c, messages: c.messages.map((m) => m.id === loadingMsg.id ? { ...m, stage } : m) }
                : c,
            ),
          }));

        const stageTimers = [
          setTimeout(() => updateStage("schema"), 400),
          setTimeout(() => updateStage("generating"), 900),
          setTimeout(() => updateStage("executing"), 1500),
        ];

        try {
          const conv = get().conversations.find((c) => c.id === activeId)!;
          const history = conv.messages.filter((m) => !m.isLoading);
          const sessionId = conv.sessionId;

          const payload = await askAssistant(prompt, history, sessionId);
          stageTimers.forEach(clearTimeout);

          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === activeId
                ? {
                    ...c,
                    // Persist session ID for multi-turn conversation
                    sessionId: payload.sessionId || c.sessionId,
                    messages: c.messages.map((m) =>
                      m.id === loadingMsg.id
                        ? { ...m, isLoading: false, stage: "done", content: "Here's what I found:", payload }
                        : m,
                    ),
                    updatedAt: Date.now(),
                  }
                : c,
            ),
          }));
        } catch (err) {
          stageTimers.forEach(clearTimeout);
          const msg = err instanceof Error ? err.message : "Something went wrong";
          set((s) => ({
            conversations: s.conversations.map((c) =>
              c.id === activeId
                ? {
                    ...c,
                    messages: c.messages.map((m) =>
                      m.id === loadingMsg.id
                        ? {
                            ...m, isLoading: false, stage: undefined, content: "",
                            error: msg,
                            errorFix: "Try rephrasing your question or check that the referenced tables exist in the connected database.",
                          }
                        : m,
                    ),
                  }
                : c,
            ),
          }));
        }
      },

      editAssistantSql: (messageId, sql) =>
        set((s) => ({
          conversations: s.conversations.map((c) => ({
            ...c,
            messages: c.messages.map((m) =>
              m.id === messageId && m.payload ? { ...m, payload: { ...m.payload, sql } } : m,
            ),
          })),
        })),

      setFeedback: async (messageId, value) => {
        set((s) => ({
          conversations: s.conversations.map((c) => ({
            ...c,
            messages: c.messages.map((m) => m.id === messageId ? { ...m, feedback: value } : m),
          })),
        }));
        try { await sendFeedback(messageId, value); } catch { /* optimistic */ }
      },

      saveQuery: (title, sql) =>
        set((s) => ({
          saved: [{ id: uid(), title: title || "Untitled query", sql, createdAt: Date.now() }, ...s.saved],
        })),

      removeSaved: (id) => set((s) => ({ saved: s.saved.filter((q) => q.id !== id) })),

      toggleTheme: () => {
        const next = get().theme === "light" ? "dark" : "light";
        document.documentElement.classList.toggle("dark", next === "dark");
        set({ theme: next });
      },

      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    {
      name: "nl2sql-assistant",
      partialize: (s) => ({
        conversations: s.conversations,
        activeId: s.activeId,
        saved: s.saved,
        theme: s.theme,
        sidebarOpen: s.sidebarOpen,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.theme === "dark") document.documentElement.classList.add("dark");
      },
    },
  ),
);
