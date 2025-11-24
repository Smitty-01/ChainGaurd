"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import Graph from "graphology";
import Sigma from "sigma";
import forceAtlas2 from "graphology-layout-forceatlas2";

export default function TxPage() {
  const { id } = useParams();
  const [txData, setTxData] = useState<any>(null);
  const [graph, setGraph] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [graphDepth, setGraphDepth] = useState(1);

  const anomaly = txData?.anomaly_score ?? txData?.anomaly_score_norm ?? null;
  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];

  // Fetch transaction data and graph
  useEffect(() => {
    if (!id) return;
    setLoading(true);

    Promise.all([
      fetch(`http://127.0.0.1:8000/tx/${id}`).then((res) => res.json()),
      fetch(`http://127.0.0.1:8000/graph/${id}?depth=${graphDepth}`).then(
        (res) => res.json()
      ),
    ])
      .then(([tx, graphData]) => {
        setTxData(tx);
        setGraph(graphData);
      })
      .catch((err) => console.error("Fetch error:", err))
      .finally(() => setLoading(false));
  }, [id, graphDepth]);

  // SIGMA GRAPH RENDER WITH DIRECTIONAL COLORING
  useEffect(() => {
    if (!graph || typeof window === "undefined") return;

    const container = document.getElementById("sigma-container");
    if (!container) return;

    const G = new Graph();

    // Risk → Color function for nodes
    const getNodeColor = (risk: number, type: string, isFlagged: boolean) => {
      if (type === "center") return "#cc00ff"; // Purple for center
      if (isFlagged) return "#000000"; // Black for FLAGGED wallets
      if (risk >= 80) return "#ff0000"; // Red for critical
      if (risk >= 60) return "#ff8c00"; // Orange for high
      if (risk >= 40) return "#ffd700"; // Yellow for medium
      return "#00bfff"; // Blue for low
    };

    // Direction → Color function for edges
    const getEdgeColor = (direction: string) => {
      if (direction === "outgoing") return "#ff6b6b"; // Red = money flowing OUT
      if (direction === "incoming") return "#51cf66"; // Green = money flowing IN
      return "#888888"; // Gray = indirect/multi-hop
    };

    // Add nodes with initial positions
    nodes.forEach((n: any, index: number) => {
      if (!G.hasNode(n.id)) {
        // Give nodes initial circular positions
        const angle = (index / nodes.length) * 2 * Math.PI;
        const radius = n.type === "center" ? 0 : 100;

        const isFlagged = n.is_flagged === true || n.is_flagged === 1;

        G.addNode(n.id, {
          label: isFlagged ? `🚩 ${n.label}` : n.label,
          size: isFlagged ? 20 : n.type === "center" ? 18 : 10,
          color: getNodeColor(n.risk || 0, n.type, isFlagged),
          x: Math.cos(angle) * radius,
          y: Math.sin(angle) * radius,
          borderColor: isFlagged ? "#ff0000" : undefined,
          borderSize: isFlagged ? 3 : 0,
        });
      }
    });

    // Add edges with direction-based styling
    edges.forEach((e: any) => {
      if (!G.hasEdge(e.source, e.target)) {
        const edgeColor = getEdgeColor(e.direction);

        G.addEdge(e.source, e.target, {
          color: edgeColor,
          size: e.direction === "indirect" ? 1 : 2,
          type: "arrow", // Show arrow direction
        });
      }
    });

    // Apply force-directed layout if nodes exist
    if (G.order > 1) {
      try {
        forceAtlas2.assign(G, {
          iterations: 50,
          settings: {
            gravity: 1,
            scalingRatio: 10,
          },
        });
      } catch (error) {
        console.warn("ForceAtlas2 layout failed, using circular layout");
      }
    }

    const renderer = new Sigma(G, container, {
      renderEdgeLabels: false,
    });

    return () => renderer.kill();
  }, [graph]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-black via-[#0a0e1a] to-black flex flex-col justify-center items-center text-lg space-y-4">
        <div className="w-12 h-12 border-3 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin"></div>
        <p className="text-gray-400 font-light">Loading transaction details…</p>
      </div>
    );
  }

  if (!txData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-black via-[#0a0e1a] to-black flex flex-col justify-center items-center p-8">
        <div className="glassmorphic glow-border rounded-2xl p-12 border-red-500/30 bg-red-500/5 text-center max-w-md">
          <p className="text-red-400 font-bold text-lg">
            ⚠️ Transaction Not Found
          </p>
          <p className="text-gray-400 text-sm mt-3">
            This transaction does not exist in the database.
          </p>
        </div>
      </div>
    );
  }

  const displayId =
    typeof id === "string"
      ? id.length > 16
        ? `${id.substring(0, 8)}...${id.substring(id.length - 8)}`
        : id
      : id;

  const copyToClipboard = () => {
    if (typeof id === "string") {
      navigator.clipboard.writeText(id);
      alert("Transaction ID copied to clipboard!");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-[#0a0e1a] to-black text-gray-100 px-8 py-12">
      <div className="max-w-6xl mx-auto space-y-8 animate-fade-in">
        {/* HEADER SECTION */}
        <div className="space-y-4">
          <h1 className="text-5xl font-black glow-text-cyan animate-glow">
            📊 Transaction Analysis
          </h1>

          {/* Secure ID Card */}
          <div className="glassmorphic glow-border rounded-2xl p-6">
            <span className="text-xs text-gray-400 uppercase tracking-widest font-semibold">
              Transaction ID
            </span>
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mt-3">
              <code
                className="flex-1 bg-[#0d1117] px-5 py-3 rounded-lg text-sm font-mono text-cyan-400 cursor-pointer hover:bg-[#0a0e1a] transition-colors border border-cyan-500/20"
                title={String(id)}
                onClick={copyToClipboard}
              >
                {displayId}
              </code>
              <button
                onClick={copyToClipboard}
                className="bg-cyan-600 hover:bg-cyan-500 text-white font-bold px-6 py-3 rounded-lg transition-all duration-300 whitespace-nowrap"
              >
                📋 Copy Full ID
              </button>
            </div>
          </div>
        </div>

        {/* METRICS GRID */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Risk Score Card */}
          <div className="glassmorphic glow-border rounded-2xl p-6 border-cyan-500/20">
            <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-3">
              Composite Risk Score
            </p>
            <p className="text-5xl font-black glow-text-cyan">
              {txData.risk_score?.toFixed(2) ?? "—"}
            </p>
          </div>

          {/* GNN Model Card */}
          <div className="glassmorphic glow-border rounded-2xl p-6 border-green-500/20">
            <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-3">
              🧬 GNN Model
            </p>
            <p className="text-5xl font-black text-green-400">
              {txData.gnn_fraud_prob
                ? (txData.gnn_fraud_prob * 100).toFixed(1)
                : "—"}
              %
            </p>
          </div>

          {/* XGB Model Card */}
          <div className="glassmorphic glow-border rounded-2xl p-6 border-orange-500/20">
            <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-3">
              📈 XGBoost
            </p>
            <p className="text-5xl font-black text-orange-400">
              {txData.fraud_prob ? (txData.fraud_prob * 100).toFixed(1) : "—"}%
            </p>
          </div>

          {/* Anomaly Score Card */}
          <div className="glassmorphic glow-border rounded-2xl p-6 border-purple-500/20">
            <p className="text-xs text-gray-400 uppercase tracking-widest font-semibold mb-3">
              👁️ Anomaly
            </p>
            <p className="text-5xl font-black text-purple-400">
              {anomaly ? anomaly.toFixed(3) : "—"}
            </p>
          </div>
        </div>

        {/* ALERT BANNER */}
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-2xl p-8">
          <p className="text-yellow-300 font-bold text-xl">
            ⚠️ Alert Status: {txData.alert ?? "Under Review"}
          </p>
          <p className="text-yellow-200/70 text-sm mt-2 font-light">
            Requires monitoring and further investigation
          </p>
        </div>

        {/* ACTION BUTTONS */}
        <div className="flex flex-col sm:flex-row gap-4">
          <button
            onClick={() =>
              window.open(`http://127.0.0.1:8000/report/${id}`, "_blank")
            }
            className="flex-1 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white font-bold py-4 px-6 rounded-lg transition-all duration-300 shadow-lg hover:shadow-red-500/50"
          >
            📄 Download Risk Report PDF
          </button>
          <button
            onClick={() => window.history.back()}
            className="flex-1 bg-gradient-to-r from-gray-700 to-gray-800 hover:from-gray-600 hover:to-gray-700 text-white font-bold py-4 px-6 rounded-lg transition-all duration-300 shadow-lg"
          >
            ← Back to Dashboard
          </button>
        </div>

        {/* GRAPH VISUALIZATION */}
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-3xl font-black glow-text-cyan mb-2">
                💫 Transaction Network Graph
              </h2>
              <p className="text-gray-400 text-sm font-light">
                Money flow visualization showing connected transactions
              </p>
            </div>

            {/* Depth Control */}
            <div className="flex gap-2">
              <button
                onClick={() => setGraphDepth(1)}
                className={`px-4 py-2 rounded-lg font-bold transition-all ${
                  graphDepth === 1
                    ? "bg-cyan-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                1-Hop
              </button>
              <button
                onClick={() => setGraphDepth(2)}
                className={`px-4 py-2 rounded-lg font-bold transition-all ${
                  graphDepth === 2
                    ? "bg-cyan-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                2-Hop
              </button>
              <button
                onClick={() => setGraphDepth(3)}
                className={`px-4 py-2 rounded-lg font-bold transition-all ${
                  graphDepth === 3
                    ? "bg-cyan-600 text-white"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
              >
                3-Hop
              </button>
            </div>
          </div>

          {/* Legend */}
          <div className="glassmorphic rounded-xl p-4 flex flex-wrap gap-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-[#cc00ff]"></div>
              <span className="text-gray-300">Center Transaction</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded-full bg-black border-2 border-red-500"></div>
              <span className="text-gray-300">🚩 Flagged Wallet</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-1 bg-[#51cf66]"></div>
              <span className="text-gray-300">Incoming Money</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-1 bg-[#ff6b6b]"></div>
              <span className="text-gray-300">Outgoing Money</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-1 bg-[#888888]"></div>
              <span className="text-gray-300">Indirect Connection</span>
            </div>
          </div>

          <div className="glassmorphic glow-border rounded-2xl p-8 overflow-hidden">
            {graph && nodes.length > 0 ? (
              <>
                <div
                  id="sigma-container"
                  className="w-full h-[700px] bg-[#0d1117] rounded-xl border border-cyan-500/20"
                />
                <div className="mt-4 text-center text-gray-400 text-sm">
                  💡 Showing {nodes.length - 1} connected transaction(s) •{" "}
                  {edges.length} connection(s)
                </div>
              </>
            ) : (
              <div className="w-full h-[700px] flex items-center justify-center">
                <p className="text-center text-gray-500 font-light">
                  ℹ️ No connected transactions found in graph data
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
