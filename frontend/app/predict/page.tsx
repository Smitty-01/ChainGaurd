"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type TxResult = {
  secure_id: string; // Changed from txId
  fraud_prob: number;
  gnn_fraud_prob: number;
  anomaly_score?: number;
  anomaly_score_norm?: number;
  risk_score: number;
  alert: string;
};

export default function PredictPage() {
  const router = useRouter();
  const [txId, setTxId] = useState(""); // User input (can be secure_id or txId)
  const [result, setResult] = useState<TxResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!txId.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`http://127.0.0.1:8000/tx/${txId.trim()}`);
      if (!res.ok) throw new Error("Not found");
      const data = await res.json();
      setResult(data);
    } catch {
      setError("❌ Transaction not found in ML database");
    } finally {
      setLoading(false);
    }
  };

  const riskBand = (score: number) => {
    if (score >= 80) return { label: "Critical", color: "bg-red-600" };
    if (score >= 60) return { label: "High", color: "bg-orange-500" };
    if (score >= 40) return { label: "Medium", color: "bg-yellow-500" };
    return { label: "Low", color: "bg-green-600" };
  };

  // Helper to display truncated secure_id
  const getTruncatedId = (secureId: string) => {
    if (secureId.length <= 16) return secureId;
    return `${secureId.substring(0, 8)}...${secureId.substring(
      secureId.length - 8
    )}`;
  };

  // Helper to copy secure_id to clipboard
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    alert("Transaction ID copied to clipboard!");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-[#0a0e1a] to-black text-gray-100 px-8 py-12">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-5xl font-black glow-text-cyan mb-8 animate-glow">
          🔮 Analyze Transaction
        </h1>

        {/* Input Section */}
        <div className="glassmorphic glow-border rounded-2xl p-8 mb-8 animate-fade-in">
          <div className="space-y-4">
            <input
              type="text"
              placeholder="Enter transaction ID (secure_id or txId)…"
              value={txId}
              onChange={(e) => setTxId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              className="w-full bg-[#0d1117] border border-cyan-500/30 hover:border-cyan-500/60 focus:border-cyan-400 rounded-lg px-5 py-3 text-sm outline-none focus:ring-2 focus:ring-cyan-400/20 transition-all duration-300"
            />
            <button
              onClick={handleSubmit}
              className="w-full bg-gradient-to-r from-cyan-500 to-cyan-600 hover:from-cyan-400 hover:to-cyan-500 text-black font-bold py-3 rounded-lg transition-all duration-300 shadow-lg hover:shadow-cyan-500/50"
            >
              🔍 Analyze Now
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-4 font-light tracking-wide">
            💡 Enter the secure hash ID or numeric transaction ID. Results
            appear instantly with multi-model predictions.
          </p>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 space-y-4 animate-fade-in">
            <div className="w-12 h-12 border-3 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin"></div>
            <p className="text-gray-400 font-light">
              Analyzing transaction with ML models…
            </p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="glassmorphic border-red-500/30 bg-red-500/5 rounded-xl p-6 border animate-fade-in">
            <p className="text-red-400 font-semibold">⚠️ {error}</p>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="glassmorphic glow-border rounded-2xl p-8 shadow-2xl animate-fade-in space-y-6">
            <div>
              <h2 className="text-3xl font-black glow-text-cyan mb-2">
                🧠 Analysis Results
              </h2>
              <p className="text-gray-400 text-sm font-light">
                Multi-model fraud detection consensus
              </p>
            </div>

            {/* Secure ID Display */}
            <div className="bg-[#0d1117] rounded-lg p-4 border border-cyan-500/20">
              <span className="text-xs text-gray-400 uppercase tracking-widest font-semibold">
                Transaction ID
              </span>
              <div className="flex items-center gap-3 mt-2">
                <code
                  className="flex-1 bg-[#000]/50 px-4 py-2 rounded font-mono text-cyan-400 text-sm cursor-pointer hover:bg-[#0a0e1a] transition-colors border border-cyan-500/20"
                  title={result.secure_id}
                  onClick={() => copyToClipboard(result.secure_id)}
                >
                  {getTruncatedId(result.secure_id)}
                </code>
                <button
                  onClick={() => copyToClipboard(result.secure_id)}
                  className="bg-cyan-600 hover:bg-cyan-500 px-4 py-2 rounded font-bold text-xs transition-colors"
                >
                  📋 Copy
                </button>
              </div>
            </div>

            {/* Risk Score - Hero Section */}
            <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 rounded-lg p-6 border border-cyan-500/20">
              <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">
                Composite Risk Score
              </p>
              <p className="text-5xl font-black glow-text-cyan">
                {result.risk_score.toFixed(2)}
              </p>
            </div>

            {/* Risk Category Badge */}
            <div>
              {(() => {
                const band = riskBand(result.risk_score);
                return (
                  <span
                    className={`inline-block px-6 py-2 rounded-full text-sm font-bold ${band.color} shadow-lg`}
                  >
                    {band.label} Risk
                  </span>
                );
              })()}
            </div>

            {/* Model Scores Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-[#0d1117] rounded-lg p-5 border border-orange-500/20">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">
                  📈 XGBoost
                </p>
                <p className="text-3xl font-black text-orange-400">
                  {(result.fraud_prob * 100).toFixed(1)}%
                </p>
              </div>
              <div className="bg-[#0d1117] rounded-lg p-5 border border-green-500/20">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">
                  🧬 GNN Model
                </p>
                <p className="text-3xl font-black text-green-400">
                  {(result.gnn_fraud_prob * 100).toFixed(1)}%
                </p>
              </div>
              <div className="bg-[#0d1117] rounded-lg p-5 border border-purple-500/20">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2\">
                  👁️ Anomaly
                </p>
                <p className="text-3xl font-black text-purple-400">
                  {(result.anomaly_score_norm ?? result.anomaly_score)?.toFixed(
                    3
                  ) ?? "—"}
                </p>
              </div>
            </div>

            {/* Alert Banner */}
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-5">
              <p className="text-yellow-300 font-bold text-lg">
                ⚠️ Alert: {result.alert}
              </p>
            </div>

            {/* CTA Button */}
            <button
              onClick={() => router.push(`/tx/${result.secure_id}`)}
              className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 px-6 py-4 rounded-lg font-bold text-base transition-all duration-300 shadow-lg hover:shadow-purple-500/50"
            >
              📊 View Full Graph & Detailed Analysis →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
