import { CornerDownRight } from "lucide-react";
import { useAssistant } from "@/store/assistant";

interface FollowUpChipsProps {
  suggestions: string[];
}

export function FollowUpChips({ suggestions }: FollowUpChipsProps) {
  const send = useAssistant((s) => s.send);
  if (!suggestions.length) return null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        <CornerDownRight className="h-3 w-3" />
        Suggested follow-ups
      </div>
      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => send(s)}
            className="group inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1.5 text-xs text-foreground/80 shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-accent/40 hover:text-foreground hover:shadow-md"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
