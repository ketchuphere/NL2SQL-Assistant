import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SqlResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ResultsTableProps {
  result: SqlResult;
  durationMs?: number;
}

const PAGE_SIZE = 8;

type SortDir = "asc" | "desc" | null;

export function ResultsTable({ result, durationMs }: ResultsTableProps) {
  const { columns, rows } = result;
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    if (sortCol === null || sortDir === null) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortCol];
      const bv = b[sortCol];
      if (av === null) return 1;
      if (bv === null) return -1;
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return copy;
  }, [rows, sortCol, sortDir]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = sorted.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  const cycleSort = (idx: number) => {
    if (sortCol !== idx) {
      setSortCol(idx);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortCol(null);
      setSortDir(null);
    }
  };

  const exportCsv = () => {
    const escape = (v: unknown) => {
      const s = v === null || v === undefined ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [
      columns.map(escape).join(","),
      ...sorted.map((r) => r.map(escape).join(",")),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "results.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b border-border bg-surface px-4 py-2.5">
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            {rows.length} {rows.length === 1 ? "row" : "rows"}
          </span>
          {typeof durationMs === "number" && (
            <>
              <span className="text-border">•</span>
              <span>{durationMs} ms</span>
            </>
          )}
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={exportCsv}
          className="h-7 gap-1.5 px-2 text-xs"
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </Button>
      </div>

      <div className="overflow-x-auto scrollbar-thin">
        <Table>
          <TableHeader>
            <TableRow className="bg-surface/60 hover:bg-surface/60">
              {columns.map((col, idx) => {
                const active = sortCol === idx;
                return (
                  <TableHead key={col} className="h-10">
                    <button
                      onClick={() => cycleSort(idx)}
                      className={cn(
                        "group inline-flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider transition-colors",
                        active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {col}
                      {active && sortDir === "asc" && <ArrowUp className="h-3 w-3" />}
                      {active && sortDir === "desc" && <ArrowDown className="h-3 w-3" />}
                      {!active && (
                        <ArrowUpDown className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-50" />
                      )}
                    </button>
                  </TableHead>
                );
              })}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((row, rIdx) => (
              <TableRow key={rIdx} className="hover:bg-surface/50">
                {row.map((cell, cIdx) => (
                  <TableCell
                    key={cIdx}
                    className={cn(
                      "py-2.5 text-sm",
                      typeof cell === "number" && "font-mono tabular-nums",
                      cell === null && "text-muted-foreground italic",
                    )}
                  >
                    {cell === null ? "NULL" : typeof cell === "number" ? cell.toLocaleString() : String(cell)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center justify-between border-t border-border bg-surface px-4 py-2 text-xs text-muted-foreground">
          <span>
            Page {safePage + 1} of {pageCount}
          </span>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="sm"
              disabled={safePage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="h-7 px-2 text-xs"
            >
              Prev
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
              className="h-7 px-2 text-xs"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
