import { useState, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";

const API_BASE = "http://localhost:8000";

interface PredictionResult {
  churn_probability: number;
  prediction: string;
  risk_level: string;
  confidence: number;
  key_factors: string[];
}

const riskColor = (prob: number) => {
  if (prob < 0.3) return "hsl(152, 60%, 42%)";
  if (prob <= 0.65) return "hsl(38, 92%, 50%)";
  return "hsl(0, 72%, 51%)";
};

const riskLabel = (prob: number) => {
  if (prob < 0.3) return "Low";
  if (prob <= 0.65) return "Medium";
  return "High";
};

// ── Small Components ─────────────────────────────────

function PillToggle({
  options,
  value,
  onChange,
}: {
  options: { label: string; value: string | number }[];
  value: string | number;
  onChange: (v: string | number) => void;
}) {
  return (
    <div className="flex rounded-lg bg-secondary p-1 gap-1">
      {options.map((o) => (
        <button
          key={String(o.value)}
          onClick={() => onChange(o.value)}
          className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
            value === o.value
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function RangeSlider({
  label,
  min,
  max,
  step,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <label className="text-sm font-medium text-foreground">{label}</label>
        <span className="font-mono-display text-sm font-bold text-primary">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step || 1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function SemiCircleGauge({ value }: { value: number }) {
  const size = 200;
  const radius = 75;
  const strokeWidth = 12;
  const cx = size / 2;
  const cy = size / 2 + 10;
  const circumference = Math.PI * radius;
  const fillLength = circumference * value;
  const color = riskColor(value);

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 30} viewBox={`0 0 ${size} ${size / 2 + 30}`}>
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="hsl(220, 13%, 90%)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${fillLength} ${circumference}`}
          style={{ transition: "stroke-dasharray 0.9s cubic-bezier(.4,0,.2,1), stroke 0.5s ease" }}
        />
      </svg>
      <span className="font-mono-display text-4xl font-bold -mt-10" style={{ color }}>
        {(value * 100).toFixed(1)}%
      </span>
    </div>
  );
}

function RiskBar({ probability }: { probability: number }) {
  return (
    <div className="space-y-2">
      <div
        className="relative h-2.5 rounded-full overflow-visible"
        style={{ background: "linear-gradient(90deg, hsl(152,60%,42%), hsl(38,92%,50%), hsl(0,72%,51%))" }}
      >
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-card border-2 border-foreground shadow-md"
          style={{
            left: `calc(${probability * 100}% - 8px)`,
            transition: "left 0.8s cubic-bezier(.4,0,.2,1)",
          }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Low</span>
        <span>Medium</span>
        <span>High</span>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────

const ChurnScope = () => {
  const { toast } = useToast();

  const [creditScore, setCreditScore] = useState(619);
  const [age, setAge] = useState(42);
  const [geography, setGeography] = useState("France");
  const [gender, setGender] = useState("Female");
  const [tenure, setTenure] = useState(2);
  const [products, setProducts] = useState(1);
  const [balance, setBalance] = useState(0);
  const [salary, setSalary] = useState(101349);
  const [hasCreditCard, setHasCreditCard] = useState(1);
  const [isActive, setIsActive] = useState(1);

  const [result, setResult] = useState<PredictionResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [showResult, setShowResult] = useState(false);

  const predict = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          credit_score: creditScore,
          geography,
          gender,
          age,
          tenure,
          balance,
          num_of_products: products,
          has_cr_card: hasCreditCard,
          is_active_member: isActive,
          estimated_salary: salary,
        }),
      });
      if (!res.ok) throw new Error("API error");
      const data: PredictionResult = await res.json();
      setResult(data);
      setShowResult(true);
    } catch {
      toast({
        title: "Connection Issue",
        description: "Could not reach the API. Showing demo prediction.",
        variant: "destructive",
      });
      const demoProb = Math.random() * 0.8 + 0.05;
      setResult({
        churn_probability: demoProb,
        prediction: demoProb > 0.5 ? "Churn" : "Stay",
        risk_level: riskLabel(demoProb),
        confidence: 1 - demoProb,
        key_factors: [
          "Active member with long tenure — loyal customer",
          "Low account balance may indicate disengagement",
          "Multiple products suggest higher retention",
        ],
      });
      setShowResult(true);
    } finally {
      setLoading(false);
    }
  }, [creditScore, age, geography, gender, tenure, products, balance, salary, hasCreditCard, isActive, toast]);

  const prob = result?.churn_probability ?? 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-card/80 backdrop-blur-lg border-b border-border">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-primary-foreground text-sm font-bold">
              ⚡
            </div>
            <span className="text-lg font-bold tracking-tight text-foreground">
              Churn<span className="text-primary">Scope</span>
            </span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-success/10">
            <span className="w-1.5 h-1.5 rounded-full bg-success" />
            <span className="text-xs font-medium text-success">Online</span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="text-center pt-10 pb-6 px-4 animate-fade-in-up" style={{ animationDelay: "0.05s" }}>
        <h1 className="text-2xl sm:text-4xl font-bold text-foreground leading-tight">
          Customer Churn Prediction
        </h1>
        <p className="mt-2 text-muted-foreground text-sm sm:text-base max-w-md mx-auto">
          Enter customer details and instantly predict churn risk.
        </p>
      </section>

      {/* Main Grid */}
      <main className="max-w-6xl mx-auto px-4 sm:px-6 pb-16 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="bg-card rounded-xl border border-border p-6 shadow-sm animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
          <h2 className="text-base font-semibold text-foreground mb-5">Customer Profile</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <RangeSlider label="Credit Score" min={300} max={900} value={creditScore} onChange={setCreditScore} />
            <RangeSlider label="Age" min={18} max={92} value={age} onChange={setAge} />

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Geography</label>
              <select
                value={geography}
                onChange={(e) => setGeography(e.target.value)}
                className="w-full bg-secondary text-foreground rounded-lg px-3 py-2.5 text-sm border border-border focus:outline-none focus:ring-2 focus:ring-primary/40"
              >
                <option value="France">🇫🇷 France</option>
                <option value="Germany">🇩🇪 Germany</option>
                <option value="Spain">🇪🇸 Spain</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Gender</label>
              <PillToggle
                options={[{ label: "Male", value: "Male" }, { label: "Female", value: "Female" }]}
                value={gender}
                onChange={(v) => setGender(String(v))}
              />
            </div>

            <RangeSlider label="Tenure (years)" min={0} max={10} value={tenure} onChange={setTenure} />
            <RangeSlider label="Products Count" min={1} max={4} value={products} onChange={setProducts} />

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Account Balance (€)</label>
              <input
                type="number"
                value={balance}
                onChange={(e) => setBalance(Number(e.target.value))}
                className="w-full bg-secondary text-foreground rounded-lg px-3 py-2.5 text-sm font-mono-display border border-border focus:outline-none focus:ring-2 focus:ring-primary/40"
                placeholder="0.00"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Estimated Salary (€/yr)</label>
              <input
                type="number"
                value={salary}
                onChange={(e) => setSalary(Number(e.target.value))}
                className="w-full bg-secondary text-foreground rounded-lg px-3 py-2.5 text-sm font-mono-display border border-border focus:outline-none focus:ring-2 focus:ring-primary/40"
                placeholder="0.00"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Has Credit Card</label>
              <PillToggle
                options={[{ label: "Yes", value: 1 }, { label: "No", value: 0 }]}
                value={hasCreditCard}
                onChange={(v) => setHasCreditCard(Number(v))}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Active Member</label>
              <PillToggle
                options={[{ label: "Active", value: 1 }, { label: "Inactive", value: 0 }]}
                value={isActive}
                onChange={(v) => setIsActive(Number(v))}
              />
            </div>
          </div>

          <button
            onClick={predict}
            disabled={loading}
            className="mt-7 w-full bg-primary text-primary-foreground font-semibold text-sm py-3 rounded-lg transition-all duration-200 hover:opacity-90 hover:shadow-md active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <span className="w-4 h-4 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin-custom" />
            ) : (
              <>⚡ Predict Churn Risk</>
            )}
          </button>
        </div>

        {/* Result */}
        <div className="flex flex-col gap-6">
          {showResult && result ? (
            <div className="bg-card rounded-xl border border-border p-6 shadow-sm animate-fade-in-up">
              <h2 className="text-base font-semibold text-foreground mb-4">Prediction Result</h2>

              <SemiCircleGauge value={prob} />

              {/* Verdict pill */}
              <div className="mt-4 flex justify-center">
                <div
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold"
                  style={{
                    background: prob < 0.5 ? "hsl(152,60%,42%,0.1)" : "hsl(0,72%,51%,0.1)",
                    color: prob < 0.5 ? "hsl(152,60%,42%)" : "hsl(0,72%,51%)",
                  }}
                >
                  {prob < 0.5 ? "✅" : "⚠️"}{" "}
                  {prob < 0.5 ? "Low Churn Risk" : "High Churn Risk"} — {(prob * 100).toFixed(1)}%
                </div>
              </div>

              {/* Risk bar */}
              <div className="mt-6">
                <RiskBar probability={prob} />
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-2 gap-3 mt-5">
                <div className="bg-secondary rounded-lg p-3.5 text-center">
                  <p className="text-xs text-muted-foreground mb-0.5">Confidence</p>
                  <p className="font-mono-display text-lg font-bold" style={{ color: riskColor(1 - (result.confidence ?? 0)) }}>
                    {((result.confidence ?? 0) * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="bg-secondary rounded-lg p-3.5 text-center">
                  <p className="text-xs text-muted-foreground mb-0.5">Risk Level</p>
                  <p className="font-mono-display text-lg font-bold" style={{ color: riskColor(prob) }}>
                    {result.risk_level}
                  </p>
                </div>
              </div>

              {/* Key Factors */}
              {result.key_factors?.length > 0 && (
                <div className="mt-5 space-y-2">
                  <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-2">Key Factors</p>
                  {result.key_factors.map((f, i) => {
                    const dotColor = i === 0 ? "hsl(152,60%,42%)" : i === 1 ? "hsl(38,92%,50%)" : "hsl(0,72%,51%)";
                    return (
                      <div key={i} className="flex items-start gap-2.5 bg-secondary rounded-lg p-3">
                        <span className="mt-1 w-2 h-2 rounded-full shrink-0" style={{ background: dotColor }} />
                        <span className="text-sm text-foreground/80">{f}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-card rounded-xl border border-border p-12 shadow-sm flex flex-col items-center justify-center text-center animate-fade-in-up" style={{ animationDelay: "0.15s" }}>
              <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center text-2xl mb-4">📊</div>
              <p className="text-sm font-medium text-muted-foreground">
                Fill in the customer details and click predict to see results here.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default ChurnScope;
