import { useState } from "react";
import { AlertCircle, Bookmark, Sparkles, ThumbsDown, ThumbsUp, User, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAssistant } from "@/store/assistant";
import type { ChatMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SqlBlock } from "./SqlBlock";
import { ResultsTable } from "./ResultsTable";
import { ExplanationPanel } from "./ExplanationPanel";
import { ThinkingSteps } from "./ThinkingSteps";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { FollowUpChips } from "./FollowUpChips";
import { ResultChart, detectChartable } from "./ResultChart";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const editAssistantSql = useAssistant((s) => s.editAssistantSql);
  const setFeedback = useAssistant((s) => s.setFeedback);
  const saveQuery = useAssistant((s) => s.saveQuery);
  const send = useAssistant((s) => s.send);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveTitle, setSaveTitle] = useState("");

  if (message.role === "user") {
    return (
      <div className="flex animate-fade-in-up justify-end gap-3">
        <div className="max-w-[85%] rounded-2xl rounded-tr-md bg-gradient-primary px-4 py-2.5 text-primary-foreground shadow-md">
          <p className="text-sm leading-relaxed">{message.content}</p>
        </div>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
          <User className="h-4 w-4" />
        </div>
      </div>
    );
  }

  const chartable = message.payload ? detectChartable(message.payload.result).chartable : false;

  return (
    <div className="flex animate-fade-in-up gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-primary text-primary-foreground shadow-glow">
        <Sparkles className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        {message.isLoading && <ThinkingSteps stage={message.stage} />}

        {message.error && (
          <div className="space-y-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4">
            <div className="flex items-start gap-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <div className="font-medium">Couldn't generate a query</div>
                <div className="mt-0.5 text-xs text-destructive/80">{message.error}</div>
              </div>
            </div>
            {message.errorFix && (
              <div className="flex items-start gap-2 rounded-lg border border-border bg-card p-3 text-xs">
                <Wand2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                <div className="flex-1">
                  <div className="font-medium text-foreground">Suggested fix</div>
                  <div className="mt-0.5 text-muted-foreground">{message.errorFix}</div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-[11px]"
                  onClick={() => send("Try again — list available tables first")}
                >
                  Retry
                </Button>
              </div>
            )}
          </div>
        )}

        {message.payload && (
          <>
            <div className="flex flex-wrap items-center gap-2">
              {message.content && (
                <p className="text-sm text-muted-foreground">{message.content}</p>
              )}
              <ConfidenceBadge value={message.payload.confidence} />
              {message.payload.tablesUsed.map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center rounded-full border border-border bg-secondary px-2 py-0.5 font-mono text-[11px] text-muted-foreground"
                >
                  {t}
                </span>
              ))}
            </div>

            <SqlBlock
              sql={message.payload.sql}
              editable
              onChange={(sql) => editAssistantSql(message.id, sql)}
            />

            <ResultsTable
              result={message.payload.result}
              durationMs={message.payload.durationMs}
            />

            {chartable && <ResultChart result={message.payload.result} />}

            <ExplanationPanel text={message.payload.explanation} />

            <FollowUpChips suggestions={message.payload.followUps} />

            <div className="flex items-center gap-1 pt-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFeedback(message.id, "up")}
                className={cn(
                  "h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground",
                  message.feedback === "up" && "bg-success/10 text-success hover:text-success",
                )}
              >
                <ThumbsUp className="h-3.5 w-3.5" />
                Helpful
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setFeedback(message.id, "down")}
                className={cn(
                  "h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground",
                  message.feedback === "down" && "bg-destructive/10 text-destructive hover:text-destructive",
                )}
              >
                <ThumbsDown className="h-3.5 w-3.5" />
                Not helpful
              </Button>
              <div className="mx-1 h-4 w-px bg-border" />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSaveTitle("");
                  setSaveOpen(true);
                }}
                className="h-8 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
              >
                <Bookmark className="h-3.5 w-3.5" />
                Save query
              </Button>
            </div>

            <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Save query</DialogTitle>
                </DialogHeader>
                <div className="space-y-2">
                  <Label htmlFor="save-title">Title</Label>
                  <Input
                    id="save-title"
                    value={saveTitle}
                    onChange={(e) => setSaveTitle(e.target.value)}
                    placeholder="e.g. Top customers — last 30 days"
                    autoFocus
                  />
                </div>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setSaveOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      saveQuery(saveTitle.trim() || "Untitled query", message.payload!.sql);
                      setSaveOpen(false);
                    }}
                  >
                    Save
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        )}
      </div>
    </div>
  );
}
