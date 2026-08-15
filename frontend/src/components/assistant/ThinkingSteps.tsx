import { Brain, Check, Database, Loader2, Sparkles, Zap } from "lucide-react";
import type { ThinkingStage } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ThinkingStepsProps {
  stage: ThinkingStage | undefined;
}

const STEPS: {
  key: Exclude<ThinkingStage, "done">;
  label: string;
  icon: React.ElementType;
}[] = [
  { key: "understanding", label: "Understanding your question", icon: Brain },
  { key: "schema", label: "Inspecting database schema", icon: Database },
  { key: "generating", label: "Generating SQL", icon: Sparkles },
  { key: "executing", label: "Running query", icon: Zap },
];

const order: ThinkingStage[] = ["understanding", "schema", "generating", "executing", "done"];

export function ThinkingSteps({ stage }: ThinkingStepsProps) {
  const currentIdx = stage ? order.indexOf(stage) : 0;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card p-3 shadow-sm">
      <ul className="space-y-1.5">
        {STEPS.map((step, idx) => {
          const done = currentIdx > idx;
          const active = currentIdx === idx;
          const Icon = step.icon;
          return (
            <li
              key={step.key}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-xs transition-all duration-300",
                active && "bg-accent/40",
                !active && !done && "opacity-40",
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full transition-colors",
                  done && "bg-success/15 text-success",
                  active && "bg-primary/15 text-primary",
                  !done && !active && "bg-muted text-muted-foreground",
                )}
              >
                {done ? (
                  <Check className="h-3 w-3" />
                ) : active ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Icon className="h-3 w-3" />
                )}
              </span>
              <span
                className={cn(
                  "font-medium",
                  active ? "text-foreground" : done ? "text-muted-foreground" : "text-muted-foreground",
                )}
              >
                {step.label}
              </span>
              {active && (
                <span className="ml-auto flex items-center gap-1 text-muted-foreground">
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                  <span className="thinking-dot" />
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
