"use client";

import { useState } from "react";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const uploadCSV = async () => {
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch("http://127.0.0.1:8000/upload", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    setResult(data);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-[#0a0e1a] to-black text-gray-100 px-8 py-12">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-5xl font-black glow-text-cyan mb-3 animate-glow">
          📂 Bulk Screening
        </h1>
        <p className="text-gray-400 text-base font-light mb-12">
          Upload CSV to analyze multiple transactions at once
        </p>

        {/* Upload Section */}
        <div className="glassmorphic glow-border rounded-2xl p-8 mb-8 animate-fade-in">
          <label className="block mb-6">
            <div className="border-2 border-dashed border-cyan-500/30 hover:border-cyan-400/60 rounded-xl p-12 text-center cursor-pointer transition-all duration-300 hover:bg-cyan-500/5">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="hidden"
              />
              <p className="text-2xl mb-2">📥</p>
              {file ? (
                <div>
                  <p className="text-cyan-400 font-bold">{file.name}</p>
                  <p className="text-gray-400 text-sm mt-2">Ready to upload</p>
                </div>
              ) : (
                <div>
                  <p className="text-gray-300 font-semibold mb-1">
                    Click to upload or drag & drop
                  </p>
                  <p className="text-gray-400 text-sm">CSV files only</p>
                </div>
              )}
            </div>
          </label>

          <button
            onClick={uploadCSV}
            disabled={!file || loading}
            className={`w-full py-4 rounded-lg font-bold text-base transition-all duration-300 ${
              !file || loading
                ? "bg-gray-700/50 text-gray-500 cursor-not-allowed"
                : "bg-gradient-to-r from-green-600 to-green-700 hover:from-green-500 hover:to-green-600 shadow-lg hover:shadow-green-500/50"
            }`}
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-green-400/30 border-t-green-400 rounded-full animate-spin"></div>
                Processing…
              </span>
            ) : (
              "🚀 Upload & Analyze"
            )}
          </button>
        </div>

        {/* Results */}
        {result && (
          <div className="glassmorphic glow-border rounded-2xl p-8 shadow-2xl animate-fade-in">
            <h2 className="text-3xl font-black glow-text-cyan mb-8">
              ✅ Analysis Complete
            </h2>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
              <div className="bg-[#0d1117] rounded-lg p-6 border border-cyan-500/20 text-center">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">
                  Total
                </p>
                <p className="text-3xl font-black text-cyan-400">
                  {result.count}
                </p>
              </div>
              <div className="bg-[#0d1117] rounded-lg p-6 border border-red-500/20 text-center">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">
                  High Risk
                </p>
                <p className="text-3xl font-black text-red-400">
                  {result.high_risk}
                </p>
              </div>
              <div className="bg-[#0d1117] rounded-lg p-6 border border-yellow-500/20 text-center">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">
                  Medium
                </p>
                <p className="text-3xl font-black text-yellow-400">
                  {result.medium_risk}
                </p>
              </div>
              <div className="bg-[#0d1117] rounded-lg p-6 border border-green-500/20 text-center">
                <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-2">
                  Low Risk
                </p>
                <p className="text-3xl font-black text-green-400">
                  {result.low_risk}
                </p>
              </div>
            </div>

            <a
              href="http://127.0.0.1:8000/download/bulk"
              className="block w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white font-bold py-4 px-6 rounded-lg text-center transition-all duration-300 shadow-lg hover:shadow-purple-500/50"
            >
              ⬇️ Download Results CSV
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
