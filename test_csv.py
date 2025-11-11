import pandas as pd
import sys

file_path = r"C:\Users\veenu\Downloads\ongc24-25.csv"

print(f"Testing CSV file: {file_path}")
sys.stdout.flush()

try:
    df = pd.read_csv(file_path)
    print(f"✓ Successfully read CSV")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    print(f"  First few rows:")
    print(df.head())
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

