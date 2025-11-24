import os
from typing import List, Optional, Dict, Any
from fastapi import UploadFile, File
import io
import pandas as pd

# --------------------------------------------------
# PATH SETUP
# --------------------------------------------------

# Allow running from project root OR from backend folder
CWD = os.getcwd()
BASE_DIR = os.path.abspath(os.path.join(CWD, "..")) if os.path.basename(CWD) == "backend" else CWD

DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

FINAL_RISK_PATH = os.path.join(DATA_DIR, "final_risk_scored.csv")

if not os.path.exists(FINAL_RISK_PATH):
    raise FileNotFoundError(f"Could not find final_risk_scored.csv at: {FINAL_RISK_PATH}")

# --------------------------------------------------
# LOAD DATA ONCE AT STARTUP
# --------------------------------------------------

print(f"[FusionPredictor] Loading risk table from {FINAL_RISK_PATH}")
_risk_df = pd.read_csv(FINAL_RISK_PATH)

# Basic sanity
required_cols = {
    "txId",
    "fraud_prob",
    "gnn_fraud_prob",
    "anomaly_score_norm",
    "risk_score",
    "alert",
}
missing = required_cols - set(_risk_df.columns)
if missing:
    raise ValueError(f"final_risk_scored.csv is missing required columns: {missing}")

# For fast lookup
_risk_df.set_index("txId", inplace=True)

print(f"[FusionPredictor] Loaded {len(_risk_df):,} transactions into memory.")


# --------------------------------------------------
# PUBLIC API FUNCTIONS
# --------------------------------------------------

def get_tx_risk(tx_id: int) -> Optional[Dict[str, Any]]:
    """Get transaction risk by txId"""
    try:
        row = _risk_df.loc[tx_id]
    except KeyError:
        return None

    return {
        "txId": int(tx_id),
        "fraud_prob": float(row["fraud_prob"]),
        "gnn_fraud_prob": float(row["gnn_fraud_prob"]),
        "anomaly_score_norm": float(row["anomaly_score_norm"]),
        "risk_score": float(row["risk_score"]),
        "alert": str(row["alert"]),
    }


def get_batch_risk(tx_ids: List[int]) -> pd.DataFrame:
    """Get batch transaction risks"""
    seen = set()
    ordered_ids = []
    for tid in tx_ids:
        if tid not in seen:
            seen.add(tid)
            ordered_ids.append(tid)

    subset = _risk_df.loc[_risk_df.index.intersection(ordered_ids)].reset_index()
    return subset


def get_top_risky(n: int = 10) -> pd.DataFrame:
    """Get top N riskiest transactions"""
    return _risk_df.reset_index().sort_values("risk_score", ascending=False).head(n)


# --------------------------------------------------
# FUSION PREDICTOR CLASS
# --------------------------------------------------



class FusionPredictor:
    def __init__(self):
        """Initialize the fusion predictor with risk scores"""
        base_dir = os.getcwd()
        data_dir = os.path.join(base_dir, "data", "processed")
        
        # Load risk scores
        risk_path = os.path.join(data_dir, "final_risk_scored.csv")
        
        if not os.path.exists(risk_path):
            raise FileNotFoundError(f"Risk scores not found at: {risk_path}")
        
        print(f"[FusionPredictor] Loading risk table from {risk_path}")
        self.df = pd.read_csv(risk_path)
        
        # Remove duplicates
        self.df = self.df.drop_duplicates(subset=["txId"])
        
        # Create indexed version for fast lookups
        self._df_indexed = self.df.set_index("txId")
        
        print(f"[FusionPredictor] Loaded {len(self.df):,} transactions")
        
        # Load edgelist for graph visualization
        edgelist_path = os.path.join(base_dir, "data", "raw", "elliptic_txs_edgelist.csv")
        if os.path.exists(edgelist_path):
            self.edgelist = pd.read_csv(edgelist_path)
            print(f"[FusionPredictor] Loaded {len(self.edgelist):,} edges")
        else:
            print(f"⚠️ Warning: edgelist not found")
            self.edgelist = pd.DataFrame(columns=["txId1", "txId2"])

    def get_by_id(self, tx_id: int) -> Optional[Dict[str, Any]]:
        """Get transaction risk data by txId"""
        try:
            row = self._df_indexed.loc[tx_id]
            
            # Safe float conversion
            def safe_float(val, default=0.0):
                try:
                    v = float(val)
                    if pd.isna(v) or not pd.api.types.is_number(v):
                        return default
                    return v
                except:
                    return default
            
            return {
                "txId": int(tx_id),
                "fraud_prob": safe_float(row.get("fraud_prob", 0)),
                "gnn_fraud_prob": safe_float(row.get("gnn_fraud_prob", 0)),
                "anomaly_score_norm": safe_float(row.get("anomaly_score_norm", 0)),
                "risk_score": safe_float(row.get("risk_score", 0)),
                "alert": str(row.get("alert", "Review transaction")),
                "is_fraud_predicted": int(row.get("is_fraud_predicted", 0)),
                "class": int(row.get("class", 2)) if pd.notna(row.get("class")) else 2,
            }
        except KeyError:
            print(f"⚠️ Transaction {tx_id} not found")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

    def get_top(self, k: int = 10) -> List[Dict[str, Any]]:
        """Get top K riskiest transactions"""
        top = self.df.nlargest(k, "risk_score")
        
        results = []
        for _, row in top.iterrows():
            results.append({
                "txId": int(row["txId"]),
                "risk_score": float(row["risk_score"]),
                "fraud_prob": float(row.get("fraud_prob", 0)),
                "gnn_fraud_prob": float(row.get("gnn_fraud_prob", 0)),
                "alert": str(row.get("alert", "Review")),
                "class": int(row.get("class", 2)) if pd.notna(row.get("class")) else 2,
            })
        
        return results
    
    def get_batch(self, tx_ids: List[int]) -> pd.DataFrame:
        """Get multiple transactions at once"""
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for tid in tx_ids:
            if tid not in seen:
                seen.add(tid)
                unique_ids.append(tid)
        
        # Get subset
        subset = self._df_indexed.loc[
            self._df_indexed.index.intersection(unique_ids)
        ].reset_index()
        
        return subset


# === Test the predictor ===
if __name__ == "__main__":
    predictor = FusionPredictor()
    
    # Test single lookup
    first_tx = int(predictor.df["txId"].iloc[0])
    print("\n[TEST] Single transaction:")
    print(predictor.get_by_id(first_tx))
    
    # Test top risky
    print("\n[TEST] Top 5 risky:")
    for tx in predictor.get_top(5):
        print(f"  Tx {tx['txId']}: Risk={tx['risk_score']:.1f}, Alert={tx['alert']}")


