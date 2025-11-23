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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "..", "data", "raw")

        # Load edge list for graph visualization
        edgelist_path = os.path.join(data_dir, "elliptic_txs_edgelist.csv")
        if os.path.exists(edgelist_path):
            self.edgelist = pd.read_csv(edgelist_path)
            print(f"[FusionPredictor] Loaded {len(self.edgelist)} edges from edgelist")
        else:
            print(f"⚠️ Warning: edgelist not found at {edgelist_path}")
            self.edgelist = pd.DataFrame(columns=["txId1", "txId2"])

        # Load risk table
        risk_path = os.path.join(base_dir, "..", "data", "processed", "final_risk_scored.csv")
        self.df = pd.read_csv(risk_path)
        self.df = self.df.drop_duplicates(subset=["txId"])
        
        # Store both indexed and non-indexed versions
        self._df_indexed = self.df.set_index("txId")
        
        # Debug: Print available columns
        print(f"[FusionPredictor] Loaded {len(self.df)} transactions")
        print(f"[FusionPredictor] Available columns: {self.df.columns.tolist()}")
        
        # Check for class column
        if "class" in self.df.columns:
            flagged_count = (self.df["class"] == 1).sum()
            print(f"[FusionPredictor] Found {flagged_count} flagged transactions")
        else:
            print("[FusionPredictor] ⚠️ No 'class' column found - flagging will use risk scores")

    def get_by_id(self, tx_id: int) -> Optional[Dict[str, Any]]:
        """
        Get transaction data by txId
        Returns dict with all transaction fields or None if not found
        """
        try:
            row = self._df_indexed.loc[tx_id]
            
            # Helper function to handle NaN/Infinity values
            def safe_float(value, default=0.0):
                try:
                    val = float(value)
                    # Check for NaN or Infinity using math
                    import math
                    if math.isnan(val) or math.isinf(val):
                        return default
                    return val
                except (ValueError, TypeError):
                    return default
            
            # Convert row to dictionary with safe float handling
            result = {
                "txId": int(tx_id),
                "fraud_prob": safe_float(row.get("fraud_prob", 0)),
                "gnn_fraud_prob": safe_float(row.get("gnn_fraud_prob", 0)),
                "risk_score": safe_float(row.get("risk_score", 0)),
                "alert": str(row.get("alert", "Review transaction")),
            }
            
            # Add anomaly score (handle different column names)
            if "anomaly_score_norm" in row.index:
                result["anomaly_score_norm"] = safe_float(row["anomaly_score_norm"])
            elif "anomaly_score" in row.index:
                result["anomaly_score"] = safe_float(row["anomaly_score"])
            
            # Add class/flag if exists (1 = illicit, 0 = licit, 2 = unknown)
            if "class" in row.index:
                class_val = row["class"]
                if pd.notna(class_val):
                    try:
                        result["class"] = int(class_val)
                    except (ValueError, TypeError):
                        result["class"] = 2
                else:
                    result["class"] = 2
            
            return result
            
        except KeyError:
            print(f"⚠️ Transaction {tx_id} not found in dataframe")
            return None
        except Exception as e:
            print(f"❌ Error getting transaction {tx_id}: {e}")
            import traceback
            traceback.print_exc()
            return None


# --------------------------------------------------
# SIMPLE MANUAL TEST
# --------------------------------------------------

if __name__ == "__main__":
    # Test the class
    predictor = FusionPredictor()
    
    # Example 1: single txId using class method
    example_tx = int(_risk_df.index[0])
    print("\n[TEST] Single txId lookup using class:", example_tx)
    print(predictor.get_by_id(example_tx))
    
    # Example 2: single txId using standalone function
    print("\n[TEST] Single txId lookup using function:", example_tx)
    print(get_tx_risk(example_tx))

    # Example 3: batch lookup
    example_ids = [int(x) for x in _risk_df.index[:5]]
    print("\n[TEST] Batch lookup:")
    print(get_batch_risk(example_ids))

    # Example 4: top risky
    print("\n[TEST] Top 5 risky:")
    print(get_top_risky(5))