// Chart rendering module for job performance analytics
// Pure JavaScript Canvas-based rendering - no external dependencies

// Chart configuration constants
const CHART_PADDING = { top: 30, right: 30, bottom: 60, left: 70 };
const DASH_PATTERN = [5, 5];

// Duration scaling thresholds (in seconds)
const THRESHOLD_HOURS = 3600; // >= 1 hour, use hours
const THRESHOLD_MINUTES = 300; // >= 5 minutes, use minutes

// Cache for CSS variables to avoid repeated DOM queries
let cssVariableCache = null;
let cssVariableSignature = '';

/**
 * Get CSS variables for chart colors with caching.
 * The cache is automatically refreshed if the underlying CSS variables change.
 * @returns {Object} - Object with color values
 */
function getCachedCSSVariables() {
    const rootStyles = getComputedStyle(document.documentElement);

    // Build a simple signature of the current raw CSS variable values
    const currentSignature = [
        rootStyles.getPropertyValue('--accent-info'),
        rootStyles.getPropertyValue('--accent-warning'),
        rootStyles.getPropertyValue('--accent-error'),
        rootStyles.getPropertyValue('--accent-primary')
    ].join('|');

    // If the signature matches, return the existing cache
    if (cssVariableCache && cssVariableSignature === currentSignature) {
        return cssVariableCache;
    }

    // Signature changed or cache is empty: rebuild the cache
    cssVariableSignature = currentSignature;
    cssVariableCache = {
        accentInfo: (rootStyles.getPropertyValue('--accent-info') || '').trim() || '#3b82f6',
        accentWarning: (rootStyles.getPropertyValue('--accent-warning') || '').trim() || '#f59e0b',
        accentError: (rootStyles.getPropertyValue('--accent-error') || '').trim() || '#ef4444',
        accentPrimary: (rootStyles.getPropertyValue('--accent-primary') || '').trim() || '#6366f1'
    };

    return cssVariableCache;
}

/**
 * Clear the cached CSS variables so that colors are re-read on next use.
 * This can be called by theme switchers when CSS custom properties change.
 */
export function clearChartCssVariableCache() {
    cssVariableCache = null;
    cssVariableSignature = '';
}

/**
 * Determine the best unit for displaying duration values
 * @param {Array} data - Array of data points with duration fields
 * @returns {Object} - Object with unit name, label, and divisor
 */
export function determineDurationUnit(data) {
    // Extract all valid duration values
    const allDurations = [];
    data.forEach(d => {
        if (d.avg_duration != null && d.avg_duration > 0) allDurations.push(d.avg_duration);
        if (d.p95_duration != null && d.p95_duration > 0) allDurations.push(d.p95_duration);
        if (d.p99_duration != null && d.p99_duration > 0) allDurations.push(d.p99_duration);
    });
    
    // If no valid durations, default to seconds
    if (allDurations.length === 0) {
        return { unit: 's', label: 'seconds', divisor: 1 };
    }
    
    // Find maximum duration to determine appropriate unit
    const maxDuration = Math.max(...allDurations);
    
    // Select unit based on thresholds
    if (maxDuration >= THRESHOLD_HOURS) {
        return { unit: 'hr', label: 'hours', divisor: 3600 };
    } else if (maxDuration >= THRESHOLD_MINUTES) {
        return { unit: 'min', label: 'minutes', divisor: 60 };
    } else {
        return { unit: 's', label: 'seconds', divisor: 1 };
    }
}

/**
 * Render a line chart showing job performance trends
 * @param {HTMLCanvasElement} canvas - Canvas element to render on
 * @param {Array} data - Array of analytics data points
 * @param {Object} options - Chart options
 */
export function renderJobPerformanceChart(canvas, data, options = {}) {
    if (!canvas || !data || data.length === 0) {
        console.warn('Cannot render chart: invalid canvas or empty data');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('Failed to get canvas 2D context');
        return;
    }
    
    // Set canvas size based on container
    const container = canvas.parentElement;
    if (!container) {
        console.error('Canvas has no parent container');
        return;
    }
    const width = container.clientWidth - 20; // Padding
    const height = container.clientHeight - 20;
    
    // Set device pixel ratio for sharp rendering on high-DPI displays
    const dpr = (typeof window !== 'undefined' && window.devicePixelRatio) ? window.devicePixelRatio : 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Chart dimensions (leave space for axes and labels)
    const chartWidth = width - CHART_PADDING.left - CHART_PADDING.right;
    const chartHeight = height - CHART_PADDING.top - CHART_PADDING.bottom;
    
    // Separate data by pipeline type and warn about unclassified data
    const defaultBranchData = data.filter(d => d.is_default_branch);
    const mrData = data.filter(d => d.is_merge_request);
    const unclassifiedData = data.filter(d => !d.is_default_branch && !d.is_merge_request);
    
    if (unclassifiedData.length > 0) {
        console.warn(
            'renderJobPerformanceChart: ignoring data points that are neither default branch nor merge request',
            unclassifiedData
        );
    }
    
    // If no data, show message
    if (defaultBranchData.length === 0 && mrData.length === 0) {
        ctx.fillStyle = '#a0a0b0';
        ctx.font = '16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No data available', width / 2, height / 2);
        return;
    }
    
    // Extract all valid duration values for scaling
    const allDurations = [];
    data.forEach(d => {
        if (d.avg_duration != null && d.avg_duration > 0) allDurations.push(d.avg_duration);
        if (d.p95_duration != null && d.p95_duration > 0) allDurations.push(d.p95_duration);
        if (d.p99_duration != null && d.p99_duration > 0) allDurations.push(d.p99_duration);
    });
    
    if (allDurations.length === 0) {
        ctx.fillStyle = '#a0a0b0';
        ctx.font = '16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No valid duration data', width / 2, height / 2);
        return;
    }
    
    // Determine the appropriate unit for display
    const durationScale = determineDurationUnit(data);
    
    const maxDuration = Math.max(...allDurations) / durationScale.divisor;
    const minDuration = Math.min(...allDurations) / durationScale.divisor;
    
    // Create unified time range for consistent x-axis scaling
    const now = Date.now();
    const TEN_YEARS_MS = 10 * 365 * 24 * 60 * 60 * 1000;
    const allTimestamps = data
        .map(d => new Date(d.created_at).getTime())
        .filter(t => !isNaN(t) && Math.abs(t - now) <= TEN_YEARS_MS);
    
    if (allTimestamps.length === 0) {
        ctx.fillStyle = '#a0a0b0';
        ctx.font = '16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No valid timestamp data', width / 2, height / 2);
        return;
    }
    
    const minTime = Math.min(...allTimestamps);
    const maxTime = Math.max(...allTimestamps);
    const timeRange = maxTime - minTime;
    
    // Scale functions - time-based x-axis for accurate positioning
    const xScale = (timestamp) => {
        if (timeRange === 0) return CHART_PADDING.left + chartWidth / 2;
        const timeSinceMin = new Date(timestamp).getTime() - minTime;
        return CHART_PADDING.left + (chartWidth * timeSinceMin / timeRange);
    };
    
    const yScale = (value) => {
        const range = maxDuration - minDuration;
        if (range === 0) return CHART_PADDING.top + chartHeight / 2;
        return CHART_PADDING.top + chartHeight - ((value - minDuration) / range * chartHeight);
    };
    
    // Draw grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    
    // Horizontal grid lines (5 lines)
    for (let i = 0; i <= 5; i++) {
        const y = CHART_PADDING.top + (chartHeight * i / 5);
        ctx.beginPath();
        ctx.moveTo(CHART_PADDING.left, y);
        ctx.lineTo(CHART_PADDING.left + chartWidth, y);
        ctx.stroke();
        
        // Y-axis labels (duration in selected unit)
        const value = maxDuration - (maxDuration - minDuration) * i / 5;
        ctx.fillStyle = '#a0a0b0';
        ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'right';
        // Format value with 1 decimal place if using minutes or hours
        const formattedValue = (durationScale.divisor === 1) 
            ? Math.round(value) 
            : value.toFixed(1);
        ctx.fillText(`${formattedValue}${durationScale.unit}`, CHART_PADDING.left - 10, y + 4);
    }
    
    // Draw axes
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(CHART_PADDING.left, CHART_PADDING.top);
    ctx.lineTo(CHART_PADDING.left, CHART_PADDING.top + chartHeight);
    ctx.lineTo(CHART_PADDING.left + chartWidth, CHART_PADDING.top + chartHeight);
    ctx.stroke();
    
    // Helper function to draw a line series with time-based x-axis
    const drawLine = (dataPoints, color, lineWidth = 2) => {
        if (dataPoints.length < 2) return;
        
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.beginPath();
        
        dataPoints.forEach((point, i) => {
            const x = xScale(point.timestamp);  // Use timestamp instead of index
            const y = yScale(point.value);
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.stroke();
        
        // Draw dots at each data point
        ctx.fillStyle = color;
        dataPoints.forEach((point, i) => {
            const x = xScale(point.timestamp);
            const y = yScale(point.value);
            
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
        });
    };
    
    /**
     * Helper to render duration series for a dataset
     * @param {Array} sourceData - Array of data points
     * @param {Object} colors - Object with avg, p95, and p99 keys
     * @param {boolean} isDashed - Whether to use dashed lines
     * @param {number} divisor - Scaling divisor for duration values
     */
    const renderDurationSeries = (sourceData, colors, isDashed = false, divisor = 1) => {
        if (sourceData.length === 0) return;
        
        // Prepare data series with timestamps and scaled values
        const avgData = sourceData
            .filter(d => d.avg_duration != null && d.avg_duration > 0)
            .map(d => ({ value: d.avg_duration / divisor, timestamp: d.created_at }));
        
        const p95Data = sourceData
            .filter(d => d.p95_duration != null && d.p95_duration > 0)
            .map(d => ({ value: d.p95_duration / divisor, timestamp: d.created_at }));
        
        const p99Data = sourceData
            .filter(d => d.p99_duration != null && d.p99_duration > 0)
            .map(d => ({ value: d.p99_duration / divisor, timestamp: d.created_at }));
        
        // Set dash pattern if needed
        if (isDashed) {
            ctx.setLineDash(DASH_PATTERN);
        }
        
        // Draw lines
        drawLine(avgData, colors.avg, 2);
        drawLine(p95Data, colors.p95, 2);
        drawLine(p99Data, colors.p99, 2);
        
        // Reset dash pattern
        if (isDashed) {
            ctx.setLineDash([]);
        }
    };
    
    // Get cached CSS variables
    const cssVars = getCachedCSSVariables();
    
    // Render default-branch lines (solid)
    renderDurationSeries(defaultBranchData, {
        avg: cssVars.accentInfo,
        p95: cssVars.accentWarning,
        p99: cssVars.accentError
    }, false, durationScale.divisor);
    
    // Render MR lines (dashed)
    renderDurationSeries(mrData, {
        avg: cssVars.accentPrimary,
        p95: cssVars.accentWarning,
        p99: cssVars.accentError
    }, true, durationScale.divisor);
    
    // X-axis labels (date/time) - use time-based positioning
    ctx.fillStyle = '#a0a0b0';
    ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    
    // Show labels for first, middle, and last data points from combined dataset
    const displayData = [...defaultBranchData, ...mrData].sort((a, b) => 
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );
    
    if (displayData.length > 0) {
        const labelIndices = [0, Math.floor(displayData.length / 2), displayData.length - 1];
        
        labelIndices.forEach(idx => {
            if (idx >= displayData.length) return;
            
            const d = displayData[idx];
            const x = xScale(d.created_at);
            const y = CHART_PADDING.top + chartHeight + 20;
            
            // Format date
            const date = new Date(d.created_at);
            const label = `${date.getMonth() + 1}/${date.getDate()}`;
            
            ctx.fillText(label, x, y);
        });
    }
    
    // Chart title with dynamic window days
    const windowDays = (typeof options.window_days === 'number' && options.window_days > 0) 
        ? options.window_days 
        : 7;
    const title = `Job Duration Trend (${windowDays} day${windowDays === 1 ? '' : 's'})`;
    ctx.fillStyle = '#e0e0e0';
    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(title, CHART_PADDING.left, CHART_PADDING.top - 10);
    
    // Y-axis label with dynamic unit
    ctx.save();
    ctx.translate(20, CHART_PADDING.top + chartHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = '#a0a0b0';
    ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`Duration (${durationScale.label})`, 0, 0);
    ctx.restore();
}
