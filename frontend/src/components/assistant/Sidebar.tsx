import { Bookmark, MessageSquare, Plus, Sparkles, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useAssistant } from "@/store/assistant";
import { cn } from "@/lib/utils";
import { SchemaExplorer } from "./SchemaExplorer";

interface SidebarProps {
  onClose?: () => void;
  className?: string;
}

function timeAgo(ts: number) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export function Sidebar({ onClose, className }: SidebarProps) {
  const conversations = useAssistant((s) => s.conversations);
  const activeId = useAssistant((s) => s.activeId);
  const saved = useAssistant((s) => s.saved);
  const newConversation = useAssistant((s) => s.newConversation);
  const selectConversation = useAssistant((s) => s.selectConversation);
  const deleteConversation = useAssistant((s) => s.deleteConversation);
  const removeSaved = useAssistant((s) => s.removeSaved);
  const send = useAssistant((s) => s.send);

  return (
    <aside
      className={cn(
        "flex h-full w-[300px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground",
        className,
      )}
    >
      {/* Brand */}
      <div className="flex h-14 items-center justify-between gap-2 px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-primary shadow-glow">
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </div>
          <span className="text-sm font-semibold tracking-tight">SQL Assistant</span>
        </div>
        {onClose && (
          <Button variant="ghost" size="icon" className="h-8 w-8 lg:hidden" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      <div className="px-3 pb-2">
        <Button
          onClick={() => {
            newConversation();
            onClose?.();
          }}
          className="w-full justify-start gap-2 bg-gradient-primary text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          New conversation
        </Button>
      </div>

      <ScrollArea className="flex-1 px-2">
        <div className="space-y-4 py-2">
          {/* Schema explorer */}
          <SchemaExplorer />

          {/* History */}
          <div>
            <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              History
            </div>
            {conversations.length === 0 ? (
              <p className="px-2 py-3 text-xs text-muted-foreground">
                Your conversations will appear here.
              </p>
            ) : (
              <ul className="space-y-0.5">
                {conversations.map((c) => {
                  const active = c.id === activeId;
                  return (
                    <li key={c.id} className="group relative">
                      <button
                        onClick={() => {
                          selectConversation(c.id);
                          onClose?.();
                        }}
                        className={cn(
                          "flex w-full items-start gap-2 rounded-lg px-2 py-2 pr-8 text-left transition-colors",
                          active
                            ? "bg-sidebar-accent text-sidebar-accent-foreground"
                            : "hover:bg-sidebar-accent/60",
                        )}
                      >
                        <MessageSquare
                          className={cn(
                            "mt-0.5 h-3.5 w-3.5 shrink-0",
                            active ? "text-primary" : "text-muted-foreground",
                          )}
                        />
                        <div className="flex min-w-0 flex-1 flex-col">
                          <span className="truncate text-xs font-medium">{c.title}</span>
                          <span className="text-[10px] text-muted-foreground">
                            {timeAgo(c.updatedAt)} • {c.messages.length}{" "}
                            {c.messages.length === 1 ? "msg" : "msgs"}
                          </span>
                        </div>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteConversation(c.id);
                        }}
                        className="absolute right-1.5 top-2 hidden rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive group-hover:inline-flex"
                        aria-label="Delete conversation"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {/* Saved */}
          <div>
            <div className="flex items-center gap-1.5 px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              <Bookmark className="h-3 w-3" />
              Favorites
            </div>
            {saved.length === 0 ? (
              <p className="px-2 py-3 text-xs text-muted-foreground">
                Save queries to reuse them later.
              </p>
            ) : (
              <ul className="space-y-0.5">
                {saved.map((q) => (
                  <li key={q.id} className="group">
                    <div
                      className={cn(
                        "flex items-start gap-2 rounded-lg px-2 py-2 transition-colors hover:bg-sidebar-accent/60",
                      )}
                    >
                      <button
                        onClick={() => {
                          send(`Run this query: ${q.title}`);
                          onClose?.();
                        }}
                        className="flex-1 truncate text-left text-xs font-medium"
                        title={q.sql}
                      >
                        {q.title}
                      </button>
                      <button
                        onClick={() => removeSaved(q.id)}
                        className="opacity-0 transition-opacity group-hover:opacity-100"
                        aria-label="Remove favorite"
                      >
                        <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </ScrollArea>

      <div className="border-t border-sidebar-border px-4 py-3">
        <p className="text-[11px] text-muted-foreground">
          Powered by AI. Always review SQL before running on production.
        </p>
      </div>
    </aside>
  );
}
