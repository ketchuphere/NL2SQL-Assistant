import { useEffect, useRef, useState } from "react";
import { ArrowUp, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ComposerProps {
  onSend: (text: string) => void;
  disabled?: boolean;
  hasMessages?: boolean;
}

const FOLLOWUP_PLACEHOLDERS = [
  "Now filter for last month…",
  "Group by country instead…",
  "Add a column for average order value…",
  "Only include completed orders…",
];

const INITIAL_PLACEHOLDERS = [
  "Ask anything about your database…",
  "How many active users signed up this week?",
  "Top selling products by revenue this quarter…",
  "Show daily orders for the last 14 days…",
];

export function Composer({ onSend, disabled, hasMessages }: ComposerProps) {
  const [value, setValue] = useState("");
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const ref = useRef<HTMLTextAreaElement>(null);

  // Rotate placeholder for visual interest.
  useEffect(() => {
    const id = setInterval(() => setPlaceholderIdx((i) => i + 1), 4500);
    return () => clearInterval(id);
  }, []);

  // Auto-resize
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [value]);

  const submit = () => {
    const t = value.trim();
    if (!t || disabled) return;
    onSend(t);
    setValue("");
  };

  const list = hasMessages ? FOLLOWUP_PLACEHOLDERS : INITIAL_PLACEHOLDERS;
  const placeholder = list[placeholderIdx % list.length];

  return (
    <div className="relative">
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-md transition-all",
          "focus-within:border-primary/50 focus-within:shadow-glow",
        )}
      >
        <span className="ml-2 flex h-9 w-5 shrink-0 items-center justify-center text-primary/60">
          <Sparkles className="h-4 w-4" />
        </span>
        <textarea
          ref={ref}
          rows={1}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder}
          className={cn(
            "block max-h-[200px] flex-1 resize-none bg-transparent px-1 py-2 text-sm",
            "outline-none placeholder:text-muted-foreground disabled:opacity-50",
          )}
        />
        <Button
          onClick={submit}
          disabled={disabled || !value.trim()}
          size="icon"
          className={cn(
            "h-9 w-9 shrink-0 rounded-xl transition-all",
            "bg-gradient-primary hover:opacity-90 disabled:opacity-40",
          )}
          aria-label="Send"
        >
          {disabled ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </Button>
      </div>
      <p className="mt-2 px-2 text-center text-xs text-muted-foreground">
        Press <kbd className="rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px]">Enter</kbd> to send,{" "}
        <kbd className="rounded border border-border bg-secondary px-1.5 py-0.5 font-mono text-[10px]">Shift + Enter</kbd> for newline
        {" "}• Always review SQL before running
      </p>
    </div>
  );
}
