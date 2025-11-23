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


@app.get("/top/{n}")
def top_riskiest(n: int = 10):
    """Get top N riskiest transactions"""
    df_top = df_private.nlargest(n, 'risk_score')[['txId', 'risk_score', 'fraud_prob', 
                                                      'gnn_fraud_prob', 'alert']]
    df_top["secure_id"] = df_top["txId"].map(real_to_secure)
    df_top = df_top.drop(columns=["txId"])
    return df_top.to_dict(orient="records")


@app.get("/graph/{secure_id}")
async def get_graph(secure_id: str, depth: int = 1):
    """Get transaction graph with configurable depth"""
    try:
        print(f"🔍 Graph request for secure_id: {secure_id}, depth: {depth}")
        
        if secure_id not in secure_to_real:
            print(f"❌ secure_id not found: {secure_id}")
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        tx_id = secure_to_real[secure_id]
        print(f"✅ Converted to txId: {tx_id}")
        
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
        
        def get_neighbors(current_tx_id, current_depth, max_depth, visited):
            if current_depth >= max_depth or current_tx_id in visited:
                return set()
            
            visited.add(current_tx_id)
            neighbors = set()
            
            outgoing = edges[edges["txId1"] == current_tx_id]["txId2"].values
            incoming = edges[edges["txId2"] == current_tx_id]["txId1"].values
            
            neighbors.update(outgoing)
            neighbors.update(incoming)
            
            if current_depth < max_depth - 1:
                for n in list(neighbors):
                    neighbors.update(get_neighbors(int(n), current_depth + 1, max_depth, visited))
            
            return neighbors
        
        all_neighbors = get_neighbors(tx_id, 0, depth, set())
        print(f"✅ Found {len(all_neighbors)} neighbors at depth {depth}")

        outgoing = edges[edges["txId1"] == tx_id]["txId2"].values
        incoming = edges[edges["txId2"] == tx_id]["txId1"].values

        nodes = [{"id": secure_id, "label": f"TX {secure_id[:8]}...", "type": "center"}]
        edges_res = []

        if not all_neighbors:
            print("ℹ️ No neighbors found")
            return {"nodes": nodes, "edges": []}

        for n in all_neighbors:
            neighbor_secure_id = real_to_secure.get(int(n), f"unknown_{n}")
            
            neighbor_tx = predictor.get_by_id(int(n))
            neighbor_risk = neighbor_tx.get("risk_score", 0) if neighbor_tx else 0
            
            is_flagged = False
            
            if neighbor_tx:
                # PRIORITY 1: Check 'class' column FIRST (most reliable)
                if "class" in neighbor_tx:
                    class_val = neighbor_tx["class"]
                    is_flagged = (class_val == 1 or class_val == "1")
                    print(f"  Checking class for {neighbor_secure_id[:16]}... - class={class_val}, flagged={is_flagged}")
                
                # PRIORITY 2: Check risk score threshold (only if class not set)
                if not is_flagged and neighbor_risk >= 80:
                    is_flagged = True
                    print(f"  Flagged by risk score: {neighbor_risk}")
                
                # PRIORITY 3: Check alert status
                if not is_flagged and neighbor_tx.get("alert") in ["CRITICAL", "Block Transaction", "High Risk"]:
                    is_flagged = True
                    print(f"  Flagged by alert status")
                
                # PRIORITY 4: Check fraud probability threshold
                if not is_flagged:
                    fraud_prob = neighbor_tx.get("fraud_prob", 0)
                    gnn_prob = neighbor_tx.get("gnn_fraud_prob", 0)
                    if fraud_prob >= 0.9 or gnn_prob >= 0.9:
                        is_flagged = True
                        print(f"  Flagged by fraud probability")
            
            print(f"  Final: Node {neighbor_secure_id[:16]}... - Risk: {neighbor_risk:.2f}, Flagged: {is_flagged}")
            
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

    # Dark header bar
    c.setFillColorRGB(0.04, 0.06, 0.12)
    c.rect(0, height - 100, width, 100, fill=True, stroke=False)
    
    # Company logo/name
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(50, height - 50, "ChainGuard")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 70, "Blockchain Risk Intelligence Platform")

    # Accent line
    c.setStrokeColorRGB(0.2, 0.6, 1)
    c.setLineWidth(3)
    c.line(50, height - 85, width - 50, height - 85)

    # Transaction metadata section
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(50, height - 120, "TRANSACTION ANALYSIS REPORT")
    
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 140, f"Transaction ID: {secure_id[:32]}...")
    c.drawString(50, height - 155, f"Report Generated: {datetime.now().strftime('%B %d, %Y at %H:%M:%S UTC')}")

    # Risk Score - Large and prominent
    score = float(tx.get("risk_score", 0))
    
    y_pos = height - 220
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(50, y_pos, "OVERALL RISK SCORE")
    
    # Determine risk level and color
    if score >= 80: 
        risk = "  CRITICAL RISK"
        color = (0.9, 0.1, 0.1)
    elif score >= 60: 
        risk = "  HIGH RISK"
        color = (1, 0.4, 0)
    elif score >= 40: 
        risk = "  MEDIUM RISK"
        color = (1, 0.7, 0)
    else: 
        risk = "LOW RISK"
        color = (0.1, 0.7, 0.3)

    # Large risk score number
    c.setFont("Helvetica-Bold", 72)
    c.setFillColorRGB(*color)
    c.drawString(50, y_pos - 80, f"{score:.1f}")
    
    c.setFont("Helvetica-Bold", 24)
    c.drawString(180, y_pos - 60, risk)

    # Risk indicator bar
    bar_width = 400
    bar_height = 20
    bar_x = 50
    bar_y = y_pos - 120
    
    # Background bar
    c.setFillColorRGB(0.9, 0.9, 0.9)
    c.rect(bar_x, bar_y, bar_width, bar_height, fill=True, stroke=False)
    
    # Filled portion
    fill_width = (score / 100) * bar_width
    c.setFillColorRGB(*color)
    c.rect(bar_x, bar_y, fill_width, bar_height, fill=True, stroke=False)
    
    # Score markers
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    for marker in [0, 25, 50, 75, 100]:
        x = bar_x + (marker / 100) * bar_width
        c.drawString(x - 5, bar_y - 15, str(marker))

    # Model predictions section
    y_pos = height - 380
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(50, y_pos, "AI Model Analysis")
    
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(1)
    c.line(50, y_pos - 5, width - 50, y_pos - 5)

    y_pos -= 35
    fraud_prob = tx.get('fraud_prob', 0)
    gnn_prob = tx.get('gnn_fraud_prob', 0)
    
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(50, y_pos, "XGBoost Fraud Detection:")
    c.setFont("Helvetica-Bold", 11)
    prob_color = (0.9, 0.1, 0.1) if fraud_prob > 0.6 else (1, 0.6, 0) if fraud_prob > 0.4 else (0.1, 0.5, 0.1)
    c.setFillColorRGB(*prob_color)
    c.drawString(300, y_pos, f"{fraud_prob*100:.2f}%")
    
    y_pos -= 25
    c.setFont("Helvetica", 11)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(50, y_pos, "Graph Neural Network Analysis:")
    c.setFont("Helvetica-Bold", 11)
    gnn_color = (0.9, 0.1, 0.1) if gnn_prob > 0.6 else (1, 0.6, 0) if gnn_prob > 0.4 else (0.1, 0.5, 0.1)
    c.setFillColorRGB(*gnn_color)
    c.drawString(300, y_pos, f"{gnn_prob*100:.2f}%")

    anomaly = tx.get("anomaly_score_norm") or tx.get("anomaly_score")
    if anomaly is not None:
        y_pos -= 25
        c.setFont("Helvetica", 11)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.drawString(50, y_pos, "Anomaly Detection Score:")
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.drawString(300, y_pos, f"{anomaly:.4f}")

    # Recommendation section with colored box
    y_pos -= 60
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(50, y_pos, "Recommended Action")
    
    y_pos -= 30
    # Background box for recommendation
    box_color = (1, 0.95, 0.95) if score >= 60 else (1, 0.98, 0.9) if score >= 40 else (0.95, 1, 0.95)
    c.setFillColorRGB(*box_color)
    c.rect(50, y_pos - 45, width - 100, 60, fill=True, stroke=False)
    
    # Border
    c.setStrokeColorRGB(*color)
    c.setLineWidth(2)
    c.rect(50, y_pos - 45, width - 100, 60, fill=False, stroke=True)
    
    alert = tx.get('alert', 'Review transaction for compliance')
    c.setFont("Helvetica-Bold", 12)
    c.setFillColorRGB(0, 0, 0)
    c.drawString(65, y_pos - 20, alert)

    # Footer disclaimer
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(50, 60, "⚠ This report uses advanced machine learning and graph neural networks")
    c.drawString(50, 45, "to identify fraudulent patterns in blockchain transactions.")
    
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(0.7, 0, 0)
    c.drawString(50, 25, "CONFIDENTIAL - FOR AUTHORIZED PERSONNEL ONLY")

    c.showPage()
    c.save()

    return FileResponse(filepath, filename=filename, media_type="application/pdf")


@app.get("/download/bulk")
def download_bulk():
    """Download the last generated bulk output CSV"""
    filepath = os.path.join("data", "processed", "bulk_output.csv")
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="No bulk output file found")
    
    return FileResponse(filepath, filename="bulk_output.csv", media_type="text/csv")


@app.get("/health")
def health_check():
    """Check API health and mapping status"""
    return {
        "status": "healthy",
        "total_transactions": len(secure_to_real),
        "sample_secure_id": list(secure_to_real.keys())[0] if secure_to_real else None,
        "predictor_loaded": predictor is not None
    }


@app.get("/debug/flagged")
def get_flagged_stats():
    """Debug endpoint to check flagged transaction detection"""
    try:
        import math
        
        flagged_count = 0
        high_risk_count = 0
        sample_flagged = []
        
        has_class_column = "class" in df_private.columns
        
        if has_class_column:
            try:
                flagged_txs = df_private[df_private["class"] == 1]
                flagged_count = len(flagged_txs)
                
                for idx, row in flagged_txs.head(5).iterrows():
                    tx_id = row["txId"]
                    secure_id = real_to_secure.get(tx_id, "N/A")
                    risk_score = row.get("risk_score", 0)
                    
                    # Handle NaN/Infinity
                    if pd.isna(risk_score) or math.isinf(risk_score):
                        risk_score = 0.0
                    
                    sample_flagged.append({
                        "txId": int(tx_id),
                        "secure_id": str(secure_id),
                        "risk_score": float(risk_score),
                        "class": int(row.get("class", 2))
                    })
            except Exception as e:
                print(f"Error checking class column: {e}")
                import traceback
                traceback.print_exc()
        
        try:
            high_risk_count = len(df_private[df_private["risk_score"] >= 80])
            
            if flagged_count == 0:
                high_risk_txs = df_private.nlargest(5, 'risk_score')
                for idx, row in high_risk_txs.iterrows():
                    tx_id = row["txId"]
                    secure_id = real_to_secure.get(tx_id, "N/A")
                    risk_score = row.get("risk_score", 0)
                    
                    # Handle NaN/Infinity
                    if pd.isna(risk_score) or math.isinf(risk_score):
                        risk_score = 0.0
                    
                    sample_flagged.append({
                        "txId": int(tx_id),
                        "secure_id": str(secure_id),
                        "risk_score": float(risk_score),
                        "note": "Auto-flagged by risk score"
                    })
        except Exception as e:
            print(f"Error checking risk scores: {e}")
            import traceback
            traceback.print_exc()
        
        return {
            "has_class_column": has_class_column,
            "total_flagged_by_class": int(flagged_count),
            "total_high_risk": int(high_risk_count),
            "sample_flagged_transactions": sample_flagged,
            "columns_available": df_private.columns.tolist()
        }
    except Exception as e:
        print(f"Debug endpoint error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")