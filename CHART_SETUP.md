# Candlestick Chart Setup Instructions

## Quick Start - Standalone HTML (Easiest)

1. **Generate the HTML chart:**
   ```bash
   python generate_chart.py
   ```

2. **Open the file:**
   - Navigate to the project folder
   - Double-click `candlestick_chart.html`
   - Or open it in your browser

The chart should display automatically with all candles visible.

## React App Setup

1. **Generate data file:**
   ```bash
   python generate_data.py
   ```

2. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

4. **Open in browser:**
   - The terminal will show a URL (usually http://localhost:5173)
   - Open that URL in your browser

## Troubleshooting

### If candles are not displaying:

1. **Check browser console:**
   - Press F12 to open Developer Tools
   - Look for any JavaScript errors in the Console tab
   - Check if data is loaded (you should see log messages)

2. **Verify data file exists:**
   - For standalone HTML: The data is embedded in the HTML file
   - For React app: Check that `frontend/public/data.json` exists

3. **Regenerate files:**
   ```bash
   python generate_chart.py
   python generate_data.py
   ```

4. **Clear browser cache:**
   - Press Ctrl+Shift+Delete
   - Clear cached images and files
   - Reload the page

### Common Issues:

- **Canvas not rendering:** Make sure the container has proper dimensions (700px height)
- **No data:** Run `python generate_data.py` first
- **React app not loading:** Make sure you're in the `frontend` directory when running `npm install` and `npm run dev`

## Files Generated:

- `candlestick_chart.html` - Standalone HTML file (no server needed)
- `frontend/public/data.json` - Data file for React app

Both should work independently!

