import { useMemo, useState } from "react";
import { BarChart3, LineChart as LineIcon, Table as TableIcon } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SqlResult } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ResultChartProps {
  result: SqlResult;
}

/** Detect whether a result set is chartable: 1 label column + ≥1 numeric column. */
export function detectChartable(result: SqlResult): {
  chartable: boolean;
  labelIdx: number;
  numericIdxs: number[];
  isTimeSeries: boolean;
} {
  const { columns, rows } = result;
  if (rows.length < 2 || rows.length > 200 || columns.length < 2) {
    return { chartable: false, labelIdx: -1, numericIdxs: [], isTimeSeries: false };
  }
  const numericIdxs: number[] = [];
  let labelIdx = -1;
  for (let i = 0; i < columns.length; i++) {
    const col = rows.map((r) => r[i]);
    const allNumeric = col.every((v) => typeof v === "number");
    if (allNumeric) numericIdxs.push(i);
    else if (labelIdx === -1) labelIdx = i;
  }
  if (labelIdx === -1 || numericIdxs.length === 0) {
    return { chartable: false, labelIdx: -1, numericIdxs: [], isTimeSeries: false };
  }
  const labelName = columns[labelIdx].toLowerCase();
  const isTimeSeries =
    labelName.includes("date") ||
    labelName.includes("day") ||
    labelName.includes("month") ||
    labelName.includes("week") ||
    labelName.includes("hour") ||
    labelName.includes("time");
  return { chartable: true, labelIdx, numericIdxs, isTimeSeries };
}

const CHART_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--primary-glow))",
  "hsl(var(--success))",
];

export function ResultChart({ result }: ResultChartProps) {
  const { columns, rows } = result;
  const meta = useMemo(() => detectChartable(result), [result]);
  const [type, setType] = useState<"bar" | "line">(meta.isTimeSeries ? "line" : "bar");

  if (!meta.chartable) return null;

  const data = rows.map((r) => {
    const obj: Record<string, string | number> = { __label: String(r[meta.labelIdx]) };
    meta.numericIdxs.forEach((idx) => {
      obj[columns[idx]] = r[idx] as number;
    });
    return obj;
  });

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2 text-xs">
          <BarChart3 className="h-3.5 w-3.5 text-primary" />
          <span className="font-medium text-foreground">Auto-visualization</span>
          <span className="text-muted-foreground">
            • {columns[meta.labelIdx]} × {meta.numericIdxs.map((i) => columns[i]).join(", ")}
          </span>
        </div>
        <div className="flex items-center gap-0.5 rounded-lg border border-border bg-secondary p-0.5">
          <button
            onClick={() => setType("bar")}
            className={cn(
              "flex h-6 items-center gap-1 rounded px-2 text-[11px] font-medium transition-colors",
              type === "bar"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <BarChart3 className="h-3 w-3" /> Bar
          </button>
          <button
            onClick={() => setType("line")}
            className={cn(
              "flex h-6 items-center gap-1 rounded px-2 text-[11px] font-medium transition-colors",
              type === "line"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <LineIcon className="h-3 w-3" /> Line
          </button>
        </div>
      </div>
      <div className="h-64 w-full p-3">
        <ResponsiveContainer width="100%" height="100%">
          {type === "bar" ? (
            <BarChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis
                dataKey="__label"
                stroke="hsl(var(--muted-foreground))"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="hsl(var(--muted-foreground))"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                cursor={{ fill: "hsl(var(--accent) / 0.5)" }}
              />
              {meta.numericIdxs.map((idx, i) => (
                <Bar
                  key={columns[idx]}
                  dataKey={columns[idx]}
                  fill={CHART_COLORS[i % CHART_COLORS.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          ) : (
            <LineChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
              <XAxis
                dataKey="__label"
                stroke="hsl(var(--muted-foreground))"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="hsl(var(--muted-foreground))"
                fontSize={11}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              {meta.numericIdxs.map((idx, i) => (
                <Line
                  key={columns[idx]}
                  type="monotone"
                  dataKey={columns[idx]}
                  stroke={CHART_COLORS[i % CHART_COLORS.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export { TableIcon };
