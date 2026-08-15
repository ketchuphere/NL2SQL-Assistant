import { useEffect, useRef, useState } from "react";
import { BarChart3, Database, Menu, Moon, Search, Sun, TrendingUp, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { useAssistant } from "@/store/assistant";
import { Sidebar } from "@/components/assistant/Sidebar";
import { Composer } from "@/components/assistant/Composer";
import { MessageBubble } from "@/components/assistant/MessageBubble";
import { DbStatus } from "@/components/assistant/DbStatus";

const SUGGESTIONS: { icon: React.ElementType; title: string; prompt: string; hint: string }[] = [
  {
    icon: Users,
    title: "Top customers",
    prompt: "Show me top 10 customers by revenue in the last 30 days",
    hint: "Aggregation • JOIN",
  },
  {
    icon: TrendingUp,
    title: "Daily order trend",
    prompt: "Show me daily orders and revenue over the last 14 days",
    hint: "Time series • Auto chart",
  },
  {
    icon: Search,
    title: "Explore the schema",
    prompt: "What tables and columns exist in the public schema?",
    hint: "Metadata",
  },
  {
    icon: BarChart3,
    title: "High-value orders",
    prompt: "Find orders with total greater than $1000 last week",
    hint: "Filtering",
  },
];

function EmptyState({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center justify-center px-4 py-12 text-center">
      <div className="relative mb-6">
        <div className="absolute inset-0 -z-10 bg-gradient-glow blur-3xl" aria-hidden />
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-primary shadow-glow">
          <Database className="h-7 w-7 text-primary-foreground" />
        </div>
      </div>
      <h1 className="text-balance text-3xl font-semibold tracking-tight">
        Query your database in plain English
      </h1>
      <p className="mt-3 max-w-md text-balance text-sm text-muted-foreground">
        Ask a question and I'll generate SQL, run it, and explain the results. Refine with
        follow-ups like <span className="font-mono text-foreground">"now filter for last month"</span>.
      </p>

      <div className="mt-8 grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => {
          const Icon = s.icon;
          return (
            <button
              key={s.title}
              onClick={() => onPick(s.prompt)}
              className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-accent-foreground transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <span className="text-sm font-semibold">{s.title}</span>
                <span className="ml-auto text-[10px] uppercase tracking-wider text-muted-foreground">
                  {s.hint}
                </span>
              </div>
              <span className="text-xs text-muted-foreground transition-colors group-hover:text-foreground">
                {s.prompt}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ChatView() {
  const active = useAssistant((s) => s.active());
  const send = useAssistant((s) => s.send);
  const theme = useAssistant((s) => s.theme);
  const toggleTheme = useAssistant((s) => s.toggleTheme);
  const newConversation = useAssistant((s) => s.newConversation);

  const scrollRef = useRef<HTMLDivElement>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  const messages = active?.messages ?? [];
  const isLoading = messages.some((m) => m.isLoading);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, isLoading]);

  const handleSend = (text: string) => {
    if (!active) newConversation();
    send(text);
  };

  return (
    <div className="flex h-full">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex">
        <Sidebar />
      </div>

      {/* Mobile sidebar */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-[300px] border-r-0 p-0">
          <Sidebar onClose={() => setMobileOpen(false)} className="w-full" />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col bg-gradient-surface">
        {/* Top bar */}
        <header className="flex h-14 items-center justify-between border-b border-border bg-background/60 px-4 backdrop-blur">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-4 w-4" />
            </Button>
            <div className="text-sm">
              <span className="font-semibold">{active?.title ?? "New conversation"}</span>
              {active && active.messages.length > 0 && (
                <span className="ml-2 text-xs text-muted-foreground">
                  {active.messages.length} {active.messages.length === 1 ? "message" : "messages"}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <DbStatus />
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              className="h-9 w-9"
              aria-label="Toggle theme"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
          </div>
        </header>

        {/* Scrollable messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin">
          {messages.length === 0 ? (
            <EmptyState onPick={handleSend} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-6 px-4 py-8">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-border bg-background/60 px-4 py-4 backdrop-blur">
          <div className="mx-auto max-w-3xl">
            <Composer
              onSend={handleSend}
              disabled={isLoading}
              hasMessages={messages.length > 0}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
