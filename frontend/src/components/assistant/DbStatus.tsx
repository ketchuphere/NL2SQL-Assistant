import { useEffect, useState } from "react";
import { Database, Loader2, Server, Table2 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { fetchDatabaseSchema, type DatabaseInfo } from "@/lib/api";
import { cn } from "@/lib/utils";

export function DbStatus() {
  const [dbInfo, setDbInfo] = useState<DatabaseInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDatabaseSchema()
      .then(setDbInfo)
      .catch(() => setDbInfo(null))
      .finally(() => setLoading(false));
  }, []);

  const connected = dbInfo?.status === "connected";
  const displayName = dbInfo?.name ?? "Database";
  const tableCount = dbInfo?.tables.length ?? 0;
  const vectorCount = dbInfo?.vectorCount ?? 0;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="hidden items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs transition-colors hover:bg-accent/40 sm:inline-flex">
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
          ) : (
            <span className="relative flex h-1.5 w-1.5">
              <span className={cn("absolute inset-0 animate-ping rounded-full", connected ? "bg-green-500/70" : "bg-red-400/70")} />
              <span className={cn("relative h-1.5 w-1.5 rounded-full", connected ? "bg-green-500" : "bg-red-400")} />
            </span>
          )}
          <span className="font-medium text-foreground">{displayName}</span>
          {!loading && <span className="text-muted-foreground">• {tableCount} tables</span>}
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-72 p-0">
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-primary">
              <Database className="h-4 w-4 text-primary-foreground" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{displayName}</div>
              <div className="text-[11px] text-muted-foreground">{dbInfo?.engine ?? "—"}</div>
            </div>
            <span className={cn(
              "ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              connected ? "bg-green-500/10 text-green-600 dark:text-green-400" : "bg-red-500/10 text-red-500",
            )}>
              <span className={cn("h-1 w-1 rounded-full", connected ? "bg-green-500" : "bg-red-400")} />
              {connected ? "Live" : "Offline"}
            </span>
          </div>
        </div>

        <div className="space-y-2 px-4 py-3 text-xs">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Server className="h-3.5 w-3.5" />
            <span className="truncate font-mono text-[11px]">{dbInfo?.host ?? "—"}</span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Table2 className="h-3.5 w-3.5" />
            <span>
              <span className="font-medium text-foreground">{tableCount}</span> tables •{" "}
              <span className="font-medium text-foreground">{vectorCount.toLocaleString()}</span> vectors indexed
            </span>
          </div>
        </div>

        {!connected && !loading && (
          <div className="border-t border-border bg-destructive/5 px-4 py-2 text-[11px] text-destructive">
            Run <span className="font-mono">make index-schema</span> or call{" "}
            <span className="font-mono">POST /api/v1/documents/index</span> to connect.
          </div>
        )}
        {connected && (
          <div className="border-t border-border bg-muted/30 px-4 py-2 text-[11px] text-muted-foreground">
            Browse the schema explorer in the sidebar to inspect columns.
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
