import React, { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [hoveredCandle, setHoveredCandle] = useState(null)
    const [hoveredCandleIndex, setHoveredCandleIndex] = useState(null)
    const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 })
    const canvasRef = useRef(null)
    const containerRef = useRef(null)

    useEffect(() => {
        // Load data from JSON file
        console.log('Fetching data from /data.json...')
        fetch('/data.json')
            .then(res => {
                console.log('Response status:', res.status, res.statusText)
                if (!res.ok) {
                    throw new Error(`HTTP error! status: ${res.status}`)
                }
                return res.json()
            })
            .then(data => {
                console.log('Data loaded successfully:', {
                    hasChartData: !!data.chartData,
                    chartDataLength: data.chartData ? data.chartData.length : 0,
                    minPrice: data.minPrice,
                    maxPrice: data.maxPrice
                })
                
                if (!data.chartData || data.chartData.length === 0) {
                    throw new Error('No chart data found in JSON file')
                }
                
                setData(data)
                setLoading(false)
            })
            .catch(err => {
                console.error('Error loading data:', err)
                console.error('Make sure:')
                console.error('1. You have run: python generate_data.py')
                console.error('2. The file frontend/public/data.json exists')
                console.error('3. You are running the dev server (npm run dev)')
                setLoading(false)
            })
    }, [])

    useEffect(() => {
        if (data && canvasRef.current && containerRef.current) {
            // Small delay to ensure DOM is ready
            setTimeout(() => {
                drawChart()
            }, 100)
        }
    }, [data])

    const drawChart = () => {
        const canvas = canvasRef.current
        if (!canvas || !data || !containerRef.current) {
            console.log('Cannot draw chart:', { canvas: !!canvas, data: !!data, container: !!containerRef.current })
            return
        }

        const ctx = canvas.getContext('2d')
        const container = containerRef.current
        
        // Set canvas size - use actual container dimensions
        const containerWidth = container.clientWidth || container.offsetWidth || 800
        const containerHeight = container.clientHeight || container.offsetHeight || 700
        
        canvas.width = containerWidth
        canvas.height = containerHeight
        
        console.log('Drawing chart with dimensions:', canvas.width, 'x', canvas.height)

        // Y-axis on the right
        const padding = { top: 60, right: 120, bottom: 100, left: 80 }
        const chartWidth = canvas.width - padding.left - padding.right
        const chartHeight = canvas.height - padding.top - padding.bottom
        const chartX = padding.left
        const chartY = padding.top

        const { chartData, minPrice, maxPrice, priceRange, maxVolume } = data
        const dataLength = chartData.length

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        // Helper functions
        const priceToY = (price) => {
            return chartY + chartHeight - ((price - minPrice) / priceRange) * chartHeight
        }

        const indexToX = (index) => {
            if (dataLength <= 1) return chartX
            return chartX + (index / (dataLength - 1)) * chartWidth
        }

        const volumeToDepth = (volume) => {
            if (maxVolume === 0) return 0
            return Math.max(3, (volume / maxVolume) * 25)
        }

        // Draw grid and axes
        ctx.strokeStyle = '#e0e0e0'
        ctx.lineWidth = 1

        // Horizontal grid lines
        for (let i = 0; i <= 10; i++) {
            const price = minPrice + (priceRange * i / 10)
            const y = priceToY(price)
            ctx.beginPath()
            ctx.moveTo(chartX, y)
            ctx.lineTo(chartX + chartWidth, y)
            ctx.stroke()
        }

        // Vertical grid lines
        const dateStep = Math.max(1, Math.floor(dataLength / 12))
        for (let i = 0; i < dataLength; i += dateStep) {
            const x = indexToX(i)
            ctx.beginPath()
            ctx.moveTo(x, chartY)
            ctx.lineTo(x, chartY + chartHeight)
            ctx.stroke()
        }

        // Draw Y-axis - on the right side
        const yAxisX = chartX + chartWidth
        ctx.strokeStyle = '#333'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(yAxisX, chartY)
        ctx.lineTo(yAxisX, chartY + chartHeight)
        ctx.stroke()

        // Draw X-axis
        ctx.beginPath()
        ctx.moveTo(chartX, chartY + chartHeight)
        ctx.lineTo(chartX + chartWidth, chartY + chartHeight)
        ctx.stroke()

        // Y-axis labels - on the right side
        ctx.fillStyle = '#666'
        ctx.font = '12px Inter'
        ctx.textAlign = 'left'
        ctx.textBaseline = 'middle'

        for (let i = 0; i <= 10; i++) {
            const price = minPrice + (priceRange * i / 10)
            const y = priceToY(price)
            ctx.fillText('₹' + price.toFixed(2), yAxisX + 15, y)
        }

        // X-axis labels
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'

        for (let i = 0; i < dataLength; i += dateStep) {
            const x = indexToX(i)
            const date = new Date(chartData[i].date + 'T00:00:00')
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            ctx.fillText(dateStr, x, chartY + chartHeight + 15)
        }

        // Draw indicators first (behind candles)
        const { indicators } = data
        
        // Draw Bollinger Bands
        if (indicators && indicators.bollingerBands) {
            const bb = indicators.bollingerBands
            
            // Draw upper band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.6)'
            ctx.lineWidth = 1.5
            ctx.setLineDash([5, 5])
            ctx.beginPath()
            let firstPoint = true
            for (let i = 0; i < bb.length; i++) {
                if (bb[i] && bb[i].upper !== null) {
                    const x = indexToX(i)
                    const y = priceToY(bb[i].upper)
                    if (firstPoint) {
                        ctx.moveTo(x, y)
                        firstPoint = false
                    } else {
                        ctx.lineTo(x, y)
                    }
                }
            }
            ctx.stroke()
            
            // Draw middle band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.8)'
            ctx.lineWidth = 1.5
            ctx.beginPath()
            firstPoint = true
            for (let i = 0; i < bb.length; i++) {
                if (bb[i] && bb[i].middle !== null) {
                    const x = indexToX(i)
                    const y = priceToY(bb[i].middle)
                    if (firstPoint) {
                        ctx.moveTo(x, y)
                        firstPoint = false
                    } else {
                        ctx.lineTo(x, y)
                    }
                }
            }
            ctx.stroke()
            
            // Draw lower band
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.6)'
            ctx.lineWidth = 1.5
            ctx.beginPath()
            firstPoint = true
            for (let i = 0; i < bb.length; i++) {
                if (bb[i] && bb[i].lower !== null) {
                    const x = indexToX(i)
                    const y = priceToY(bb[i].lower)
                    if (firstPoint) {
                        ctx.moveTo(x, y)
                        firstPoint = false
                    } else {
                        ctx.lineTo(x, y)
                    }
                }
            }
            ctx.stroke()
            ctx.setLineDash([])
            
            // Fill between bands
            ctx.fillStyle = 'rgba(255, 152, 0, 0.1)'
            ctx.beginPath()
            firstPoint = true
            for (let i = 0; i < bb.length; i++) {
                if (bb[i] && bb[i].upper !== null && bb[i].lower !== null) {
                    const x = indexToX(i)
                    const upperY = priceToY(bb[i].upper)
                    if (firstPoint) {
                        ctx.moveTo(x, upperY)
                        firstPoint = false
                    } else {
                        ctx.lineTo(x, upperY)
                    }
                }
            }
            for (let i = bb.length - 1; i >= 0; i--) {
                if (bb[i] && bb[i].upper !== null && bb[i].lower !== null) {
                    const x = indexToX(i)
                    const lowerY = priceToY(bb[i].lower)
                    ctx.lineTo(x, lowerY)
                }
            }
            ctx.closePath()
            ctx.fill()
        }
        
        // Draw VWAP
        if (indicators && indicators.vwap) {
            ctx.strokeStyle = '#FFC107'
            ctx.lineWidth = 2
            ctx.setLineDash([3, 3])
            ctx.beginPath()
            
            let firstPoint = true
            for (let i = 0; i < indicators.vwap.length; i++) {
                const vwap = indicators.vwap[i]
                if (vwap && vwap.vwap !== null && vwap.vwap !== undefined) {
                    const x = indexToX(i)
                    const y = priceToY(vwap.vwap)
                    
                    if (firstPoint) {
                        ctx.moveTo(x, y)
                        firstPoint = false
                    } else {
                        ctx.lineTo(x, y)
                    }
                }
            }
            ctx.stroke()
            ctx.setLineDash([])
        }
        
        // Draw MA10
        if (indicators && indicators.ma10) {
            ctx.strokeStyle = '#f44336'
            ctx.lineWidth = 2
            ctx.beginPath()
            
            let firstPoint = true
            for (let i = 0; i < indicators.ma10.length; i++) {
                const ma = indicators.ma10[i]
                if (ma && ma.ma !== null && ma.ma !== undefined) {
                    const x = indexToX(i)
                    const y = priceToY(ma.ma)
                    
                    if (firstPoint) {
                        ctx.moveTo(x, y)
                        firstPoint = false
                    } else {
                        ctx.lineTo(x, y)
                    }
                }
            }
            ctx.stroke()
        }

        // Draw candles
        window.candles = []
        for (let i = 0; i < dataLength; i++) {
            const candle = chartData[i]
            const x = indexToX(i)
            const depth = volumeToDepth(candle.volume)

            const openY = priceToY(candle.open)
            const closeY = priceToY(candle.close)
            const highY = priceToY(candle.high)
            const lowY = priceToY(candle.low)

            const isBullish = candle.close > candle.open
            const bodyTop = Math.min(openY, closeY)
            const bodyBottom = Math.max(openY, closeY)
            const bodyHeight = Math.max(1, bodyBottom - bodyTop)
            const candleWidth = Math.max(3, (chartWidth / dataLength) * 0.85)
            
            // Ensure candle is visible
            if (isNaN(x) || isNaN(openY) || isNaN(closeY) || isNaN(highY) || isNaN(lowY)) {
                console.warn('Invalid candle data at index', i, candle)
                continue
            }

            // Draw wick
            ctx.strokeStyle = isBullish ? '#10b981' : '#ef4444'
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.moveTo(x + candleWidth / 2, highY)
            ctx.lineTo(x + candleWidth / 2, lowY)
            ctx.stroke()

            // Draw body
            if (isBullish) {
                ctx.fillStyle = '#10b981'  // Green
                ctx.strokeStyle = '#059669'  // Darker green border
            } else {
                ctx.fillStyle = '#ef4444'  // Red
                ctx.strokeStyle = '#dc2626'  // Darker red border
            }
            ctx.lineWidth = 2
            ctx.beginPath()
            ctx.rect(x, bodyTop, candleWidth, bodyHeight)
            ctx.fill()
            ctx.stroke()

            // 3D effect
            if (depth > 0) {
                const alpha = 0.5
                ctx.fillStyle = isBullish 
                    ? `rgba(16, 185, 129, ${alpha})`  // Green
                    : `rgba(239, 68, 68, ${alpha})`  // Red

                // Right face
                ctx.beginPath()
                ctx.moveTo(x + candleWidth, bodyTop)
                ctx.lineTo(x + candleWidth + depth, bodyTop - depth)
                ctx.lineTo(x + candleWidth + depth, bodyBottom - depth)
                ctx.lineTo(x + candleWidth, bodyBottom)
                ctx.closePath()
                ctx.fill()

                // Top face
                ctx.beginPath()
                ctx.moveTo(x, bodyTop)
                ctx.lineTo(x + depth, bodyTop - depth)
                ctx.lineTo(x + candleWidth + depth, bodyTop - depth)
                ctx.lineTo(x + candleWidth, bodyTop)
                ctx.closePath()
                ctx.fill()

                // Shadow
                ctx.fillStyle = 'rgba(0, 0, 0, 0.1)'
                ctx.beginPath()
                ctx.rect(x + depth, chartY + chartHeight - depth, candleWidth, depth)
                ctx.fill()
            }

            window.candles.push({
                x: x,
                y: Math.min(highY, bodyTop),
                width: candleWidth + depth,
                height: Math.abs(lowY - highY),
                index: i,
                candle: candle
            })
        }
        
        // Draw vertical line if hovering (after candles are drawn)
        if (hoveredCandleIndex !== null && window.candles && window.candles[hoveredCandleIndex]) {
            const candle = window.candles[hoveredCandleIndex]
            const x = candle.x + candle.width / 2
            ctx.strokeStyle = '#FFD700'
            ctx.lineWidth = 2
            ctx.setLineDash([5, 5])
            ctx.beginPath()
            ctx.moveTo(x, chartY)
            ctx.lineTo(x, chartY + chartHeight)
            ctx.stroke()
            ctx.setLineDash([])
        }
        
        console.log('Chart drawn successfully with', window.candles.length, 'candles')
    }

    const handleMouseMove = (e) => {
        if (!window.candles) return

        const canvas = canvasRef.current
        const rect = canvas.getBoundingClientRect()
        const x = e.clientX - rect.left
        const y = e.clientY - rect.top

        let hovered = null
        let hoveredIdx = null
        for (let i = 0; i < window.candles.length; i++) {
            const candle = window.candles[i]
            const candleCenterX = candle.x + candle.width / 2
            const distanceX = Math.abs(x - candleCenterX)
            
            if (distanceX < candle.width / 2 + 15 && 
                y >= candle.y && y <= candle.y + candle.height) {
                hovered = candle
                hoveredIdx = i
                break
            }
        }

        setHoveredCandleIndex(hoveredIdx)

        if (hovered) {
            setHoveredCandle(hovered)
            
            // Smart tooltip positioning - prevent going off screen
            const tooltipWidth = 220
            const tooltipHeight = 180
            let tooltipX = e.clientX + 15
            let tooltipY = e.clientY - 10
            
            // Check right edge
            if (tooltipX + tooltipWidth > window.innerWidth) {
                tooltipX = e.clientX - tooltipWidth - 15
            }
            
            // Check left edge
            if (tooltipX < 0) {
                tooltipX = 15
            }
            
            // Check bottom edge
            if (tooltipY + tooltipHeight > window.innerHeight) {
                tooltipY = window.innerHeight - tooltipHeight - 10
            }
            
            // Check top edge
            if (tooltipY < 0) {
                tooltipY = 10
            }
            
            setTooltipPosition({ x: tooltipX, y: tooltipY })
        } else {
            setHoveredCandle(null)
        }
    }

    const handleResize = () => {
        if (data && canvasRef.current && containerRef.current) {
            setTimeout(() => {
                drawChart()
            }, 100)
        }
    }

    useEffect(() => {
        window.addEventListener('resize', handleResize)
        return () => window.removeEventListener('resize', handleResize)
    }, [data])
    
    // Also redraw when window loads
    useEffect(() => {
        const handleLoad = () => {
            if (data && canvasRef.current) {
                setTimeout(() => {
                    drawChart()
                }, 200)
            }
        }
        window.addEventListener('load', handleLoad)
        return () => window.removeEventListener('load', handleLoad)
    }, [data])

    if (loading) {
        return (
            <div className="app">
                <div className="loading">
                    <div className="spinner"></div>
                    <p>Loading chart data...</p>
                </div>
            </div>
        )
    }

    if (!data) {
        return (
            <div className="app">
                <div className="error">
                    <p>Error loading data. Please run: python generate_data.py</p>
                </div>
            </div>
        )
    }

    const { chartData, minPrice, maxPrice, maxVolume } = data

    return (
        <div className="app">
            <div className="container">
                <header className="header">
                    <h1>📈 3D Candlestick Chart</h1>
                    <p className="subtitle">Interactive Stock Analysis - Hover over candles to see details</p>
                </header>

                <div className="chart-wrapper" ref={containerRef}>
                    <div className="zoom-controls">
                        <button onClick={() => {/* Zoom in - to be implemented */}} className="zoom-btn zoom-in">+</button>
                        <button onClick={() => {/* Zoom out - to be implemented */}} className="zoom-btn zoom-out">-</button>
                        <button onClick={() => {/* Reset - to be implemented */}} className="zoom-btn zoom-reset">Reset</button>
                    </div>
                    <canvas
                        ref={canvasRef}
                        onMouseMove={handleMouseMove}
                        onMouseLeave={() => {
                            setHoveredCandle(null)
                            setHoveredCandleIndex(null)
                        }}
                    />
                    
                    {hoveredCandle && (
                        <div 
                            className="tooltip"
                            style={{
                                left: `${tooltipPosition.x}px`,
                                top: `${tooltipPosition.y}px`
                            }}
                        >
                            <div className="tooltip-row">
                                <span className="tooltip-label">Date:</span>
                                <span className="tooltip-value">
                                    {new Date(hoveredCandle.candle.date + 'T00:00:00').toLocaleDateString('en-US', {
                                        year: 'numeric',
                                        month: 'long',
                                        day: 'numeric'
                                    })}
                                </span>
                            </div>
                            <div className="tooltip-row">
                                <span className="tooltip-label">Open:</span>
                                <span className="tooltip-value">₹{hoveredCandle.candle.open.toFixed(2)}</span>
                            </div>
                            <div className="tooltip-row">
                                <span className="tooltip-label">High:</span>
                                <span className="tooltip-value">₹{hoveredCandle.candle.high.toFixed(2)}</span>
                            </div>
                            <div className="tooltip-row">
                                <span className="tooltip-label">Low:</span>
                                <span className="tooltip-value">₹{hoveredCandle.candle.low.toFixed(2)}</span>
                            </div>
                            <div className="tooltip-row">
                                <span className="tooltip-label">Close:</span>
                                <span className="tooltip-value">₹{hoveredCandle.candle.close.toFixed(2)}</span>
                            </div>
                            <div className="tooltip-row">
                                <span className="tooltip-label">Volume:</span>
                                <span className="tooltip-value">{hoveredCandle.candle.volume.toLocaleString()}</span>
                            </div>
                        </div>
                    )}
                </div>

                <div className="legend">
                    <div className="legend-item">
                        <div className="legend-color bullish"></div>
                        <span>Bullish (Open &lt; Close)</span>
                    </div>
                    <div className="legend-item">
                        <div className="legend-color bearish"></div>
                        <span>Bearish (Open &gt; Close)</span>
                    </div>
                </div>

                <div className="indicator-legend">
                    <div className="indicator-item">
                        <div className="indicator-line ma10"></div>
                        <span>MA 10</span>
                    </div>
                    <div className="indicator-item">
                        <div className="indicator-line vwap"></div>
                        <span>VWAP</span>
                    </div>
                    <div className="indicator-item">
                        <div className="indicator-line bb"></div>
                        <span>Bollinger Bands</span>
                    </div>
                </div>

                <div className="info-panel">
                    <div className="info-item">
                        <span className="info-label">Total Data Points:</span>
                        <span className="info-value">{chartData.length} days</span>
                    </div>
                    <div className="info-item">
                        <span className="info-label">Price Range:</span>
                        <span className="info-value">₹{minPrice.toFixed(2)} - ₹{maxPrice.toFixed(2)}</span>
                    </div>
                    <div className="info-item">
                        <span className="info-label">Max Volume:</span>
                        <span className="info-value">{maxVolume.toLocaleString()}</span>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default App


