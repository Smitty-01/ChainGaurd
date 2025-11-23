import pandas as pd
df2 = pd.read_csv("../data/processed/final_risk_scored.csv")
df2['class'] = 0
df2.loc[df2['risk_score'] >= 80, 'class'] = 1
df2.loc[df2['fraud_prob'] >= 0.85, 'class'] = 1
df2.loc[df2['gnn_fraud_prob'] >= 0.85, 'class'] = 1
df2.to_csv("../data/processed/final_risk_scored.csv", index=False)
print(f"✅ Flagged {(df2['class'] == 1).sum()} transactions in final_risk_scored.csv")


