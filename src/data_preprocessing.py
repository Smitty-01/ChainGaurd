import pandas as pd
import os

RAW_DIR = "../data/raw"
PROCESSED_DIR = "../data/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

def load_raw_data():
    """Load the raw CSVs and return DataFrames."""
    features = pd.read_csv(f"{RAW_DIR}/elliptic_txs_features.csv", header=None)
    classes = pd.read_csv(f"{RAW_DIR}/elliptic_txs_classes.csv")
    edgelist = pd.read_csv(f"{RAW_DIR}/elliptic_txs_edgelist.csv")
    return features, classes, edgelist


def preprocess_data(features, classes):
    """Merge, rename columns, and encode classes.
    Input:
        features: DataFrame with 167 columns (txId + 166 features)
        classes: DataFrame with columns txId + class
    Output:
        data: merged dataframe with clean labels
    """

    # Set column names
    features.rename(columns={0: "txId"}, inplace=True)
    features.columns = ["txId"] + [f"f{i}" for i in range(1, 167)]

    # Merge features & classes
    data = pd.merge(features, classes, on="txId", how="left")

    # Encode labels: 2 → 0 (normal), 1 → 1 (fraud), unknown → -1
    data["binary_label"] = data["class"].replace(
        {"2": 0, "1": 1, "unknown": -1}
    )

    return data


def split_and_save(data):
    """Generate labeled, normal-only, and full datasets."""
    labeled_data = data[data["binary_label"] != -1]
    normal_data = labeled_data[labeled_data["binary_label"] == 0]

    data.to_csv(f"{PROCESSED_DIR}/full_graph_data.csv", index=False)
    labeled_data.to_csv(f"{PROCESSED_DIR}/labeled_data.csv", index=False)
    normal_data.to_csv(f"{PROCESSED_DIR}/normal_data.csv", index=False)


if __name__ == "__main__":
    features, classes, edgelist = load_raw_data()
    data = preprocess_data(features, classes)
    split_and_save(data)

    print("Preprocessing completed!")
    print("Saved files in data/processed:")
    print(os.listdir(PROCESSED_DIR))
