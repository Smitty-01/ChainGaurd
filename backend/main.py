from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import io
import os
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from fusion_predictor import FusionPredictor

app = FastAPI(
    title="ChainGuard API",
    description="DeFi Fraud Risk Detection",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Load Data with Hashing ==========
df_private = pd.read_csv("../data/processed/final_risk_scored_private.csv")
df_public = pd.read_csv("../data/processed/final_risk_scored_public.csv")

print("🔍 Public CSV columns:", df_public.columns.tolist())
print("🔍 Private CSV columns:", df_private.columns.tolist())
print("🔍 Public CSV shape:", df_public.shape)

if "txId" not in df_public.columns:
    print("⚠️  txId not found in public CSV. Assuming row alignment with private CSV...")
    if len(df_public) != len(df_private):
        raise ValueError(f"Mismatch: public CSV has {len(df_public)} rows, private has {len(df_private)} rows")
    
    secure_to_real = dict(zip(df_public["secure_id"], df_private["txId"]))
    real_to_secure = dict(zip(df_private["txId"], df_public["secure_id"]))
else:
    print("✅ txId found in public CSV")
    secure_to_real = dict(zip(df_public["secure_id"], df_public["txId"]))
    real_to_secure = dict(zip(df_public["txId"], df_public["secure_id"]))

predictor = FusionPredictor()

print(f"✅ Loaded {len(secure_to_real)} secure_id mappings")
print(f"✅ Sample secure_id: {list(secure_to_real.keys())[0][:16]}...")
print(f"✅ Sample txId: {list(secure_to_real.values())[0]}")


@app.get("/")
def root():
    return {"message": "🚀 ChainGuard API is running!"}


# ========== 1️⃣ Single Transaction Lookup ==========
@app.get("/tx/{secure_id}")
def get_transaction_risk(secure_id: str):
    """Get transaction risk by secure_id"""
    try:
        print(f"🔍 Looking up secure_id: {secure_id}")
        
        if secure_id not in secure_to_real:
            print(f"❌ secure_id not in mapping")
            raise HTTPException(404, "Unknown transaction")

        real_id = secure_to_real[secure_id]
        print(f"✅ Mapped to real_id: {real_id}")
        
        tx = predictor.get_by_id(real_id)
        print(f"📊 Transaction data: {tx}")
        
        if not tx:
            print(f"❌ No data returned from predictor.get_by_id({real_id})")
            raise HTTPException(404, "Transaction data not found")

        tx["secure_id"] = secure_id
        tx.pop("txId", None)
        return tx
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in /tx/{secure_id}:", e)
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Internal error: {str(e)}")


# ========== 2️⃣ CSV Upload & Batch Inference ==========
@app.post("/batch")
async def get_batch_results(file: UploadFile = File(...)):
    """Upload CSV with secure_id or txId column for batch analysis"""
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(400, "Please upload a CSV file")

    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    if "secure_id" in df.columns:
        df["txId"] = df["secure_id"].map(secure_to_real)
        df = df.dropna(subset=["txId"])
        tx_ids = df["txId"].astype(int).tolist()
    elif "txId" in df.columns:
        tx_ids = df["txId"].astype(int).tolist()
    else:
        raise HTTPException(400, "CSV must contain 'secure_id' or 'txId' column")

    results = []
    for tx_id in tx_ids:
        tx = predictor.get_by_id(tx_id)
        if tx:
            tx["secure_id"] = real_to_secure.get(tx_id, "N/A")
            tx.pop("txId", None)
            results.append(tx)

    return {
        "total_requested": len(tx_ids),
        "found": len(results),
        "results": results
    }


# ========== 3️⃣ Top-N Riskiest ==========
@app.get("/top/{n}")
def top_riskiest(n: int = 10):
    """Get top N riskiest transactions"""
    df_top = df_private.nlargest(n, 'risk_score')[['txId', 'risk_score', 'fraud_prob', 
                                                      'gnn_fraud_prob', 'alert']]
    df_top["secure_id"] = df_top["txId"].map(real_to_secure)
    df_top = df_top.drop(columns=["txId"])
    return df_top.to_dict(orient="records")


# ========== 4️⃣ Graph Endpoint (ENHANCED WITH MULTI-HOP) ==========
@app.get("/graph/{secure_id}")
async def get_graph(secure_id: str, depth: int = 1):
    """Get transaction graph with configurable depth"""
    try:
        print(f"🔍 Graph request for secure_id: {secure_id}, depth: {depth}")
        
        # Convert secure_id to real txId
        if secure_id not in secure_to_real:
            print(f"❌ secure_id not found: {secure_id}")
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        tx_id = secure_to_real[secure_id]
        print(f"✅ Converted to txId: {tx_id}")
        
        # Verify tx exists in predictor dataframe
        if not hasattr(predictor, 'df'):
            print("❌ predictor.df not found")
            raise HTTPException(status_code=500, detail="Predictor not initialized properly")
            
        if "txId" not in predictor.df.columns:
            print("❌ txId column not in predictor.df")
            print(f"Available columns: {predictor.df.columns.tolist()}")
            raise HTTPException(status_code=500, detail="txId column missing from predictor data")
        
        if tx_id not in predictor.df["txId"].values:
            print(f"❌ txId {tx_id} not found in predictor.df")
            raise HTTPException(status_code=404, detail="TxID not found in graph")

        edges = predictor.edgelist
        print(f"✅ Edgelist loaded: {len(edges)} edges")
        
        # Define recursive neighbor function
        def get_neighbors(current_tx_id, current_depth, max_depth, visited):
            if current_depth >= max_depth or current_tx_id in visited:
                return set()
            
            visited.add(current_tx_id)
            neighbors = set()
            
            outgoing = edges[edges["txId1"] == current_tx_id]["txId2"].values
            incoming = edges[edges["txId2"] == current_tx_id]["txId1"].values
            
            neighbors.update(outgoing)
            neighbors.update(incoming)
            
            # Recursively get next level
            if current_depth < max_depth - 1:
                for n in list(neighbors):
                    neighbors.update(get_neighbors(int(n), current_depth + 1, max_depth, visited))
            
            return neighbors
        
        # Get all neighbors up to specified depth
        all_neighbors = get_neighbors(tx_id, 0, depth, set())
        print(f"✅ Found {len(all_neighbors)} neighbors at depth {depth}")

        # Get direct 1-hop connections for direction tracking
        outgoing = edges[edges["txId1"] == tx_id]["txId2"].values
        incoming = edges[edges["txId2"] == tx_id]["txId1"].values

        # Build node list
        nodes = [{"id": secure_id, "label": f"TX {secure_id[:8]}...", "type": "center"}]
        edges_res = []

        # If no neighbors, return single node
        if not all_neighbors:
            print("ℹ️ No neighbors found")
            return {"nodes": nodes, "edges": []}

        # Add neighbor nodes and edges with direction
        for n in all_neighbors:
            neighbor_secure_id = real_to_secure.get(int(n), f"unknown_{n}")
            
            # Get risk info for neighbor
            neighbor_tx = predictor.get_by_id(int(n))
            neighbor_risk = neighbor_tx.get("risk_score", 0) if neighbor_tx else 0
            
            # Check if transaction is flagged (class == 1 means illicit in Elliptic dataset)
            is_flagged = False
            if neighbor_tx and "class" in neighbor_tx:
                is_flagged = neighbor_tx["class"] == 1 or neighbor_tx["class"] == "1"
            
            # Determine direction (only for direct 1-hop connections)
            if int(n) in outgoing:
                edges_res.append({
                    "source": secure_id, 
                    "target": neighbor_secure_id,
                    "direction": "outgoing"
                })
            elif int(n) in incoming:
                edges_res.append({
                    "source": neighbor_secure_id,
                    "target": secure_id,
                    "direction": "incoming"
                })
            else:
                # Multi-hop connection (not directly connected)
                edges_res.append({
                    "source": secure_id,
                    "target": neighbor_secure_id,
                    "direction": "indirect"
                })
            
            nodes.append({
                "id": neighbor_secure_id, 
                "label": f"TX {neighbor_secure_id[:8]}...", 
                "type": "neighbor",
                "risk": neighbor_risk,
                "is_flagged": is_flagged
            })

        print(f"✅ Returning {len(nodes)} nodes and {len(edges_res)} edges")
        return {"nodes": nodes, "edges": edges_res}

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Graph Error:", e)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Graph building error: {str(e)}")


# ========== 5️⃣ Bulk Upload with Output ==========
@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Upload CSV for bulk processing"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV allowed")

    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    if "secure_id" in df.columns:
        df["txId"] = df["secure_id"].map(secure_to_real)
        df = df.dropna(subset=["txId"])
    elif "txId" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must contain 'secure_id' or 'txId' column")

    results = []
    for _, row in df.iterrows():
        tx_id = int(row["txId"])
        tx = predictor.get_by_id(tx_id)
        if tx:
            tx["secure_id"] = real_to_secure.get(tx_id, "N/A")
            tx.pop("txId", None)
            results.append(tx)
        else:
            results.append({"secure_id": real_to_secure.get(tx_id, "N/A"), "error": "Not in database"})

    final_df = pd.DataFrame(results)

    out_dir = os.path.join("data", "processed")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "bulk_output.csv")
    final_df.to_csv(out_path, index=False)

    valid_scores = final_df[final_df["risk_score"].notna()]["risk_score"]
    
    return {
        "count": len(results),
        "high_risk": int((valid_scores >= 60).sum()) if len(valid_scores) > 0 else 0,
        "medium_risk": int(((valid_scores >= 40) & (valid_scores < 60)).sum()) if len(valid_scores) > 0 else 0,
        "low_risk": int((valid_scores < 40).sum()) if len(valid_scores) > 0 else 0,
        "file": "/download/bulk"
    }


# ========== 6️⃣ PDF Report Generation ==========
@app.get("/report/{secure_id}")
def generate_report(secure_id: str):
    """Generate PDF report for transaction by secure_id"""
    
    if secure_id not in secure_to_real:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    tx_id = secure_to_real[secure_id]
    tx = predictor.get_by_id(tx_id)
    
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction data not found")

    filename = f"tx_{secure_id[:16]}_report.pdf"
    out_dir = os.path.join("data", "processed")
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, height - 50, "ChainGuard Risk Intelligence Report")

    c.setFont("Helvetica", 10)
    c.drawString(40, height - 80, f"Transaction ID: {secure_id}")
    c.drawString(40, height - 100, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    score = float(tx.get("risk_score", 0))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 150, f"Risk Score: {score:.2f}")

    c.setFont("Helvetica", 12)
    fraud_prob = tx.get('fraud_prob', 0)
    gnn_prob = tx.get('gnn_fraud_prob', 0)
    c.drawString(40, height - 180, f"XGBoost Fraud Probability: {fraud_prob*100:.2f}%")
    c.drawString(40, height - 200, f"GNN Fraud Probability: {gnn_prob*100:.2f}%")

    anomaly = tx.get("anomaly_score_norm") or tx.get("anomaly_score")
    if anomaly is not None:
        c.drawString(40, height - 220, f"Anomaly Score: {anomaly:.4f}")

    if score >= 80: 
        risk = "CRITICAL"
        color = (1, 0.1, 0.1)
    elif score >= 60: 
        risk = "HIGH"
        color = (1, 0.1, 0.1)
    elif score >= 40: 
        risk = "MEDIUM"
        color = (1, 0.8, 0)
    else: 
        risk = "LOW"
        color = (0, 0.6, 0)

    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(*color)
    c.drawString(40, height - 260, f"Risk Level: {risk}")
    c.setFillColorRGB(0, 0, 0)

    c.setFont("Helvetica", 12)
    alert = tx.get('alert', 'Review transaction')
    c.drawString(40, height - 290, f"Recommended Action: {alert}")

    c.setFont("Helvetica-Oblique", 10)
    c.drawString(40, 40, "Confidential - ChainGuard Analytics")

    c.showPage()
    c.save()

    return FileResponse(filepath, filename=filename, media_type="application/pdf")


# ========== 7️⃣ Download Bulk Results ==========
@app.get("/download/bulk")
def download_bulk():
    """Download the last generated bulk output CSV"""
    filepath = os.path.join("data", "processed", "bulk_output.csv")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="No bulk output file found")
    
    return FileResponse(filepath, filename="bulk_output.csv", media_type="text/csv")


# ========== 8️⃣ Health Check & Mapping Stats ==========
@app.get("/health")
def health_check():
    """Check API health and mapping status"""
    return {
        "status": "healthy",
        "total_transactions": len(secure_to_real),
        "sample_secure_id": list(secure_to_real.keys())[0] if secure_to_real else None,
        "predictor_loaded": predictor is not None
    }