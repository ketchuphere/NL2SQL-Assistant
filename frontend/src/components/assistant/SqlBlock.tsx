import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SqlBlockProps {
  sql: string;
  editable?: boolean;
  onChange?: (sql: string) => void;
}

export function SqlBlock({ sql, editable = false, onChange }: SqlBlockProps) {
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(sql);

  const copy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const startEdit = () => {
    setDraft(sql);
    setEditing(true);
  };
  const save = () => {
    onChange?.(draft);
    setEditing(false);
  };
  const cancel = () => {
    setDraft(sql);
    setEditing(false);
  };

  return (
    <div className="group relative overflow-hidden rounded-xl border border-border/60 bg-[hsl(var(--code-bg))] shadow-sm">
      <div className="flex items-center justify-between border-b border-white/5 px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-destructive/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-warning/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-success/70" />
          <span className="ml-3 font-mono text-xs uppercase tracking-wider text-white/40">
            SQL
          </span>
        </div>
        <div className="flex items-center gap-1">
          {editable && !editing && (
            <Button
              variant="ghost"
              size="sm"
              onClick={startEdit}
              className="h-7 px-2 text-xs text-white/70 hover:bg-white/10 hover:text-white"
            >
              Edit
            </Button>
          )}
          {editing && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={cancel}
                className="h-7 px-2 text-xs text-white/70 hover:bg-white/10 hover:text-white"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={save}
                className="h-7 px-2 text-xs"
              >
                Save
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={copy}
            className="h-7 gap-1.5 px-2 text-xs text-white/70 hover:bg-white/10 hover:text-white"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5" /> Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" /> Copy
              </>
            )}
          </Button>
        </div>
      </div>

      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          className={cn(
            "block w-full resize-y bg-transparent px-4 py-4 font-mono text-sm leading-relaxed text-[hsl(var(--code-fg))]",
            "min-h-[160px] outline-none focus:ring-0",
          )}
        />
      ) : (
        <div className="overflow-x-auto scrollbar-thin">
          <SyntaxHighlighter
            language="sql"
            style={oneDark}
            customStyle={{
              margin: 0,
              padding: "1rem 1rem",
              background: "transparent",
              fontSize: "0.875rem",
              lineHeight: "1.6",
            }}
            codeTagProps={{
              style: { fontFamily: "JetBrains Mono, ui-monospace, monospace" },
            }}
          >
            {sql}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  );
}
