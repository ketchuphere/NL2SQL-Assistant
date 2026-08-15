import { ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ConfidenceBadgeProps {
  value: number; // 0..1
}

export function ConfidenceBadge({ value }: ConfidenceBadgeProps) {
  const pct = Math.round(value * 100);
  const tone =
    pct >= 90
      ? "bg-success/10 text-success border-success/20"
      : pct >= 70
        ? "bg-primary/10 text-primary border-primary/20"
        : "bg-warning/10 text-warning border-warning/20";
  const label = pct >= 90 ? "High confidence" : pct >= 70 ? "Good confidence" : "Low confidence";

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium",
              tone,
            )}
          >
            <ShieldCheck className="h-3 w-3" />
            {pct}%
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="text-xs">
          {label} — based on schema match and prompt clarity.
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
