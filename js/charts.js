/**
 * Chart management module.
 * Creates and updates Chart.js time-series line charts.
 */

const Charts = (() => {
    const instances = {};

    const defaultOptions = (label, color, isCurrency, currencySymbol) => ({
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(15, 25, 35, 0.95)',
                titleColor: '#e8edf2',
                bodyColor: '#e8edf2',
                borderColor: '#2a4a6b',
                borderWidth: 1,
                padding: 12,
                displayColors: false,
                titleFont: { size: 12, weight: '500' },
                bodyFont: { size: 14, weight: '700' },
                callbacks: {
                    title(items) {
                        const d = new Date(items[0].parsed.x);
                        return d.toLocaleDateString('en-GB', {
                            weekday: 'short', day: 'numeric',
                            month: 'short', year: 'numeric'
                        });
                    },
                    label(item) {
                        if (isCurrency) {
                            return `${label}: ${item.parsed.y.toFixed(4)}`;
                        }
                        return `${label}: ${currencySymbol}${item.parsed.y.toLocaleString()}`;
                    }
                }
            }
        },
        scales: {
            x: {
                type: 'time',
                time: {
                    tooltipFormat: 'PP',
                    displayFormats: {
                        hour: 'HH:mm',
                        day: 'dd MMM',
                        week: 'dd MMM',
                        month: 'MMM yyyy',
                        year: 'yyyy',
                    }
                },
                grid: {
                    color: 'rgba(42, 74, 107, 0.3)',
                    drawBorder: false,
                },
                ticks: {
                    color: '#8899aa',
                    font: { size: 11 },
                    maxTicksLimit: 10,
                }
            },
            y: {
                grid: {
                    color: 'rgba(42, 74, 107, 0.3)',
                    drawBorder: false,
                },
                ticks: {
                    color: '#8899aa',
                    font: { size: 11 },
                    callback(value) {
                        if (isCurrency) return value.toFixed(4);
                        return '$' + value.toLocaleString();
                    }
                }
            }
        },
        elements: {
            point: { radius: 0, hoverRadius: 5, hoverBorderWidth: 2 },
            line: { tension: 0.3, borderWidth: 2.5 },
        },
    });

    function showLoading(canvasId) {
        const container = document.getElementById(canvasId).parentElement;
        let overlay = container.querySelector('.chart-loading');
        if (!overlay) {
            overlay = document.createElement('div');
            overlay.className = 'chart-loading';
            overlay.innerHTML = '<div class="spinner"></div>';
            container.style.position = 'relative';
            container.appendChild(overlay);
        }
        overlay.style.display = 'flex';
    }

    function hideLoading(canvasId) {
        const container = document.getElementById(canvasId).parentElement;
        const overlay = container.querySelector('.chart-loading');
        if (overlay) overlay.style.display = 'none';
    }

    function createOrUpdate(canvasId, dataPoints, label, color, isCurrency, currencySymbol = '$') {
        const ctx = document.getElementById(canvasId).getContext('2d');

        const chartData = {
            datasets: [{
                label,
                data: dataPoints.map(p => ({ x: new Date(p.date), y: p.value })),
                borderColor: color,
                backgroundColor: hexToRgba(color, 0.08),
                fill: true,
            }]
        };

        if (instances[canvasId]) {
            instances[canvasId].data = chartData;
            instances[canvasId].update('none');
        } else {
            instances[canvasId] = new Chart(ctx, {
                type: 'line',
                data: chartData,
                options: defaultOptions(label, color, isCurrency, currencySymbol),
            });
        }

        hideLoading(canvasId);
    }

    function hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    return { createOrUpdate, showLoading, hideLoading };
})();
