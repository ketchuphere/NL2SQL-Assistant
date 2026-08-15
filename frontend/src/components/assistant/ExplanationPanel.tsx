import { useState } from "react";
import { ChevronDown, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";

interface ExplanationProps {
  text: string;
  defaultOpen?: boolean;
}

// Tiny inline-markdown renderer: **bold** and `code`. Safe — no HTML injection.
function renderInline(text: string) {
  const parts: (string | JSX.Element)[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      parts.push(<strong key={key++} className="font-semibold text-foreground">{tok.slice(2, -2)}</strong>);
    } else {
      parts.push(
        <code
          key={key++}
          className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[0.85em] text-foreground"
        >
          {tok.slice(1, -1)}
        </code>,
      );
    }
    last = m.index + tok.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export function ExplanationPanel({ text, defaultOpen = true }: ExplanationProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-accent/40">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-accent/60"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-accent-foreground">
          <Lightbulb className="h-4 w-4" />
          Explanation
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
      </button>
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-smooth",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <p className="px-4 pb-4 text-sm leading-relaxed text-muted-foreground">
            {renderInline(text)}
          </p>
        </div>
      </div>
    </div>
  );
}
