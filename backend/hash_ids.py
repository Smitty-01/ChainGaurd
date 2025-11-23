import pandas as pd
import hashlib

SALT = b"chainguard-privacy-123"

def hash_id(raw):
    m = hashlib.sha256()
    m.update(SALT)
    m.update(str(raw).encode())
    return m.hexdigest()

df = pd.read_csv("../data/processed/final_risk_scored.csv")

df["secure_id"] = df["txId"].apply(hash_id)

# backend keeps original real txId (private)
df.to_csv("../data/processed/final_risk_scored_private.csv", index=False)

# frontend only uses secure version
df_public = df.drop(columns=["txId"])
df_public.to_csv("../data/processed/final_risk_scored_public.csv", index=False)

print("🔐 IDs hashed successfully!")
print("→ public file created: final_risk_scored_public.csv")
