import pandas as pd
import os

class FusionPredictor:
    def __init__(self):
        base = os.path.join(os.getcwd(), "data", "processed")
        path = path = r"D:\redact\data\processed\final_risk_scored.csv"

        print(f"[FusionPredictor] Loading risk table from {path}")
        self.df = pd.read_csv(path)
        print(f"[FusionPredictor] Loaded {len(self.df)} transactions into memory.")

    def get_by_id(self, tx_id: int):
        record = self.df[self.df["txId"] == int(tx_id)]
        if len(record) == 0:
            return None
        return record.iloc[0].to_dict()

    def get_top(self, k=10):
        return (
            self.df.nlargest(k, "risk_score")
            .iloc[:, :10]
            .to_dict(orient="records")
        )
