"""
Generate HTML candlestick chart from stock data
"""

from data_loader import load_stock
from calculation import calculate_ma_dict, calculate_bollinger_bands_dict, calculate_vwap_dict
from price_predictor import get_market_direction_predictions
import json
import pandas as pd

# Local file path
DATA_FILE = r"C:\Users\veenu\Downloads\ongc24-25.csv"

# Load data
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

print(f"Price range: Rs {min_price:.2f} - Rs {max_price:.2f}")
print(f"Max volume: {max_volume:,.0f}")

# Calculate technical indicators
print("Calculating technical indicators...")
ma_10 = calculate_ma_dict(df, period=10)
bollinger_bands = calculate_bollinger_bands_dict(df, period=20, num_std=2.0)
vwap = calculate_vwap_dict(df)
print("[OK] Calculated 10-day MA")
print("[OK] Calculated Bollinger Bands")
print("[OK] Calculated VWAP")
print(f"  VWAP sample (first 3): {vwap[:3]}")
print(f"  VWAP sample (last 3): {vwap[-3:]}")

# Calculate price predictions using market direction logic
print("Generating predictions...")
print("Note: Market direction logic to be implemented by user")

predictions = get_market_direction_predictions(df)
print(f"[OK] Generated {len(predictions)} predictions")
if predictions:
    rise_count = sum(1 for p in predictions if p and p.get('prediction') == 'rise')
    fall_count = sum(1 for p in predictions if p and p.get('prediction') == 'fall')
    print(f"  Predictions: {rise_count} rise, {fall_count} fall")

# Generate HTML with embedded JavaScript
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3D Candlestick Chart - Stock Analysis</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }}

        h1 {{
            text-align: center;
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}

        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }}

        .chart-container {{
            position: relative;
            width: 100%;
            height: 700px;
            background: #f8f9fa;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }}

        #chartCanvas {{
            width: 100%;
            height: 100%;
            cursor: crosshair;
            display: block;
        }}

        .tooltip {{
            position: absolute;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 12px 15px;
            border-radius: 8px;
            font-size: 14px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            min-width: 200px;
        }}

        .tooltip.show {{
            opacity: 1;
        }}

        .tooltip .label {{
            font-weight: bold;
            color: #4CAF50;
            margin-right: 8px;
            display: inline-block;
            width: 70px;
        }}

        .tooltip .value {{
            color: #fff;
        }}

        .tooltip .row {{
            margin: 5px 0;
        }}

        .legend {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
            padding: 15px;
            background: #f0f0f0;
            border-radius: 8px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .legend-color {{
            width: 30px;
            height: 20px;
            border: 2px solid #333;
            border-radius: 3px;
        }}

        .legend-color.bullish {{
            background: #4CAF50;
        }}

        .legend-color.bearish {{
            background: #f44336;
        }}
        
        .indicator-legend {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 10px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 8px;
        }}
        
        .indicator-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }}
        
        .indicator-line {{
            width: 30px;
            height: 2px;
            border-radius: 1px;
        }}
        
        .indicator-line.ma10 {{
            background: #f44336;
        }}
        
        .indicator-line.vwap {{
            background: #FFC107;
            border-top: 2px dashed #FFC107;
        }}
        
        .indicator-line.bb {{
            background: rgba(255, 152, 0, 0.6);
        }}
        
        .prediction-legend {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 10px;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 8px;
        }}
        
        .prediction-marker {{
            width: 0;
            height: 0;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
        }}
        
        .prediction-marker.fall-marker {{
            border-top: 10px solid #f44336;
            border-bottom: none;
        }}
        
        .prediction-marker.rise-marker {{
            border-bottom: 10px solid #4CAF50;
            border-top: none;
        }}

        .info-panel {{
            margin-top: 20px;
            padding: 15px;
            background: #e8f5e9;
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
        }}

        .info-panel p {{
            margin: 5px 0;
            color: #2e7d32;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 3D Candlestick Chart</h1>
        <p class="subtitle">Interactive Stock Analysis - Hover over candles to see details</p>
        
        <div class="chart-container">
            <canvas id="chartCanvas"></canvas>
            <div id="tooltip" class="tooltip"></div>
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-color bullish"></div>
                <span>Bullish (Open &lt; Close)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color bearish"></div>
                <span>Bearish (Open &gt; Close)</span>
            </div>
        </div>

        <div class="indicator-legend">
            <div class="indicator-item">
                <div class="indicator-line ma10"></div>
                <span>MA 10</span>
            </div>
            <div class="indicator-item">
                <div class="indicator-line vwap"></div>
                <span>VWAP</span>
            </div>
            <div class="indicator-item">
                <div class="indicator-line bb"></div>
                <span>Bollinger Bands</span>
            </div>
        </div>

        <div class="prediction-legend">
            <div class="legend-item">
                <div class="prediction-marker fall-marker"></div>
                <span>Expected Fall (Red ↑)</span>
            </div>
            <div class="legend-item">
                <div class="prediction-marker rise-marker"></div>
                <span>Expected Rise (Green ↓)</span>
            </div>
        </div>

        <div class="info-panel">
            <p><strong>Total Data Points:</strong> {len(chart_data)} days</p>
            <p><strong>Price Range:</strong> ₹{min_price:.2f} - ₹{max_price:.2f}</p>
            <p><strong>Max Volume:</strong> {max_volume:,.0f}</p>
        </div>
    </div>

    <script>
        // Chart data
        const data = {json.dumps(chart_data)};
        const minPrice = {min_price};
        const maxPrice = {max_price};
        const priceRange = {price_range};
        const maxVolume = {max_volume};
        const dataLength = {len(chart_data)};
        
        // Technical indicators
        const indicators = {{
            ma10: {json.dumps(ma_10)},
            bollingerBands: {json.dumps(bollinger_bands)},
            vwap: {json.dumps(vwap)}
        }};
        
        // Price predictions
        const predictions = {json.dumps(predictions)};

        console.log('Data loaded:', dataLength, 'candles');
        console.log('Price range:', minPrice, 'to', maxPrice);
        console.log('First candle:', data[0]);
        console.log('Last candle:', data[dataLength - 1]);
        console.log('VWAP data:', indicators.vwap ? indicators.vwap.length + ' points' : 'missing');
        if (indicators.vwap && indicators.vwap.length > 0) {{
            console.log('First VWAP:', indicators.vwap[0]);
            console.log('Last VWAP:', indicators.vwap[indicators.vwap.length - 1]);
        }}

        // Canvas setup
        const canvas = document.getElementById('chartCanvas');
        const ctx = canvas.getContext('2d');
        const tooltip = document.getElementById('tooltip');

        // Set canvas size
        function resizeCanvas() {{
            const container = canvas.parentElement;
            if (!container) {{
                console.error('Container not found');
                return;
            }}
            const width = container.clientWidth || container.offsetWidth || 1200;
            const height = container.clientHeight || container.offsetHeight || 700;
            canvas.width = width;
            canvas.height = height;
            console.log('Canvas resized to:', width, 'x', height);
            drawChart();
        }}

        window.addEventListener('resize', resizeCanvas);
        
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', () => {{
                setTimeout(resizeCanvas, 100);
            }});
        }} else {{
            setTimeout(resizeCanvas, 100);
        }}

        // Chart dimensions - Y-axis on the right
        const padding = {{ top: 50, right: 100, bottom: 80, left: 80 }};
        let chartWidth, chartHeight, chartX, chartY;

        function updateDimensions() {{
            chartWidth = canvas.width - padding.left - padding.right;
            chartHeight = canvas.height - padding.top - padding.bottom;
            chartX = padding.left;
            chartY = padding.top;
        }}

        // Convert price to Y coordinate
        function priceToY(price) {{
            return chartY + chartHeight - ((price - minPrice) / priceRange) * chartHeight;
        }}

        // Convert index to X coordinate (with zoom support)
        function indexToX(index) {{
            const visible = getVisibleRange();
            if (visible.count <= 1) return chartX;
            const relativeIndex = index - visible.start;
            return chartX + (relativeIndex / (visible.count - 1)) * chartWidth;
        }}

        // Convert volume to depth (3D effect)
        function volumeToDepth(volume) {{
            if (maxVolume === 0) return 0;
            return Math.max(2, (volume / maxVolume) * 20); // Max depth of 20 pixels
        }}

        // Draw axis
        function drawAxes() {{
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 2;

            // Y-axis (price) - on the right side
            const yAxisX = chartX + chartWidth;
            ctx.beginPath();
            ctx.moveTo(yAxisX, chartY);
            ctx.lineTo(yAxisX, chartY + chartHeight);
            ctx.stroke();

            // X-axis (date)
            ctx.beginPath();
            ctx.moveTo(chartX, chartY + chartHeight);
            ctx.lineTo(chartX + chartWidth, chartY + chartHeight);
            ctx.stroke();

            // Y-axis labels - on the right side
            ctx.fillStyle = '#333';
            ctx.font = '12px Arial';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';

            const numLabels = 10;
            for (let i = 0; i <= numLabels; i++) {{
                const price = minPrice + (priceRange * i / numLabels);
                const y = priceToY(price);
                ctx.fillText('₹' + price.toFixed(2), yAxisX + 10, y);
                
                // Grid line
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(chartX, y);
                ctx.lineTo(chartX + chartWidth, y);
                ctx.stroke();
            }}

            // X-axis labels (dates)
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 2;
            ctx.fillStyle = '#333';

            const dateStep = Math.max(1, Math.floor(dataLength / 12));
            for (let i = 0; i < dataLength; i += dateStep) {{
                const x = indexToX(i);
                const date = new Date(data[i].date + 'T00:00:00');
                const dateStr = date.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }});
                
                ctx.fillText(dateStr, x, chartY + chartHeight + 10);
                
                // Grid line
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x, chartY);
                ctx.lineTo(x, chartY + chartHeight);
                ctx.stroke();
            }}
        }}

        // Draw 3D candlestick
        function drawCandle(index, candle, x, depth) {{
            // Validate inputs
            if (!candle || typeof candle.open !== 'number' || typeof candle.close !== 'number') {{
                console.warn('Invalid candle data at index', index, candle);
                return null;
            }}
            
            const openY = priceToY(candle.open);
            const closeY = priceToY(candle.close);
            const highY = priceToY(candle.high);
            const lowY = priceToY(candle.low);
            
            // Validate Y coordinates
            if (isNaN(openY) || isNaN(closeY) || isNaN(highY) || isNaN(lowY) || isNaN(x)) {{
                console.warn('Invalid coordinates at index', index, {{openY, closeY, highY, lowY, x}});
                return null;
            }}
            
            const isBullish = candle.close > candle.open;
            const bodyTop = Math.min(openY, closeY);
            const bodyBottom = Math.max(openY, closeY);
            const bodyHeight = Math.max(1, bodyBottom - bodyTop);
            const candleWidth = Math.max(2, (chartWidth / dataLength) * 0.8);

            // Draw wick (high-low line)
            ctx.strokeStyle = isBullish ? '#4CAF50' : '#f44336';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x + candleWidth / 2, highY);
            ctx.lineTo(x + candleWidth / 2, lowY);
            ctx.stroke();

            // Draw 3D body
            if (isBullish) {{
                // Bullish (green)
                ctx.fillStyle = '#4CAF50';
                ctx.strokeStyle = '#2e7d32';
                ctx.lineWidth = 2;
            }} else {{
                // Bearish (red)
                ctx.fillStyle = '#f44336';
                ctx.strokeStyle = '#c62828';
                ctx.lineWidth = 2;
            }}

            // Draw body
            ctx.beginPath();
            ctx.rect(x, bodyTop, candleWidth, bodyHeight);
            ctx.fill();
            ctx.stroke();

            // 3D depth effect - draw side faces
            if (depth > 0) {{
                ctx.fillStyle = isBullish ? 'rgba(76, 175, 80, 0.5)' : 'rgba(244, 67, 54, 0.5)';
                
                // Right face
                ctx.beginPath();
                ctx.moveTo(x + candleWidth, bodyTop);
                ctx.lineTo(x + candleWidth + depth, bodyTop - depth);
                ctx.lineTo(x + candleWidth + depth, bodyBottom - depth);
                ctx.lineTo(x + candleWidth, bodyBottom);
                ctx.closePath();
                ctx.fill();

                // Top face
                ctx.beginPath();
                ctx.moveTo(x, bodyTop);
                ctx.lineTo(x + depth, bodyTop - depth);
                ctx.lineTo(x + candleWidth + depth, bodyTop - depth);
                ctx.lineTo(x + candleWidth, bodyTop);
                ctx.closePath();
                ctx.fill();

                // Shadow
                ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
                ctx.beginPath();
                ctx.rect(x + depth, chartY + chartHeight - depth, candleWidth, depth);
                ctx.fill();
            }}

            return {{
                x: x,
                y: Math.min(highY, bodyTop),
                width: candleWidth + depth,
                height: Math.abs(lowY - highY),
                index: index,
                candle: candle
            }};
        }}

        // Draw Moving Average (MA10)
        function drawMA10() {{
            if (!indicators || !indicators.ma10) return;
            
            ctx.strokeStyle = '#f44336';
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            let firstPoint = true;
            for (let i = 0; i < indicators.ma10.length; i++) {{
                const ma = indicators.ma10[i];
                if (ma && ma.ma !== null && ma.ma !== undefined) {{
                    const x = indexToX(i);
                    const y = priceToY(ma.ma);
                    
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
        }}

        // Draw Bollinger Bands
        function drawBollingerBands() {{
            if (!indicators || !indicators.bollingerBands) return;
            
            const bb = indicators.bollingerBands;
            
            // Draw upper band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.6)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            let firstPoint = true;
            for (let i = 0; i < bb.length; i++) {{
                if (bb[i] && bb[i].upper !== null) {{
                    const x = indexToX(i);
                    const y = priceToY(bb[i].upper);
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            
            // Draw middle band (SMA)
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.8)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            firstPoint = true;
            for (let i = 0; i < bb.length; i++) {{
                if (bb[i] && bb[i].middle !== null) {{
                    const x = indexToX(i);
                    const y = priceToY(bb[i].middle);
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            
            // Draw lower band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.6)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            firstPoint = true;
            for (let i = 0; i < bb.length; i++) {{
                if (bb[i] && bb[i].lower !== null) {{
                    const x = indexToX(i);
                    const y = priceToY(bb[i].lower);
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            ctx.setLineDash([]);
            
            // Fill between bands
            ctx.fillStyle = 'rgba(255, 152, 0, 0.1)';
            ctx.beginPath();
            firstPoint = true;
            for (let i = 0; i < bb.length; i++) {{
                if (bb[i] && bb[i].upper !== null && bb[i].lower !== null) {{
                    const x = indexToX(i);
                    const upperY = priceToY(bb[i].upper);
                    const lowerY = priceToY(bb[i].lower);
                    if (firstPoint) {{
                        ctx.moveTo(x, upperY);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, upperY);
                    }}
                }}
            }}
            for (let i = bb.length - 1; i >= 0; i--) {{
                if (bb[i] && bb[i].upper !== null && bb[i].lower !== null) {{
                    const x = indexToX(i);
                    const lowerY = priceToY(bb[i].lower);
                    ctx.lineTo(x, lowerY);
                }}
            }}
            ctx.closePath();
            ctx.fill();
        }}

        // Draw VWAP
        function drawVWAP() {{
            if (!indicators || !indicators.vwap) return;
            
            ctx.strokeStyle = '#FFC107';
            ctx.lineWidth = 2;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            
            let firstPoint = true;
            for (let i = 0; i < indicators.vwap.length; i++) {{
                const vwap = indicators.vwap[i];
                if (vwap && vwap.vwap !== null && vwap.vwap !== undefined && !isNaN(vwap.vwap)) {{
                    const x = indexToX(i);
                    const y = priceToY(vwap.vwap);
                    
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            ctx.setLineDash([]);
        }}
        
        // Draw VWAP for visible range
        function drawVWAPForRange(startIdx, endIdx, minP, maxP, priceRng) {{
            if (!indicators || !indicators.vwap) return;
            
            const priceToYLocal = (price) => chartY + chartHeight - ((price - minP) / priceRng) * chartHeight;
            const indexToXLocal = (idx) => {{
                const visible = getVisibleRange();
                if (visible.count <= 1) return chartX;
                const relativeIdx = idx - visible.start;
                return chartX + (relativeIdx / (visible.count - 1)) * chartWidth;
            }};
            
            ctx.strokeStyle = '#FFC107';
            ctx.lineWidth = 2;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            
            let firstPoint = true;
            for (let i = startIdx; i < endIdx && i < indicators.vwap.length; i++) {{
                const vwap = indicators.vwap[i];
                if (vwap && vwap.vwap !== null && vwap.vwap !== undefined && !isNaN(vwap.vwap)) {{
                    const x = indexToXLocal(i);
                    const y = priceToYLocal(vwap.vwap);
                    
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            ctx.setLineDash([]);
        }}
        
        // Draw MA10 for visible range
        function drawMA10ForRange(startIdx, endIdx, minP, maxP, priceRng) {{
            if (!indicators || !indicators.ma10) return;
            
            const priceToYLocal = (price) => chartY + chartHeight - ((price - minP) / priceRng) * chartHeight;
            const indexToXLocal = (idx) => {{
                const visible = getVisibleRange();
                if (visible.count <= 1) return chartX;
                const relativeIdx = idx - visible.start;
                return chartX + (relativeIdx / (visible.count - 1)) * chartWidth;
            }};
            
            ctx.strokeStyle = '#f44336';
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            let firstPoint = true;
            for (let i = startIdx; i < endIdx && i < indicators.ma10.length; i++) {{
                const ma = indicators.ma10[i];
                if (ma && ma.ma !== null && ma.ma !== undefined && !isNaN(ma.ma)) {{
                    const x = indexToXLocal(i);
                    const y = priceToYLocal(ma.ma);
                    
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
        }}
        
        // Draw Bollinger Bands for visible range
        function drawBollingerBandsForRange(startIdx, endIdx, minP, maxP, priceRng) {{
            if (!indicators || !indicators.bollingerBands) return;
            
            const bb = indicators.bollingerBands;
            const priceToYLocal = (price) => chartY + chartHeight - ((price - minP) / priceRng) * chartHeight;
            const indexToXLocal = (idx) => {{
                const visible = getVisibleRange();
                if (visible.count <= 1) return chartX;
                const relativeIdx = idx - visible.start;
                return chartX + (relativeIdx / (visible.count - 1)) * chartWidth;
            }};
            
            // Draw upper band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.6)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            let firstPoint = true;
            for (let i = startIdx; i < endIdx && i < bb.length; i++) {{
                if (bb[i] && bb[i].upper !== null && !isNaN(bb[i].upper)) {{
                    const x = indexToXLocal(i);
                    const y = priceToYLocal(bb[i].upper);
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            
            // Draw middle band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.8)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            firstPoint = true;
            for (let i = startIdx; i < endIdx && i < bb.length; i++) {{
                if (bb[i] && bb[i].middle !== null && !isNaN(bb[i].middle)) {{
                    const x = indexToXLocal(i);
                    const y = priceToYLocal(bb[i].middle);
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            
            // Draw lower band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.6)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            firstPoint = true;
            for (let i = startIdx; i < endIdx && i < bb.length; i++) {{
                if (bb[i] && bb[i].lower !== null && !isNaN(bb[i].lower)) {{
                    const x = indexToXLocal(i);
                    const y = priceToYLocal(bb[i].lower);
                    if (firstPoint) {{
                        ctx.moveTo(x, y);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, y);
                    }}
                }}
            }}
            ctx.stroke();
            ctx.setLineDash([]);
            
            // Fill between bands
            ctx.fillStyle = 'rgba(255, 152, 0, 0.1)';
            ctx.beginPath();
            firstPoint = true;
            for (let i = startIdx; i < endIdx && i < bb.length; i++) {{
                if (bb[i] && bb[i].upper !== null && bb[i].lower !== null && !isNaN(bb[i].upper) && !isNaN(bb[i].lower)) {{
                    const x = indexToXLocal(i);
                    const upperY = priceToYLocal(bb[i].upper);
                    if (firstPoint) {{
                        ctx.moveTo(x, upperY);
                        firstPoint = false;
                    }} else {{
                        ctx.lineTo(x, upperY);
                    }}
                }}
            }}
            for (let i = endIdx - 1; i >= startIdx && i >= 0 && i < bb.length; i--) {{
                if (bb[i] && bb[i].upper !== null && bb[i].lower !== null && !isNaN(bb[i].upper) && !isNaN(bb[i].lower)) {{
                    const x = indexToXLocal(i);
                    const lowerY = priceToYLocal(bb[i].lower);
                    ctx.lineTo(x, lowerY);
                }}
            }}
            ctx.closePath();
            ctx.fill();
        }}
        
        // Draw axes with custom price range
        function drawAxesWithRange(minP, maxP, priceRng) {{
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 2;

            // Y-axis (price) - on the right side
            const yAxisX = chartX + chartWidth;
            ctx.beginPath();
            ctx.moveTo(yAxisX, chartY);
            ctx.lineTo(yAxisX, chartY + chartHeight);
            ctx.stroke();

            // X-axis (date)
            ctx.beginPath();
            ctx.moveTo(chartX, chartY + chartHeight);
            ctx.lineTo(chartX + chartWidth, chartY + chartHeight);
            ctx.stroke();

            // Y-axis labels - on the right side
            ctx.fillStyle = '#333';
            ctx.font = '12px Arial';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';

            const numLabels = 10;
            for (let i = 0; i <= numLabels; i++) {{
                const price = minP + (priceRng * i / numLabels);
                const y = chartY + chartHeight - ((price - minP) / priceRng) * chartHeight;
                ctx.fillText('₹' + price.toFixed(2), yAxisX + 10, y);
                
                // Grid line
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(chartX, y);
                ctx.lineTo(chartX + chartWidth, y);
                ctx.stroke();
            }}

            // X-axis labels (dates)
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 2;
            ctx.fillStyle = '#333';

            const visible = getVisibleRange();
            const dateStep = Math.max(1, Math.floor(visible.count / 12));
            for (let i = visible.start; i < visible.end; i += dateStep) {{
                const x = indexToX(i);
                const date = new Date(data[i].date + 'T00:00:00');
                const dateStr = date.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }});
                
                ctx.fillText(dateStr, x, chartY + chartHeight + 10);
                
                // Grid line
                ctx.strokeStyle = '#e0e0e0';
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x, chartY);
                ctx.lineTo(x, chartY + chartHeight);
                ctx.stroke();
            }}
        }}
        
        // Draw prediction markers
        function drawPredictionMarkers(startIdx, endIdx, minP, maxP, priceRng) {{
            if (!predictions || predictions.length === 0) return;
            
            const priceToYLocal = (price) => chartY + chartHeight - ((price - minP) / priceRng) * chartHeight;
            const indexToXLocal = (idx) => {{
                const visible = getVisibleRange();
                if (visible.count <= 1) return chartX;
                const relativeIdx = idx - visible.start;
                return chartX + (relativeIdx / (visible.count - 1)) * chartWidth;
            }};
            
            for (let i = startIdx; i < endIdx && i < predictions.length; i++) {{
                const pred = predictions[i];
                if (!pred || !pred.prediction) continue;
                
                const candle = data[i];
                if (!candle) continue;
                
                const x = indexToXLocal(i);
                const candleWidth = Math.max(2, (chartWidth / (endIdx - startIdx)) * 0.8);
                const markerSize = 8;
                const markerOffset = 5;
                const textOffset = 15;
                
                if (pred.prediction === 'fall') {{
                    // Red marker above candle (expected to fall)
                    const highY = priceToYLocal(candle.high);
                    const markerY = highY - markerOffset - markerSize;
                    const textY = markerY - textOffset;
                    
                    ctx.fillStyle = '#f44336';
                    ctx.strokeStyle = '#c62828';
                    ctx.lineWidth = 2;
                    
                    // Draw downward triangle
                    ctx.beginPath();
                    ctx.moveTo(x + candleWidth / 2, markerY);
                    ctx.lineTo(x + candleWidth / 2 - markerSize, markerY + markerSize);
                    ctx.lineTo(x + candleWidth / 2 + markerSize, markerY + markerSize);
                    ctx.closePath();
                    ctx.fill();
                    ctx.stroke();
                    
                    // Draw case name text above marker
                    if (pred.case_name) {{
                        ctx.fillStyle = '#f44336';
                        ctx.font = '10px Arial';
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'bottom';
                        ctx.fillText(pred.case_name, x + candleWidth / 2, textY);
                    }}
                }} else if (pred.prediction === 'rise') {{
                    // Green marker below candle (expected to rise)
                    const lowY = priceToYLocal(candle.low);
                    const markerY = lowY + markerOffset + markerSize;
                    const textY = markerY + textOffset;
                    
                    ctx.fillStyle = '#4CAF50';
                    ctx.strokeStyle = '#2e7d32';
                    ctx.lineWidth = 2;
                    
                    // Draw upward triangle
                    ctx.beginPath();
                    ctx.moveTo(x + candleWidth / 2, markerY);
                    ctx.lineTo(x + candleWidth / 2 - markerSize, markerY - markerSize);
                    ctx.lineTo(x + candleWidth / 2 + markerSize, markerY - markerSize);
                    ctx.closePath();
                    ctx.fill();
                    ctx.stroke();
                    
                    // Draw case name text below marker
                    if (pred.case_name) {{
                        ctx.fillStyle = '#4CAF50';
                        ctx.font = '10px Arial';
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'top';
                        ctx.fillText(pred.case_name, x + candleWidth / 2, textY);
                    }}
                }}
            }}
        }}
        
        // Draw candle for visible range
        function drawCandleForRange(index, candle, x, depth, minP, maxP, priceRng) {{
            const priceToYLocal = (price) => chartY + chartHeight - ((price - minP) / priceRng) * chartHeight;
            
            // Validate inputs
            if (!candle || typeof candle.open !== 'number' || typeof candle.close !== 'number') {{
                return null;
            }}
            
            const openY = priceToYLocal(candle.open);
            const closeY = priceToYLocal(candle.close);
            const highY = priceToYLocal(candle.high);
            const lowY = priceToYLocal(candle.low);
            
            // Validate Y coordinates
            if (isNaN(openY) || isNaN(closeY) || isNaN(highY) || isNaN(lowY) || isNaN(x)) {{
                return null;
            }}
            
            const isBullish = candle.close > candle.open;
            const bodyTop = Math.min(openY, closeY);
            const bodyBottom = Math.max(openY, closeY);
            const bodyHeight = Math.max(1, bodyBottom - bodyTop);
            const visible = getVisibleRange();
            const candleWidth = Math.max(2, (chartWidth / visible.count) * 0.8);

            // Draw wick (high-low line)
            ctx.strokeStyle = isBullish ? '#4CAF50' : '#f44336';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(x + candleWidth / 2, highY);
            ctx.lineTo(x + candleWidth / 2, lowY);
            ctx.stroke();

            // Draw 3D body
            if (isBullish) {{
                ctx.fillStyle = '#4CAF50';
                ctx.strokeStyle = '#2e7d32';
                ctx.lineWidth = 2;
            }} else {{
                ctx.fillStyle = '#f44336';
                ctx.strokeStyle = '#c62828';
                ctx.lineWidth = 2;
            }}

            // Draw body
            ctx.beginPath();
            ctx.rect(x, bodyTop, candleWidth, bodyHeight);
            ctx.fill();
            ctx.stroke();

            // 3D depth effect - draw side faces
            if (depth > 0) {{
                ctx.fillStyle = isBullish ? 'rgba(76, 175, 80, 0.5)' : 'rgba(244, 67, 54, 0.5)';
                
                // Right face
                ctx.beginPath();
                ctx.moveTo(x + candleWidth, bodyTop);
                ctx.lineTo(x + candleWidth + depth, bodyTop - depth);
                ctx.lineTo(x + candleWidth + depth, bodyBottom - depth);
                ctx.lineTo(x + candleWidth, bodyBottom);
                ctx.closePath();
                ctx.fill();

                // Top face
                ctx.beginPath();
                ctx.moveTo(x, bodyTop);
                ctx.lineTo(x + depth, bodyTop - depth);
                ctx.lineTo(x + candleWidth + depth, bodyTop - depth);
                ctx.lineTo(x + candleWidth, bodyTop);
                ctx.closePath();
                ctx.fill();

                // Shadow
                ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
                ctx.beginPath();
                ctx.rect(x + depth, chartY + chartHeight - depth, candleWidth, depth);
                ctx.fill();
            }}

            return {{
                x: x,
                y: Math.min(highY, bodyTop),
                width: candleWidth + depth,
                height: Math.abs(lowY - highY),
                index: index,
                candle: candle
            }};
        }}

        // Draw chart
        function drawChart() {{
            if (!canvas || !ctx) {{
                console.error('Canvas not initialized');
                return;
            }}

            if (canvas.width === 0 || canvas.height === 0) {{
                console.warn('Canvas has zero dimensions, retrying...');
                setTimeout(resizeCanvas, 100);
                return;
            }}

            updateDimensions();
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (dataLength === 0) {{
                ctx.fillStyle = '#333';
                ctx.font = '20px Arial';
                ctx.textAlign = 'center';
                ctx.fillText('No data available', canvas.width / 2, canvas.height / 2);
                return;
            }}

            // Calculate visible range based on zoom
            const visible = getVisibleRange();
            const visibleData = data.slice(visible.start, visible.end);
            
            // Recalculate price range for visible data only
            let visibleMinPrice = minPrice;
            let visibleMaxPrice = maxPrice;
            if (visibleData.length > 0) {{
                visibleMinPrice = Math.min(...visibleData.map(d => d.low));
                visibleMaxPrice = Math.max(...visibleData.map(d => d.high));
                // Add some padding
                const padding = (visibleMaxPrice - visibleMinPrice) * 0.05;
                visibleMinPrice -= padding;
                visibleMaxPrice += padding;
            }}
            const visiblePriceRange = visibleMaxPrice - visibleMinPrice;
            
            // Override priceToY for visible range
            const originalPriceToY = priceToY;
            window.currentPriceToY = function(price) {{
                return chartY + chartHeight - ((price - visibleMinPrice) / visiblePriceRange) * chartHeight;
            }};

            console.log('Drawing chart with', visible.count, 'visible candles (zoom:', zoomLevel.toFixed(2) + ')');
            console.log('Visible range:', visible.start, 'to', visible.end);
            console.log('Price range:', visibleMinPrice.toFixed(2), 'to', visibleMaxPrice.toFixed(2));

            // Draw axes with visible price range
            drawAxesWithRange(visibleMinPrice, visibleMaxPrice, visiblePriceRange);
            
            // Draw indicators first (behind candles) - for visible range
            drawBollingerBandsForRange(visible.start, visible.end, visibleMinPrice, visibleMaxPrice, visiblePriceRange);
            drawVWAPForRange(visible.start, visible.end, visibleMinPrice, visibleMaxPrice, visiblePriceRange);
            drawMA10ForRange(visible.start, visible.end, visibleMinPrice, visibleMaxPrice, visiblePriceRange);

            // Draw candles for visible range
            const candles = [];
            let drawnCount = 0;
            for (let i = visible.start; i < visible.end; i++) {{
                const x = indexToX(i);
                const depth = volumeToDepth(data[i].volume);
                const candleRect = drawCandleForRange(i, data[i], x, depth, visibleMinPrice, visibleMaxPrice, visiblePriceRange);
                if (candleRect) {{
                    candles.push(candleRect);
                    drawnCount++;
                }}
            }}
            
            // Draw prediction markers
            drawPredictionMarkers(visible.start, visible.end, visibleMinPrice, visibleMaxPrice, visiblePriceRange);
            
            console.log('Drawn', drawnCount, 'out of', visible.count, 'visible candles');

            // Store candles for hover detection
            window.chartCandles = candles;
            if (window.hoveredCandleIndex === undefined) {{
                window.hoveredCandleIndex = null;
            }}
        }}

        // Zoom state
        let zoomLevel = 1.0;
        let visibleStart = 0;
        let visibleEnd = dataLength;
        let isPanning = false;
        let panStartX = 0;
        let panStartIndex = 0;

        // Convert mouse X position to data index
        function mouseXToIndex(mouseX) {{
            const visible = getVisibleRange();
            if (visible.count <= 1) return 0;
            const relativeX = mouseX - chartX;
            const ratio = Math.max(0, Math.min(1, relativeX / chartWidth));
            const index = Math.floor(visible.start + ratio * visible.count);
            return Math.max(0, Math.min(dataLength - 1, index));
        }}

        // Calculate visible data range based on zoom
        function getVisibleRange() {{
            const totalData = dataLength;
            const visibleCount = Math.max(10, Math.floor(totalData / zoomLevel));
            const center = (visibleStart + visibleEnd) / 2;
            const halfRange = visibleCount / 2;
            
            let start = Math.max(0, Math.floor(center - halfRange));
            let end = Math.min(totalData, Math.floor(center + halfRange));
            
            // Adjust if we hit boundaries
            if (end >= totalData) {{
                end = totalData;
                start = Math.max(0, end - visibleCount);
            }}
            if (start <= 0) {{
                start = 0;
                end = Math.min(totalData, start + visibleCount);
            }}
            
            return {{ start: start, end: end, count: end - start }};
        }}

        // Zoom to a specific data index (centers the view on that index)
        function zoomToIndex(targetIndex, zoomFactor) {{
            const oldZoom = zoomLevel;
            zoomLevel = Math.max(0.5, Math.min(5.0, zoomLevel * zoomFactor));
            
            const totalData = dataLength;
            const visibleCount = Math.max(10, Math.floor(totalData / zoomLevel));
            const halfRange = visibleCount / 2;
            
            // Center on target index
            let start = Math.max(0, Math.floor(targetIndex - halfRange));
            let end = Math.min(totalData, Math.floor(targetIndex + halfRange));
            
            // Adjust if we hit boundaries
            if (end >= totalData) {{
                end = totalData;
                start = Math.max(0, end - visibleCount);
            }}
            if (start <= 0) {{
                start = 0;
                end = Math.min(totalData, start + visibleCount);
            }}
            
            visibleStart = start;
            visibleEnd = end;
        }}

        // Redraw chart with zoom and pan
        function redrawChart() {{
            drawChart();
            
            // Draw vertical line if hovering
            if (window.hoveredCandleIndex !== null && window.hoveredCandleIndex !== undefined) {{
                const candle = window.chartCandles[window.hoveredCandleIndex];
                if (candle) {{
                    const x = candle.x + candle.width / 2;
                    ctx.strokeStyle = '#FFD700';
                    ctx.lineWidth = 2;
                    ctx.setLineDash([5, 5]);
                    ctx.beginPath();
                    ctx.moveTo(x, chartY);
                    ctx.lineTo(x, chartY + chartHeight);
                    ctx.stroke();
                    ctx.setLineDash([]);
                }}
            }}
        }}


        canvas.addEventListener('mouseup', () => {{
            if (isPanning) {{
                isPanning = false;
                canvas.style.cursor = 'crosshair';
            }}
        }});

        canvas.addEventListener('mouseleave', () => {{
            tooltip.classList.remove('show');
            window.hoveredCandleIndex = null;
            isPanning = false;
            canvas.style.cursor = 'crosshair';
            redrawChart();
        }});

        // Panning functionality - click and drag to move around
        canvas.addEventListener('mousedown', (e) => {{
            if (e.button === 0) {{ // Left mouse button
                const rect = canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                
                // Only start panning if mouse is over the chart area
                if (mouseX >= chartX && mouseX <= chartX + chartWidth) {{
                    isPanning = true;
                    panStartX = mouseX;
                    panStartIndex = mouseXToIndex(mouseX);
                    canvas.style.cursor = 'grabbing';
                }}
            }}
        }});

        canvas.addEventListener('mousemove', (e) => {{
            if (isPanning) {{
                const rect = canvas.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const currentIndex = mouseXToIndex(mouseX);
                const indexDelta = panStartIndex - currentIndex;
                
                // Update visible range based on pan
                const visible = getVisibleRange();
                const newStart = Math.max(0, Math.min(dataLength - 1, visible.start + indexDelta));
                const newEnd = Math.max(0, Math.min(dataLength, visible.end + indexDelta));
                
                if (newStart >= 0 && newEnd <= dataLength && newEnd - newStart === visible.count) {{
                    visibleStart = newStart;
                    visibleEnd = newEnd;
                    redrawChart();
                }}
                
                return; // Don't process hover when panning
            }}
            
            // Tooltip handling
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            if (!window.chartCandles) return;

            let hoveredCandle = null;
            let hoveredIndex = null;
            for (let i = 0; i < window.chartCandles.length; i++) {{
                const candle = window.chartCandles[i];
                const candleCenterX = candle.x + candle.width / 2;
                const distanceX = Math.abs(x - candleCenterX);
                
                if (distanceX < candle.width / 2 + 10 && 
                    y >= candle.y && y <= candle.y + candle.height) {{
                    hoveredCandle = candle;
                    hoveredIndex = i;
                    break;
                }}
            }}

            window.hoveredCandleIndex = hoveredIndex;

            if (hoveredCandle) {{
                const c = hoveredCandle.candle;
                const date = new Date(c.date + 'T00:00:00');
                const dateStr = date.toLocaleDateString('en-US', {{ 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                }});

                tooltip.innerHTML = `
                    <div class="row"><span class="label">Date:</span><span class="value">${{dateStr}}</span></div>
                    <div class="row"><span class="label">Open:</span><span class="value">₹${{c.open.toFixed(2)}}</span></div>
                    <div class="row"><span class="label">High:</span><span class="value">₹${{c.high.toFixed(2)}}</span></div>
                    <div class="row"><span class="label">Low:</span><span class="value">₹${{c.low.toFixed(2)}}</span></div>
                    <div class="row"><span class="label">Close:</span><span class="value">₹${{c.close.toFixed(2)}}</span></div>
                    <div class="row"><span class="label">Volume:</span><span class="value">${{c.volume.toLocaleString()}}</span></div>
                `;
                tooltip.classList.add('show');
                
                // Smart tooltip positioning - prevent going off screen
                const tooltipWidth = 220;
                const tooltipHeight = 180;
                let tooltipX = e.clientX + 15;
                let tooltipY = e.clientY - 10;
                
                // Check right edge
                if (tooltipX + tooltipWidth > window.innerWidth) {{
                    tooltipX = e.clientX - tooltipWidth - 15;
                }}
                
                // Check left edge
                if (tooltipX < 0) {{
                    tooltipX = 15;
                }}
                
                // Check bottom edge
                if (tooltipY + tooltipHeight > window.innerHeight) {{
                    tooltipY = window.innerHeight - tooltipHeight - 10;
                }}
                
                // Check top edge
                if (tooltipY < 0) {{
                    tooltipY = 10;
                }}
                
                tooltip.style.left = tooltipX + 'px';
                tooltip.style.top = tooltipY + 'px';
                
                // Redraw to show vertical line
                redrawChart();
            }} else {{
                tooltip.classList.remove('show');
                window.hoveredCandleIndex = null;
                redrawChart();
            }}
        }});

        // Zoom functionality with mouse wheel - zooms into mouse position
        canvas.addEventListener('wheel', (e) => {{
            e.preventDefault();
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            
            // Only zoom if mouse is over the chart area
            if (mouseX >= chartX && mouseX <= chartX + chartWidth) {{
                const targetIndex = mouseXToIndex(mouseX);
                const delta = e.deltaY > 0 ? 0.9 : 1.1;
                zoomToIndex(targetIndex, delta);
                redrawChart();
            }}
        }});

        // Add zoom controls
        const zoomControls = document.createElement('div');
        zoomControls.style.cssText = 'position: absolute; top: 10px; right: 10px; z-index: 1000; display: flex; gap: 5px;';
        zoomControls.innerHTML = `
            <button id="zoomIn" style="padding: 8px 15px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">+</button>
            <button id="zoomOut" style="padding: 8px 15px; background: #f44336; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px;">-</button>
            <button id="zoomReset" style="padding: 8px 15px; background: #2196F3; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 14px;">Reset</button>
        `;
        document.querySelector('.chart-container').appendChild(zoomControls);

        document.getElementById('zoomIn').addEventListener('click', () => {{
            const visible = getVisibleRange();
            const centerIndex = Math.floor((visible.start + visible.end) / 2);
            zoomToIndex(centerIndex, 1.2);
            redrawChart();
        }});

        document.getElementById('zoomOut').addEventListener('click', () => {{
            const visible = getVisibleRange();
            const centerIndex = Math.floor((visible.start + visible.end) / 2);
            zoomToIndex(centerIndex, 1 / 1.2);
            redrawChart();
        }});

        document.getElementById('zoomReset').addEventListener('click', () => {{
            zoomLevel = 1.0;
            visibleStart = 0;
            visibleEnd = dataLength;
            redrawChart();
        }});

        // Initial draw - multiple attempts to ensure it works
        function initializeChart() {{
            if (canvas && canvas.parentElement) {{
                resizeCanvas();
            }} else {{
                console.log('Waiting for DOM...');
                setTimeout(initializeChart, 50);
            }}
        }}
        
        // Try multiple times to ensure canvas is ready
        setTimeout(initializeChart, 50);
        setTimeout(initializeChart, 200);
        setTimeout(initializeChart, 500);
    </script>
</body>
</html>
"""

# Write HTML file
with open("candlestick_chart.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print("[OK] Chart generated successfully!")
print(f"[OK] File: candlestick_chart.html")
print(f"[OK] Data points: {len(chart_data)}")
print(f"\nOpen 'candlestick_chart.html' in your browser to view the chart.")
