"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

type RiskRow = {
  secure_id: number;
  risk_score: number;
  fraud_prob: number;
  gnn_fraud_prob: number;
  anomaly_score_norm?: number;
  anomaly_score?: number;
  alert: string;
};

export default function Home() {
  const router = useRouter();
  const [topRisk, setTopRisk] = useState<RiskRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchId, setSearchId] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  const totalPages = Math.ceil(topRisk.length / itemsPerPage);

  useEffect(() => {
    const loadTop = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/top/50");
        if (!res.ok) throw new Error("Backend error");
        const data = await res.json();
        setTopRisk(data);

        setError("");
      } catch (err) {
        console.error(err);
        setError("Could not load top risky transactions. Backend running?");
      } finally {
        setLoading(false);
      }
    };

    loadTop();
  }, []);

  const handleSearch = () => {
    if (!searchId.trim()) return;
    router.push(`/tx/${searchId.trim()}`);
  };

  const riskBand = (score: number) => {
    if (score >= 80) return { label: "Critical", color: "bg-red-600" };
    if (score >= 60) return { label: "High", color: "bg-orange-500" };
    if (score >= 40) return { label: "Medium", color: "bg-yellow-500" };
    return { label: "Low", color: "bg-green-600" };
  };

  // Pagination helpers
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentData = topRisk.slice(startIndex, endIndex);

  const goToPage = (page: number) => {
    const pageNum = Math.max(1, Math.min(page, totalPages));
    setCurrentPage(pageNum);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-[#0a0e1a] to-black text-gray-100 px-8 py-12">
      {/* PREMIUM HEADER */}
      <header className="mb-12 animate-fade-in">
        <div className="flex flex-col gap-6">
          {/* Title Section */}
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
            <div className="space-y-2">
              <h1 className="text-5xl font-black glow-text-cyan animate-glow">
                🛡️ ChainGuard
              </h1>
              <p className="text-base text-gray-400 font-light tracking-wide">
                Advanced DeFi Transaction Risk Detection — XGBoost + GNN +
                Anomaly Detection
              </p>
            </div>
          </div>

          {/* Search & Navigation Bar */}
          <div className="glassmorphic glow-border rounded-2xl p-6 space-y-4">
            <div className="flex flex-col lg:flex-row gap-4 items-stretch lg:items-center">
              <div className="flex-1">
                <input
                  type="text"
                  placeholder="Search by Transaction ID..."
                  value={searchId}
                  onChange={(e) => setSearchId(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  className="w-full bg-[#0d1117] border border-cyan-500/30 hover:border-cyan-500/60 focus:border-cyan-400 rounded-lg px-5 py-3 text-sm outline-none focus:ring-2 focus:ring-cyan-400/20 transition-all duration-300"
                />
              </div>
              <button
                onClick={handleSearch}
                className="bg-gradient-to-r from-cyan-500 to-cyan-600 hover:from-cyan-400 hover:to-cyan-500 text-black px-8 py-3 rounded-lg text-sm font-bold transition-all duration-300 shadow-lg hover:shadow-cyan-500/50 whitespace-nowrap"
              >
                🔍 Search
              </button>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-col sm:flex-row gap-3 pt-2">
              <Link href="/upload" className="flex-1">
                <button className="w-full px-6 py-3 bg-gradient-to-r from-green-600 to-green-700 hover:from-green-500 hover:to-green-600 rounded-lg font-bold text-sm transition-all duration-300 shadow-lg hover:shadow-green-500/50">
                  ⬆️ Upload CSV
                </button>
              </Link>

              <Link href="/predict" className="flex-1">
                <button className="w-full px-6 py-3 bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 rounded-lg font-bold text-sm transition-all duration-300 shadow-lg hover:shadow-purple-500/50">
                  🔮 Predict
                </button>
              </Link>
            </div>
          </div>
        </div>
      </header>

      {/* LOADING STATE */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-20 space-y-4 animate-fade-in">
          <div className="w-12 h-12 border-3 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin"></div>
          <p className="text-gray-400 font-light">
            Loading top risky transactions…
          </p>
        </div>
      )}

      {/* ERROR STATE */}
      {error && (
        <div className="glassmorphic glow-border rounded-xl p-6 mb-6 border-red-500/30 bg-red-500/5 animate-fade-in">
          <p className="text-red-400 font-semibold">⚠️ {error}</p>
        </div>
      )}

      {/* MAIN TABLE SECTION */}
      {!loading && !error && (
        <section className="glassmorphic glow-border rounded-2xl p-8 shadow-2xl animate-fade-in">
          <div className="mb-8 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <h2 className="text-3xl font-bold glow-text-cyan mb-2">
                🔴 Top 50 Riskiest Transactions
              </h2>
              <p className="text-gray-400 text-sm font-light">
                Click any row to view detailed analysis and transaction graph
              </p>
            </div>

            {/* PAGINATION CONTROLS - Top Right */}
            {totalPages > 1 && (
              <div className="flex flex-wrap items-center justify-end gap-2">
                <button
                  onClick={() => goToPage(1)}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold rounded text-xs transition-colors"
                >
                  ⬅️ First
                </button>

                <button
                  onClick={() => goToPage(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold rounded text-xs transition-colors"
                >
                  ←
                </button>

                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min="1"
                    max={totalPages}
                    value={currentPage}
                    onChange={(e) => goToPage(parseInt(e.target.value) || 1)}
                    className="w-12 bg-[#0d1117] border border-cyan-500/30 rounded px-1.5 py-1 text-cyan-400 text-center font-semibold focus:border-cyan-400 outline-none text-xs"
                  />
                  <span className="text-gray-400 font-medium text-xs">
                    / {totalPages}
                  </span>
                </div>

                <button
                  onClick={() => goToPage(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold rounded text-xs transition-colors"
                >
                  →
                </button>

                <button
                  onClick={() => goToPage(totalPages)}
                  disabled={currentPage === totalPages}
                  className="px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold rounded text-xs transition-colors"
                >
                  Last ➡️
                </button>
              </div>
            )}
          </div>

          <div className="overflow-hidden rounded-xl border border-cyan-500/20">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 border-b border-cyan-500/20">
                    <th className="py-4 px-6 text-left text-cyan-400 font-semibold">
                      Secure ID
                    </th>
                    <th className="py-4 px-6 text-left text-cyan-400 font-semibold">
                      Risk Score
                    </th>
                    <th className="py-4 px-6 text-left text-cyan-400 font-semibold">
                      Category
                    </th>
                    <th className="py-4 px-6 text-left text-cyan-400 font-semibold">
                      XGB Model
                    </th>
                    <th className="py-4 px-6 text-left text-cyan-400 font-semibold">
                      GNN Model
                    </th>
                    {/* <th className="py-4 px-6 text-left text-cyan-400 font-semibold">
                      Anomaly Score
                    </th> */}
                    <th className="py-4 px-6 text-left text-cyan-400 font-semibold">
                      Status
                    </th>
                  </tr>
                </thead>

                <tbody>
                  {currentData.map((row) => {
                    const band = riskBand(row.risk_score);
                    return (
                      <tr
                        key={row.secure_id}
                        onClick={() => router.push(`/tx/${row.secure_id}`)}
                        className="group border-b border-cyan-500/10 hover:bg-cyan-500/5 cursor-pointer transition-all duration-300 hover:glow-border"
                      >
                        <td className="py-5 px-6 font-mono text-cyan-400 group-hover:glow-text-cyan">
                          {String(row.secure_id)?.substring(0, 10)}...
                        </td>
                        <td className="py-5 px-6 font-bold text-white">
                          {row.risk_score.toFixed(2)}
                        </td>
                        <td className="py-5 px-6">
                          <span
                            className={`px-3 py-1 rounded-full text-xs font-bold ${band.color} shadow-lg`}
                          >
                            {band.label}
                          </span>
                        </td>
                        <td className="py-5 px-6 text-orange-300 font-semibold">
                          {(row.fraud_prob * 100).toFixed(1)}%
                        </td>
                        <td className="py-5 px-6 text-green-300 font-semibold">
                          {(row.gnn_fraud_prob * 100).toFixed(1)}%
                        </td>
                        {/* <td className="py-5 px-6 text-gray-300">
                          {row.anomaly_score?.toFixed(3) ?? "—"}
                        </td> */}
                        <td className="py-5 px-6 text-yellow-300 font-semibold text-xs uppercase tracking-wide">
                          {row.alert}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-6 text-xs text-gray-500 text-center font-light">
            Showing {currentData.length} of {topRisk.length} transactions • Last
            updated: {new Date().toLocaleString()}
          </div>
        </section>
      )}
    </div>
  );
}
