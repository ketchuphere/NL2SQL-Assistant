import { useEffect, useMemo, useState } from "react";
import {
  ChevronRight, Database, KeyRound, Link2,
  Loader2, RefreshCw, Search, Table2,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { fetchDatabaseSchema, type DatabaseInfo } from "@/lib/api";
import { useAssistant } from "@/store/assistant";
import { cn } from "@/lib/utils";

export function SchemaExplorer() {
  const send = useAssistant((s) => s.send);
  const [query, setQuery] = useState("");
  const [openTable, setOpenTable] = useState<string | null>(null);
  const [dbInfo, setDbInfo] = useState<DatabaseInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSchema = async () => {
    setLoading(true);
    setError(null);
    try {
      const info = await fetchDatabaseSchema();
      setDbInfo(info);
    } catch {
      setError("Could not load schema. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSchema(); }, []);

  const tables = dbInfo?.tables ?? [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tables;
    return tables
      .map((t) => {
        if (t.name.toLowerCase().includes(q)) return t;
        const matchedCols = t.columns.filter((c) => c.name.toLowerCase().includes(q));
        return matchedCols.length ? { ...t, columns: matchedCols } : null;
      })
      .filter(Boolean) as typeof tables;
  }, [query, tables]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-1.5 px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        <Database className="h-3 w-3" />
        Schema
        <span className="ml-auto flex items-center gap-1 text-[10px] font-normal normal-case tracking-normal">
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <>
              <span className={cn("h-1.5 w-1.5 rounded-full", dbInfo?.status === "connected" ? "bg-green-500" : "bg-red-400")} />
              {tables.length} tables
            </>
          )}
          <button onClick={loadSchema} className="ml-1 rounded p-0.5 hover:bg-sidebar-accent/60" title="Refresh schema">
            <RefreshCw className="h-2.5 w-2.5" />
          </button>
        </span>
      </div>

      {/* Search */}
      <div className="relative px-2 pb-2">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search tables and columns…"
          className="h-7 pl-7 text-xs"
        />
      </div>

      {error && <p className="px-2 py-3 text-xs text-destructive">{error}</p>}

      {loading && !error && (
        <div className="space-y-1 px-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-7 animate-pulse rounded-lg bg-sidebar-accent/40" />
          ))}
        </div>
      )}

      {!loading && !error && tables.length === 0 && (
        <p className="px-2 py-3 text-xs text-muted-foreground">
          No schema indexed yet.{" "}
          <span className="font-mono text-foreground">POST /api/v1/documents/index</span>{" "}
          to index your database.
        </p>
      )}

      {!loading && !error && (
        <ul className="space-y-0.5">
          {filtered.map((t) => {
            const open = openTable === `${t.schema}.${t.name}`;
            return (
              <li key={`${t.schema}.${t.name}`}>
                <button
                  onClick={() => setOpenTable(open ? null : `${t.schema}.${t.name}`)}
                  className={cn(
                    "flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-sidebar-accent/60",
                    open && "bg-sidebar-accent/60",
                  )}
                >
                  <ChevronRight className={cn("h-3 w-3 shrink-0 text-muted-foreground transition-transform", open && "rotate-90")} />
                  <Table2 className="h-3.5 w-3.5 shrink-0 text-primary/80" />
                  <span className="flex-1 truncate font-mono text-xs">{t.name}</span>
                  <span className="text-[10px] tabular-nums text-muted-foreground">{t.schema}</span>
                </button>

                {open && (
                  <div className="ml-5 mt-0.5 space-y-0.5 border-l border-sidebar-border pl-2">
                    {t.columns.map((c) => (
                      <div key={c.name} className="flex items-center gap-1.5 rounded px-1.5 py-1 text-[11px]">
                        {c.pk ? (
                          <KeyRound className="h-2.5 w-2.5 shrink-0 text-warning" />
                        ) : c.fk ? (
                          <Link2 className="h-2.5 w-2.5 shrink-0 text-primary/70" />
                        ) : (
                          <span className="h-2.5 w-2.5 shrink-0" />
                        )}
                        <span className="truncate font-mono text-foreground/90">{c.name}</span>
                        <span className="ml-auto font-mono text-[10px] text-muted-foreground">{c.type}</span>
                        {c.fk && (
                          <span className="ml-1 truncate text-[10px] text-primary/60" title={`FK → ${c.fk}`}>
                            → {c.fk}
                          </span>
                        )}
                      </div>
                    ))}
                    <button
                      onClick={() => send(`Show me 10 sample rows from ${t.schema}.${t.name}`)}
                      className="my-1 w-full rounded px-1.5 py-1 text-left text-[11px] text-primary hover:bg-accent/40"
                    >
                      → Query this table
                    </button>
                  </div>
                )}
              </li>
            );
          })}
          {filtered.length === 0 && tables.length > 0 && (
            <p className="px-2 py-3 text-xs text-muted-foreground">No matching tables or columns.</p>
          )}
        </ul>
      )}
    </div>
  );
}
