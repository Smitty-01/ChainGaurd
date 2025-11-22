from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File
import io
from fusion import FusionPredictor
import os
import pandas as pd
from fusion_predictor import get_tx_risk, get_batch_risk, get_top_risky
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import io
from fastapi.responses import FileResponse
app = FastAPI(
    title="ChainGuard API",
    description="DeFi Fraud Risk Detection",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow localhost frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
predictor = FusionPredictor()

@app.get("/")
def root():
    return {"message": "🚀 ChainGuard API is running!"}


# ========== 1️⃣ Single Transaction Lookup ==========
@app.get("/tx/{tx_id}")
def get_transaction_risk(tx_id: int):
    result = get_tx_risk(tx_id)
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found in dataset"
        )
    
    return result


# ========== 2️⃣ CSV Upload & Batch Inference ==========
@app.post("/batch")
async def get_batch_results(file: UploadFile = File(...)):
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(400, "Please upload a CSV file")

    df = pd.read_csv(file.file)

    if "txId" not in df.columns:
        raise HTTPException(400, "CSV must contain 'txId' column")

    tx_ids = df["txId"].astype(int).tolist()
    df_results = get_batch_risk(tx_ids)

    return {
        "total_requested": len(tx_ids),
        "found": len(df_results),
        "results": df_results.to_dict(orient="records")
    }


# ========== 3️⃣ Top-N Riskiest ==========
@app.get("/top/{n}")
def top_riskiest(n: int = 10):
    df_top = get_top_risky(n)
    return df_top.to_dict(orient="records")


@app.get("/graph/{tx_id}")
async def get_graph(tx_id: int):
    try:
        # Verify tx exists
        if tx_id not in fusion.df.txId.values:
            raise HTTPException(status_code=404, detail="TxID not found")

        edges = fusion.edgelist
        neighbors = set()

        # collect 1-hop neighbors
        neighbors.update(edges[edges.txId1 == tx_id].txId2.values)
        neighbors.update(edges[edges.txId2 == tx_id].txId1.values)

        nodes = [{"id": int(tx_id), "label": f"TX {tx_id}", "type": "center"}]
        edges_res = []

        # If no neighbors, return single node
        if not neighbors:
            return {"nodes": nodes, "edges": []}

        for n in neighbors:
            nodes.append({"id": int(n), "label": f"TX {n}", "type": "neighbor"})
            edges_res.append({"source": int(tx_id), "target": int(n)})

        return {"nodes": nodes, "edges": edges_res}

    except Exception as e:
        print("Graph Error:", e)
        raise HTTPException(status_code=500, detail="Graph building error")

@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV allowed")

    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))

    if "txId" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must contain 'txId' column")

    results = []

    for _, row in df.iterrows():
        tx_id = int(row["txId"])
        tx = predictor.get_by_id(tx_id)
        if tx:
            results.append(tx)
        else:
            results.append({"txId": tx_id, "error": "Not in database"})

    final_df = pd.DataFrame(results)

    out_path = os.path.join("data", "processed", "bulk_output.csv")
    final_df.to_csv(out_path, index=False)

    return {
        "count": len(results),
        "high_risk": int((final_df["risk_score"] >= 60).sum()),
        "medium_risk": int(((final_df["risk_score"] >= 40) &
                            (final_df["risk_score"] < 60)).sum()),
        "low_risk": int((final_df["risk_score"] < 40).sum()),
        "file": "/download/bulk"  # download endpoint later
    }
@app.get("/report/{tx_id}")
def generate_report(tx_id: int):

    tx = predictor.get_by_id(tx_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    print("TX DATA KEYS:", tx.keys())  # Debug print

    filename = f"tx_{tx_id}_report.pdf"
    out_dir = os.path.join("data", "processed")
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, height - 50, "ChainGuard Risk Intelligence Report")

    c.setFont("Helvetica", 12)
    c.drawString(40, height - 80, f"Transaction ID: {tx_id}")
    c.drawString(40, height - 100, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    score = float(tx["risk_score"])
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 150, f"Risk Score: {score:.2f}")

    c.setFont("Helvetica", 12)
    c.drawString(40, height - 180, f"XGBoost Fraud Probability: {tx['fraud_prob']*100:.2f}%")
    c.drawString(40, height - 200, f"GNN Fraud Probability: {tx['gnn_fraud_prob']*100:.2f}%")

    anomaly = tx.get("anomaly_score_norm") or tx.get("anomaly_score")
    if anomaly is not None:
        c.drawString(40, height - 220, f"Anomaly Score: {anomaly:.4f}")

    if score >= 80: risk = "CRITICAL"
    elif score >= 60: risk = "HIGH"
    elif score >= 40: risk = "MEDIUM"
    else: risk = "LOW"

    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(1, 0.1, 0.1) if risk in ["CRITICAL","HIGH"] else c.setFillColorRGB(1, 0.8, 0)
    c.drawString(40, height - 260, f"Risk Level: {risk}")
    c.setFillColorRGB(0, 0, 0)

    c.setFont("Helvetica", 12)
    c.drawString(40, height - 290, f"Recommended Action: {tx['alert']}")

    c.showPage()
    c.save()

    return FileResponse(filepath, filename=filename, media_type="application/pdf")
