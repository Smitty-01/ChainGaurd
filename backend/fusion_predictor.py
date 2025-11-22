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
    """
    Look up a single transaction / wallet by txId and return its risk info.

    Parameters
    ----------
    tx_id : int
        The transaction ID / node ID in the Elliptic dataset.

    Returns
    -------
    dict or None
        Example:
        {
          "txId": 72631257,
          "fraud_prob": 0.9998,
          "gnn_fraud_prob": 0.64,
          "anomaly_score_norm": 0.08,
          "risk_score": 71.2,
          "alert": "🟡 High Risk — Add to Watchlist"
        }
        Returns None if txId not found.
    """
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
    """
    Get risk info for a list of txIds.
    Useful for CSV uploads from the frontend.

    Parameters
    ----------
    tx_ids : List[int]

    Returns
    -------
    pandas.DataFrame
        Columns: txId, fraud_prob, gnn_fraud_prob,
                 anomaly_score_norm, risk_score, alert

        Rows where txId was not found are dropped.
        You can handle 'missing' yourself in the API layer.
    """
    # Deduplicate while preserving order
    seen = set()
    ordered_ids = []
    for tid in tx_ids:
        if tid not in seen:
            seen.add(tid)
            ordered_ids.append(tid)

    subset = _risk_df.loc[_risk_df.index.intersection(ordered_ids)].reset_index()
    return subset


def get_top_risky(n: int = 10) -> pd.DataFrame:
    """
    Convenience helper: return top-N riskiest transactions
    for dashboards / default view.

    Returns
    -------
    DataFrame with same columns as final_risk_scored, sorted by risk_score desc.
    """
    return _risk_df.reset_index().sort_values("risk_score", ascending=False).head(n)


# --------------------------------------------------
# SIMPLE MANUAL TEST
# --------------------------------------------------

if __name__ == "__main__":
    # Example 1: single txId
    example_tx = int(_risk_df.index[0])
    print("\n[TEST] Single txId lookup:", example_tx)
    print(get_tx_risk(example_tx))

    # Example 2: batch lookup
    example_ids = [int(x) for x in _risk_df.index[:5]]
    print("\n[TEST] Batch lookup:")
    print(get_batch_risk(example_ids))

    # Example 3: top risky
    print("\n[TEST] Top 5 risky:")
    print(get_top_risky(5))
