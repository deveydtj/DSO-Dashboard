// Chart rendering module for job performance analytics
// Pure JavaScript Canvas-based rendering - no external dependencies

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
    const padding = { top: 30, right: 30, bottom: 60, left: 70 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    
    // Separate data by pipeline type
    const defaultBranchData = data.filter(d => d.is_default_branch);
    const mrData = data.filter(d => d.is_merge_request);
    
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
    
    const maxDuration = Math.max(...allDurations);
    const minDuration = Math.min(...allDurations);
    
    // Scale functions
    const xScale = (index, total) => padding.left + (chartWidth * index / Math.max(1, total - 1));
    const yScale = (value) => {
        const range = maxDuration - minDuration;
        if (range === 0) return padding.top + chartHeight / 2;
        return padding.top + chartHeight - ((value - minDuration) / range * chartHeight);
    };
    
    // Draw grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    
    // Horizontal grid lines (5 lines)
    for (let i = 0; i <= 5; i++) {
        const y = padding.top + (chartHeight * i / 5);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + chartWidth, y);
        ctx.stroke();
        
        // Y-axis labels (duration in seconds)
        const value = maxDuration - (maxDuration - minDuration) * i / 5;
        ctx.fillStyle = '#a0a0b0';
        ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(`${Math.round(value)}s`, padding.left - 10, y + 4);
    }
    
    // Draw axes
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, padding.top + chartHeight);
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
    ctx.stroke();
    
    // Helper function to draw a line series
    const drawLine = (dataPoints, color, lineWidth = 2) => {
        if (dataPoints.length < 2) return;
        
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.beginPath();
        
        dataPoints.forEach((point, i) => {
            const x = xScale(i, dataPoints.length);
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
            const x = xScale(i, dataPoints.length);
            const y = yScale(point.value);
            
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fill();
        });
    };
    
    // Render default-branch lines
    if (defaultBranchData.length > 0) {
        const avgData = defaultBranchData
            .filter(d => d.avg_duration != null && d.avg_duration > 0)
            .map(d => ({ value: d.avg_duration }));
        
        const p95Data = defaultBranchData
            .filter(d => d.p95_duration != null && d.p95_duration > 0)
            .map(d => ({ value: d.p95_duration }));
        
        const p99Data = defaultBranchData
            .filter(d => d.p99_duration != null && d.p99_duration > 0)
            .map(d => ({ value: d.p99_duration }));
        
        // Use CSS variables for consistency with theme
        const accentInfo = getComputedStyle(document.documentElement).getPropertyValue('--accent-info').trim() || '#3b82f6';
        const accentWarning = getComputedStyle(document.documentElement).getPropertyValue('--accent-warning').trim() || '#f59e0b';
        const accentError = getComputedStyle(document.documentElement).getPropertyValue('--accent-error').trim() || '#ef4444';
        
        drawLine(avgData, accentInfo, 2);     // Blue for avg
        drawLine(p95Data, accentWarning, 2);  // Orange for p95
        drawLine(p99Data, accentError, 2);    // Red for p99
    }
    
    // Render MR lines (dashed style)
    if (mrData.length > 0) {
        const avgData = mrData
            .filter(d => d.avg_duration != null && d.avg_duration > 0)
            .map(d => ({ value: d.avg_duration }));
        
        const p95Data = mrData
            .filter(d => d.p95_duration != null && d.p95_duration > 0)
            .map(d => ({ value: d.p95_duration }));
        
        const p99Data = mrData
            .filter(d => d.p99_duration != null && d.p99_duration > 0)
            .map(d => ({ value: d.p99_duration }));
        
        // Use CSS variables for consistency with theme
        const accentPrimary = getComputedStyle(document.documentElement).getPropertyValue('--accent-primary').trim() || '#6366f1';
        const accentWarning = getComputedStyle(document.documentElement).getPropertyValue('--accent-warning').trim() || '#f59e0b';
        const accentError = getComputedStyle(document.documentElement).getPropertyValue('--accent-error').trim() || '#ef4444';
        
        // Draw dashed lines for MR data
        ctx.setLineDash([5, 5]);
        drawLine(avgData, accentPrimary, 2);  // Purple for MR avg
        drawLine(p95Data, accentWarning, 2);  // Orange for MR p95
        drawLine(p99Data, accentError, 2);    // Red for MR p99
        ctx.setLineDash([]);
    }
    
    // X-axis labels (date/time)
    ctx.fillStyle = '#a0a0b0';
    ctx.font = '11px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    
    // Show labels for first, middle, and last data points
    const displayData = defaultBranchData.length > 0 ? defaultBranchData : mrData;
    if (displayData.length > 0) {
        const showLabels = [0, Math.floor(displayData.length / 2), displayData.length - 1];
        
        showLabels.forEach(idx => {
            if (idx >= displayData.length) return;
            
            const d = displayData[idx];
            const x = xScale(idx, displayData.length);
            const y = padding.top + chartHeight + 20;
            
            // Format date
            const date = new Date(d.created_at);
            const label = `${date.getMonth() + 1}/${date.getDate()}`;
            
            ctx.fillText(label, x, y);
        });
    }
    
    // Chart title
    ctx.fillStyle = '#e0e0e0';
    ctx.font = 'bold 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Job Duration Trend (7 days)', padding.left, padding.top - 10);
    
    // Y-axis label
    ctx.save();
    ctx.translate(20, padding.top + chartHeight / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = '#a0a0b0';
    ctx.font = '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Duration (seconds)', 0, 0);
    ctx.restore();
}
