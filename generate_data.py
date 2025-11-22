"""
Generate JSON data file for frontend
"""

from data_loader import load_stock
from calculation import calculate_ma_dict, calculate_bollinger_bands_dict, calculate_vwap_dict
from price_predictor import get_market_direction_predictions
import json
import pandas as pd
import os

# Local file path
DATA_FILE = r"C:\Users\veenu\Downloads\ongc24-25.csv"

print("Loading data...")
df = load_stock(DATA_FILE)
print(f"Loaded {len(df)} rows")

# Prepare data for chart
chart_data = []
for _, row in df.iterrows():
    volume = row['volume']
    if pd.isna(volume):
        volume = 0
    
    chart_data.append({
        'date': row['date'].strftime('%Y-%m-%d'),
        'open': float(row['open']),
        'high': float(row['high']),
        'low': float(row['low']),
        'close': float(row['close']),
        'volume': float(volume)
    })

# Calculate chart dimensions
min_price = float(df['low'].min())
max_price = float(df['high'].max())
price_range = max_price - min_price
max_volume = float(df['volume'].max())
if pd.isna(max_volume) or max_volume == 0:
    max_volume = 1.0

# Calculate technical indicators
print("Calculating technical indicators...")
ma_10 = calculate_ma_dict(df, period=10)
bollinger_bands = calculate_bollinger_bands_dict(df, period=20, num_std=2.0)
vwap = calculate_vwap_dict(df)

print("[OK] Calculated 10-day MA")
print("[OK] Calculated Bollinger Bands")
print("[OK] Calculated VWAP")

# Calculate price predictions using market direction logic
print("Generating predictions...")
print("Note: Market direction logic to be implemented by user")

predictions = get_market_direction_predictions(df)
print(f"[OK] Generated {len(predictions)} predictions")
if predictions:
    rise_count = sum(1 for p in predictions if p and p.get('prediction') == 'rise')
    fall_count = sum(1 for p in predictions if p and p.get('prediction') == 'fall')
    print(f"  Predictions: {rise_count} rise, {fall_count} fall")

# Create output data structure
output_data = {
    'chartData': chart_data,
    'minPrice': min_price,
    'maxPrice': max_price,
    'priceRange': price_range,
    'maxVolume': max_volume,
    'indicators': {
        'ma10': ma_10,
        'bollingerBands': bollinger_bands,
        'vwap': vwap
    },
    'predictions': predictions
}

# Write to frontend public directory
output_path = os.path.join('frontend', 'public', 'data.json')
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output_data, f, indent=2)

print(f"[OK] Data generated successfully!")
print(f"[OK] File: {output_path}")
print(f"[OK] Data points: {len(chart_data)}")
print(f"[OK] Price range: Rs {min_price:.2f} - Rs {max_price:.2f}")
print(f"\nNext steps:")
print(f"1. cd frontend")
print(f"2. npm install")
print(f"3. npm run dev")


