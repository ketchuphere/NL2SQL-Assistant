import { useState, useEffect, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";

// ─── Types ───────────────────────────────────────────
interface PredictionResult {
  churn_probability: number;
  prediction: string;
  risk_level: string;
  confidence: number;
  key_factors: string[];
  model_accuracy: number;
  model_roc_auc: number;
}

interface ModelInfo {
  accuracy: number;
  roc_auc: number;
  architecture: string;
  optimizer: string;
}

// ─── Helpers ─────────────────────────────────────────
const API_BASE = "http://localhost:8000";

const riskColor = (prob: number) => {
  if (prob < 0.3) return "hsl(162, 68%, 48%)";
  if (prob <= 0.65) return "hsl(37, 91%, 55%)";
  return "hsl(345, 78%, 60%)";
};

const riskLabel = (prob: number) => {
  if (prob < 0.3) return "Low";
  if (prob <= 0.65) return "Medium";
  return "High";
};

// ─── Sub-components ──────────────────────────────────

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
    <div className="flex gap-2">
      {options.map((o) => (
        <button
          key={String(o.value)}
          onClick={() => onChange(o.value)}
          className={`flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all duration-300 ${
            value === o.value
              ? "gradient-bg text-primary-foreground shadow-lg glow-shadow"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
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
        <label className="text-sm text-muted-foreground font-medium">{label}</label>
        <span className="font-mono text-sm font-bold gradient-text">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step || 1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full"
      />
    </div>
  );
}

function SemiCircleGauge({ value, size = 200 }: { value: number; size?: number }) {
  const radius = 80;
  const strokeWidth = 14;
  const cx = size / 2;
  const cy = size / 2 + 10;
  const circumference = Math.PI * radius;
  const fillLength = circumference * value;
  const color = riskColor(value);

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size / 2 + 30} viewBox={`0 0 ${size} ${size / 2 + 30}`}>
        {/* Track */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="hsl(232, 22%, 16%)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Fill */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={`${fillLength} ${circumference}`}
          style={{
            transition: "stroke-dasharray 0.9s cubic-bezier(.4,0,.2,1), stroke 0.5s ease",
          }}
        />
      </svg>
      <span
        className="font-mono text-4xl font-bold -mt-12"
        style={{ color }}
      >
        {(value * 100).toFixed(1)}%
      </span>
    </div>
  );
}

function RiskBar({ probability }: { probability: number }) {
  return (
    <div className="space-y-2">
      <div className="relative h-3 rounded-full overflow-hidden" style={{
        background: "linear-gradient(90deg, hsl(162,68%,48%), hsl(37,91%,55%), hsl(345,78%,60%))",
      }}>
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-foreground border-2 border-background shadow-lg"
          style={{
            left: `calc(${probability * 100}% - 8px)`,
            transition: "left 0.8s cubic-bezier(.4,0,.2,1)",
          }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground font-medium">
        <span>Low Risk</span>
        <span>Medium</span>
        <span>High Risk</span>
      </div>
    </div>
  );
}

function NeuralNetworkDiagram() {
  const layers = [
    { label: "Input", neurons: 5, color: "hsl(220, 70%, 55%)" },
    { label: "128", neurons: 6, color: "hsl(258, 85%, 62%)" },
    { label: "64", neurons: 5, color: "hsl(300, 70%, 55%)" },
    { label: "32", neurons: 4, color: "hsl(345, 78%, 60%)" },
    { label: "Output", neurons: 1, color: "hsl(162, 68%, 48%)" },
  ];
  const svgW = 400;
  const svgH = 180;
  const layerSpacing = svgW / (layers.length + 1);

  return (
    <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full max-w-md mx-auto">
      {layers.map((layer, li) => {
        const x = layerSpacing * (li + 1);
        const neuronSpacing = svgH / (layer.neurons + 1);
        return layers[li + 1]
          ? Array.from({ length: layer.neurons }).flatMap((_, ni) => {
              const y1 = neuronSpacing * (ni + 1);
              const nextLayer = layers[li + 1];
              const nextSpacing = svgH / (nextLayer.neurons + 1);
              const nx = layerSpacing * (li + 2);
              return Array.from({ length: nextLayer.neurons }).map((_, nj) => (
                <line
                  key={`${li}-${ni}-${nj}`}
                  x1={x}
                  y1={y1}
                  x2={nx}
                  y2={nextSpacing * (nj + 1)}
                  stroke="hsl(232, 22%, 20%)"
                  strokeWidth={0.5}
                />
              ));
            })
          : null;
      })}
      {layers.map((layer, li) => {
        const x = layerSpacing * (li + 1);
        const neuronSpacing = svgH / (layer.neurons + 1);
        return (
          <g key={li}>
            {Array.from({ length: layer.neurons }).map((_, ni) => (
              <circle
                key={ni}
                cx={x}
                cy={neuronSpacing * (ni + 1)}
                r={6}
                fill={layer.color}
                opacity={0.85}
              />
            ))}
            <text x={x} y={svgH - 2} textAnchor="middle" fill="hsl(220,10%,55%)" fontSize="9" fontFamily="JetBrains Mono">
              {layer.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Main Page ───────────────────────────────────────
const ChurnScope = () => {
  const { toast } = useToast();

  // Form state
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

  // Results
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [showResult, setShowResult] = useState(false);

  // Fetch model info on mount
  useEffect(() => {
    fetch(`${API_BASE}/model-info`)
      .then((r) => r.json())
      .then((data) => {
        setModelInfo({
          accuracy: data.accuracy ?? 0.714,
          roc_auc: data.roc_auc ?? 0.7415,
          architecture: data.architecture ?? "128 → 64 → 32",
          optimizer: data.optimizer ?? "Adam",
        });
      })
      .catch(() => {
        setModelInfo({
          accuracy: 0.714,
          roc_auc: 0.7415,
          architecture: "128 → 64 → 32",
          optimizer: "Adam",
        });
      });
  }, []);

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
        title: "Prediction Failed",
        description: "Could not reach the prediction API. Using demo data.",
        variant: "destructive",
      });
      // Demo fallback
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
        model_accuracy: 0.714,
        model_roc_auc: 0.7415,
      });
      setShowResult(true);
    } finally {
      setLoading(false);
    }
  }, [creditScore, age, geography, gender, tenure, products, balance, salary, hasCreditCard, isActive, toast]);

  const prob = result?.churn_probability ?? 0;
  const pillBadges = ["DNN · 3 Hidden Layers", "128 → 64 → 32 Neurons", "Adam Optimizer", "L2 Regularisation", "Early Stopping"];
  const mi = modelInfo || { accuracy: 0.714, roc_auc: 0.7415, architecture: "128 → 64 → 32", optimizer: "Adam" };

  return (
    <div className="relative z-10 min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-background/60 border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg gradient-bg flex items-center justify-center text-primary-foreground font-bold text-lg">
              ⚡
            </div>
            <h1 className="font-heading text-xl font-bold tracking-tight">
              Churn<span className="text-secondary">Scope</span>
            </h1>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-success/10 border border-success/20">
            <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-xs font-semibold text-success">Model Online</span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="text-center py-10 px-4 animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
        <h2 className="font-heading text-3xl sm:text-5xl font-extrabold leading-tight max-w-3xl mx-auto">
          Predict Customer{" "}
          <span className="gradient-text">Churn Risk</span>{" "}
          with Deep Learning
        </h2>
        <p className="mt-3 text-muted-foreground max-w-xl mx-auto text-sm sm:text-base">
          Enter customer details below and let our neural network predict the likelihood of churn.
        </p>
        <div className="flex flex-wrap justify-center gap-2 mt-5">
          {pillBadges.map((b) => (
            <span key={b} className="font-mono text-xs px-3 py-1.5 rounded-full bg-muted text-muted-foreground border border-border">
              {b}
            </span>
          ))}
        </div>
      </section>

      {/* Main Grid */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 pb-16 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left — Form */}
        <div className="card-surface p-6 sm:p-8 animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
          <h3 className="font-heading text-lg font-bold mb-6">Customer Profile</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <RangeSlider label="Credit Score" min={300} max={900} value={creditScore} onChange={setCreditScore} />
            <RangeSlider label="Age" min={18} max={92} value={age} onChange={setAge} />
            <div className="space-y-2">
              <label className="text-sm text-muted-foreground font-medium">Geography</label>
              <select
                value={geography}
                onChange={(e) => setGeography(e.target.value)}
                className="w-full bg-muted text-foreground rounded-xl px-4 py-2.5 text-sm border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="France">🇫🇷 France</option>
                <option value="Germany">🇩🇪 Germany</option>
                <option value="Spain">🇪🇸 Spain</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm text-muted-foreground font-medium">Gender</label>
              <PillToggle
                options={[{ label: "Male", value: "Male" }, { label: "Female", value: "Female" }]}
                value={gender}
                onChange={(v) => setGender(String(v))}
              />
            </div>
            <RangeSlider label="Tenure (years)" min={0} max={10} value={tenure} onChange={setTenure} />
            <RangeSlider label="Products Count" min={1} max={4} value={products} onChange={setProducts} />
            <div className="space-y-2">
              <label className="text-sm text-muted-foreground font-medium">Account Balance (€)</label>
              <input
                type="number"
                value={balance}
                onChange={(e) => setBalance(Number(e.target.value))}
                className="w-full bg-muted text-foreground rounded-xl px-4 py-2.5 text-sm font-mono border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-muted-foreground font-medium">Estimated Salary (€/yr)</label>
              <input
                type="number"
                value={salary}
                onChange={(e) => setSalary(Number(e.target.value))}
                className="w-full bg-muted text-foreground rounded-xl px-4 py-2.5 text-sm font-mono border border-border focus:outline-none focus:ring-2 focus:ring-primary/50"
                placeholder="0.00"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-muted-foreground font-medium">Has Credit Card</label>
              <PillToggle
                options={[{ label: "Yes", value: 1 }, { label: "No", value: 0 }]}
                value={hasCreditCard}
                onChange={(v) => setHasCreditCard(Number(v))}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-muted-foreground font-medium">Active Member</label>
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
            className="mt-8 w-full gradient-bg text-primary-foreground font-heading font-bold text-base py-3.5 rounded-xl transition-all duration-300 hover:shadow-xl hover:glow-shadow hover:-translate-y-0.5 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {loading ? (
              <span className="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin-slow" />
            ) : (
              <>⚡ Predict Churn Risk</>
            )}
          </button>
        </div>

        {/* Right — Results */}
        <div className="flex flex-col gap-6">
          {/* Prediction Result Card */}
          {showResult && result && (
            <div
              className="card-surface p-6 sm:p-8 animate-fade-in-up"
              style={{ animationDelay: "0s" }}
            >
              <h3 className="font-heading text-lg font-bold mb-4">Prediction Result</h3>

              {/* Gauge */}
              <SemiCircleGauge value={prob} />

              {/* Verdict */}
              <div className="mt-4 flex justify-center">
                <div
                  className="inline-flex items-center gap-2 px-5 py-2 rounded-full text-sm font-bold"
                  style={{
                    background: prob < 0.5 ? "hsl(162,68%,48%,0.12)" : "hsl(345,78%,60%,0.12)",
                    color: prob < 0.5 ? "hsl(162,68%,48%)" : "hsl(345,78%,60%)",
                    border: `1px solid ${prob < 0.5 ? "hsl(162,68%,48%,0.25)" : "hsl(345,78%,60%,0.25)"}`,
                  }}
                >
                  {prob < 0.5 ? "✅" : "⚠️"}{" "}
                  {prob < 0.5 ? "LOW CHURN RISK" : "HIGH CHURN RISK"} ({(prob * 100).toFixed(1)}%)
                </div>
              </div>

              {/* Risk Bar */}
              <div className="mt-6">
                <RiskBar probability={prob} />
              </div>

              {/* Stats */}
              <div className="grid grid-cols-2 gap-3 mt-6">
                <div className="bg-muted rounded-xl p-4 text-center">
                  <p className="text-xs text-muted-foreground mb-1">Confidence</p>
                  <p className="font-mono text-xl font-bold" style={{ color: riskColor(1 - (result.confidence ?? 0)) }}>
                    {((result.confidence ?? 0) * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="bg-muted rounded-xl p-4 text-center">
                  <p className="text-xs text-muted-foreground mb-1">Risk Level</p>
                  <p className="font-mono text-xl font-bold" style={{ color: riskColor(prob) }}>
                    {result.risk_level}
                  </p>
                </div>
              </div>

              {/* Key Factors */}
              {result.key_factors && result.key_factors.length > 0 && (
                <div className="mt-6 space-y-2">
                  <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider mb-3">Key Factors</p>
                  {result.key_factors.map((f, i) => {
                    const dotColor = i === 0 ? "hsl(162,68%,48%)" : i === 1 ? "hsl(37,91%,55%)" : "hsl(345,78%,60%)";
                    return (
                      <div key={i} className="flex items-start gap-3 bg-muted rounded-xl p-3">
                        <span className="mt-1 w-2.5 h-2.5 rounded-full shrink-0" style={{ background: dotColor }} />
                        <span className="text-sm text-foreground/80">{f}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Neural Network Info */}
          <div className="card-surface p-6 sm:p-8 animate-fade-in-up" style={{ animationDelay: "0.4s" }}>
            <h3 className="font-heading text-lg font-bold mb-5">Neural Network Info</h3>
            <div className="grid grid-cols-2 gap-3 mb-6">
              {[
                { label: "Accuracy", value: `${(mi.accuracy * 100).toFixed(1)}%` },
                { label: "ROC-AUC", value: mi.roc_auc.toFixed(4) },
                { label: "Architecture", value: mi.architecture },
                { label: "Optimizer", value: mi.optimizer },
              ].map((m) => (
                <div key={m.label} className="bg-muted rounded-xl p-4 text-center">
                  <p className="text-xs text-muted-foreground mb-1">{m.label}</p>
                  <p className="font-mono text-sm font-bold text-foreground">{m.value}</p>
                </div>
              ))}
            </div>
            <NeuralNetworkDiagram />
          </div>
        </div>
      </main>
    </div>
  );
};

export default ChurnScope;
