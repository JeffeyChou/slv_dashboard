document.addEventListener('DOMContentLoaded', () => {
    fetchData();
    // P0 Trends
    const p0Select = document.getElementById('p0-metric-select');
    if (p0Select) {
        p0Select.addEventListener('change', () => fetchP0HistoryAndRender());
        // Initial load
        fetchP0HistoryAndRender();
    }
    // Refresh every 5 minutes
    setInterval(fetchData, 300000);
});

async function fetchData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        updateDashboard(data);

        // After getting current data, fetch history for charts
        fetchHistoryAndRender();
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

async function fetchHistoryAndRender() {
    try {
        // Fetch Intraday Data (Price & OI) - using 30 days for now as requested, but we can zoom in
        const priceHistory = await fetch('/api/history?metric=COMEX_Futures_Price&days=30').then(r => r.json());
        const oiHistory = await fetch('/api/history?metric=COMEX_Silver_Registered&days=30').then(r => r.json()); // Using Registered for inventory chart
        const slvHistory = await fetch('/api/history?metric=SLV_Inventory_Ounces&days=30').then(r => r.json()); // Need to make sure this metric name matches what we store

        // For Intraday Price/OI, we might want 'COMEX_Futures_Price' and 'OI_ag2603' (or COMEX OI)
        // Let's check what metrics we are storing in p0_storage.py
        // 'COMEX_Futures_Price', 'COMEX_Silver_Registered', 'SLV_Coverage' etc.

        const comexOiHistory = await fetch('/api/history?metric=OI_ag2603&days=30').then(r => r.json()); // Using SHFE OI for now or we need COMEX OI if available
        // Wait, p0_storage columns: 'OI_ag2603', 'COMEX_Futures_Price', 'COMEX_Silver_Registered', 'LBMA_London_Vault_Silver'

        renderIntradayChart(priceHistory, comexOiHistory); // View 1
        renderHistoricalChart(slvHistory, oiHistory); // View 2 (Inventory)
        renderSlvHistoryChart(slvHistory); // New SLV Chart

    } catch (error) {
        console.error('Error fetching history:', error);
    }
}

async function fetchP0HistoryAndRender() {
    const metric = document.getElementById('p0-metric-select').value;
    try {
        const history = await fetch(`/api/history?metric=${metric}&days=30`).then(r => r.json());
        renderP0HistoryChart(history, metric);
    } catch (error) {
        console.error('Error fetching P0 history:', error);
    }
}

function updateDashboard(data) {
    // Futures
    if (data.futures && !data.futures.error) {
        document.getElementById('futures-price').textContent = `$${data.futures.price}`;
        document.getElementById('futures-volume').textContent = formatNumber(data.futures.volume);
        document.getElementById('futures-oi').textContent = formatNumber(data.futures.open_interest);
    } else {
        document.getElementById('futures-price').textContent = 'Error';
    }

    // SLV
    if (data.slv && !data.slv.error) {
        document.getElementById('slv-tonnes').textContent = data.slv.inventory_tonnes;
        document.getElementById('slv-ounces').textContent = data.slv.inventory_ounces;
        renderSlvChart(data.slv);
    }

    // CME/LBMA
    if (data.cme && !data.cme.error) {
        document.getElementById('cme-registered').textContent = formatNumber(data.cme.registered) + ' oz';
        document.getElementById('cme-eligible').textContent = formatNumber(data.cme.eligible) + ' oz';
    }
    if (data.lbma && !data.lbma.error) {
        document.getElementById('lbma-holdings').textContent = formatNumber(data.lbma.holdings_tonnes) + ' T';
    }

    // Macro (P2)
    if (data.macro) {
        document.getElementById('macro-dxy').textContent = data.macro.usd_index || 'N/A';
        document.getElementById('macro-yield').textContent = data.macro.real_yield ? data.macro.real_yield + '%' : 'N/A';
        document.getElementById('macro-gsr').textContent = data.macro.gold_silver_ratio || 'N/A';
        document.getElementById('macro-cny').textContent = data.macro.usd_cny || 'N/A';
    }

    // Sentiment (P1)
    if (data.options && !data.options.error) {
        document.getElementById('sent-pc-ratio').textContent = data.options.put_call_ratio;
        document.getElementById('sent-call-vol').textContent = formatNumber(data.options.call_volume);
    }
    if (data.cot) {
        document.getElementById('sent-cot').textContent = data.cot.status || 'N/A';
    }

    // SHFE (P0)
    if (data.shfe) {
        document.getElementById('shfe-price').textContent = data.shfe.price_cny || data.shfe.price || 'N/A';
        document.getElementById('shfe-premium').textContent = data.shfe.premium_usd || 'N/A';
    }

    // P0 Indicators
    if (data.p0_indicators) {
        const p0 = data.p0_indicators;
        document.getElementById('p0-paper-physical').textContent = formatValue(p0.Paper_to_Physical);
        document.getElementById('p0-slv-coverage').textContent = formatValue(p0.SLV_Coverage);
        document.getElementById('p0-dominance').textContent = formatValue(p0.COMEX_Dominance);
        document.getElementById('p0-shanghai-prem').textContent = formatValue(p0.Shanghai_Premium_Implied, '$');
        document.getElementById('p0-shfe-turnover').textContent = formatValue(p0.Turnover_ag2603);
        document.getElementById('p0-shfe-conc').textContent = formatValue(p0.OI_concentration_2603);
        document.getElementById('p0-curve-slope').textContent = formatValue(p0.Curve_slope_SHFE_3m6m);

        renderP0Chart(p0);
    }
}

function formatValue(val, prefix = '') {
    if (val === null || val === undefined || val === 'N/A') return 'N/A';
    return prefix + val;
}

function formatNumber(numStr) {
    if (!numStr) return 'N/A';
    const num = parseFloat(numStr.toString().replace(/,/g, ''));
    if (isNaN(num)) return numStr;
    return num.toLocaleString();
}

// --- ECharts Implementations ---

function renderIntradayChart(priceData, oiData) {
    const chartDom = document.getElementById('futuresChart');
    const myChart = echarts.init(chartDom);

    // Process data
    const dates = priceData.map(item => item.timestamp);
    const prices = priceData.map(item => item.value);
    // Align OI data (assuming same timestamps or close enough, for simplicity we just map)
    // In a real app we'd align by timestamp. 
    const ois = oiData.map(item => item.value);

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' }
        },
        grid: {
            left: '3%',
            right: '3%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            axisLabel: { formatter: (value) => value.substring(11, 16) } // Show HH:MM
        },
        yAxis: [
            {
                type: 'value',
                name: 'Price',
                position: 'left',
                scale: true,
                splitLine: { lineStyle: { color: '#334155' } }
            },
            {
                type: 'value',
                name: 'OI',
                position: 'right',
                splitLine: { show: false }
            }
        ],
        series: [
            {
                name: 'Price',
                type: 'line',
                data: prices,
                smooth: true,
                lineStyle: { color: '#38bdf8' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(56, 189, 248, 0.5)' },
                        { offset: 1, color: 'rgba(56, 189, 248, 0.0)' }
                    ])
                }
            },
            {
                name: 'Open Interest',
                type: 'line',
                yAxisIndex: 1,
                data: ois,
                showSymbol: false,
                lineStyle: { color: '#94a3b8', type: 'dashed' }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

function renderHistoricalChart(slvData, cmeData) {
    const chartDom = document.getElementById('inventoryChart');
    const myChart = echarts.init(chartDom);

    const dates = cmeData.map(item => item.timestamp);
    const cmeVals = cmeData.map(item => item.value / 1000000); // Convert to Million oz
    // const slvVals = slvData.map(item => item.value); // Need to handle if slvData is empty or different length

    const option = {
        title: { text: '30-Day Inventory Trend (Million oz)', textStyle: { fontSize: 12, color: '#94a3b8' } },
        tooltip: { trigger: 'axis' },
        legend: { data: ['CME Registered'], textStyle: { color: '#94a3b8' } },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
            type: 'category',
            data: dates,
            axisLabel: { formatter: (value) => value.substring(5, 10) } // MM-DD
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { lineStyle: { color: '#334155' } }
        },
        series: [
            {
                name: 'CME Registered',
                type: 'line',
                data: cmeVals,
                smooth: true,
                lineStyle: { color: '#f87171' }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

function renderSlvChart(slvData) {
    const ctx = document.getElementById('slvChart').getContext('2d');
    // Destroy existing chart if any (Chart.js specific, but we are keeping Chart.js for this one for now as per plan "View 1... View 2" were the main changes)
    // Actually, let's just keep using Chart.js for the simple doughnut if it works, or switch to ECharts.
    // The user asked for "View 1" and "View 2" to be ECharts (implied by "Integrate a charting library... View 1... View 2").
    // But I'll leave the Doughnut as Chart.js since I didn't change its container.

    // We want a time-series chart here, but 'slvData' passed from updateDashboard is just the current snapshot.
    // We need to fetch history for this chart too, or use the history we fetched in fetchHistoryAndRender.
    // Actually, fetchHistoryAndRender calls renderHistoricalChart for inventory.
    // Let's repurpose the 'slvChart' canvas to be an ECharts container.

    // First, ensure the container is a div, not canvas (we might need to change HTML or just replace the element via JS)
    const container = document.querySelector('#slvChart').parentElement;
    if (container.querySelector('canvas')) {
        container.innerHTML = '<div id="slvChart" style="width: 100%; height: 100%;"></div>';
    }

    // Now we need history data. This function is called with snapshot data.
    // We should rely on fetchHistoryAndRender to draw this chart.
    // So we'll leave this empty or just update the text values, and let fetchHistoryAndRender handle the chart.
}

// New function to render SLV History (called from fetchHistoryAndRender)
function renderSlvHistoryChart(slvHistoryData) {
    const chartDom = document.getElementById('slvChart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);

    // If we don't have real inventory history, we might have backfilled price/OI.
    // If slvHistoryData is empty, show message.
    if (!slvHistoryData || slvHistoryData.length === 0) {
        // myChart.showLoading(); // or show "No Data"
        return;
    }

    const dates = slvHistoryData.map(item => item.timestamp);
    const values = slvHistoryData.map(item => item.value); // Tonnes or Ounces? Metric says 'SLV_Inventory_Ounces'

    const option = {
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
            type: 'category',
            data: dates,
            axisLabel: { formatter: (value) => value.substring(5, 10) }
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { lineStyle: { color: '#334155' } }
        },
        series: [
            {
                name: 'SLV Inventory (oz)',
                type: 'line',
                data: values,
                smooth: true,
                lineStyle: { color: '#38bdf8' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(56, 189, 248, 0.5)' },
                        { offset: 1, color: 'rgba(56, 189, 248, 0.0)' }
                    ])
                }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

function renderP0Chart(p0) {
    const ctx = document.getElementById('p0Chart').getContext('2d');

    const labels = [];
    const values = [];
    const colors = [];

    const metrics = [
        { label: 'Paper/Phys', value: p0.Paper_to_Physical, color: 'rgba(248, 113, 113, 0.7)' },
        { label: 'SLV Cov', value: p0.SLV_Coverage, color: 'rgba(251, 191, 36, 0.7)' },
        { label: 'Dominance', value: p0.COMEX_Dominance, color: 'rgba(56, 189, 248, 0.7)' },
        { label: 'Shanghai', value: p0.Shanghai_Premium_Implied, color: 'rgba(52, 211, 153, 0.7)' },
        { label: 'Turnover', value: p0.Turnover_ag2603, color: 'rgba(167, 139, 250, 0.7)' },
        { label: 'Concen', value: p0.OI_concentration_2603, color: 'rgba(236, 72, 153, 0.7)' }
    ];

    metrics.forEach(m => {
        if (m.value !== null && m.value !== undefined && m.value !== 'N/A') {
            labels.push(m.label);
            values.push(Math.abs(m.value));
            colors.push(m.color);
        }
    });

    if (window.p0ChartInstance) window.p0ChartInstance.destroy();

    if (values.length === 0) return;

    window.p0ChartInstance = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'P0 Indicators',
                data: values,
                backgroundColor: 'rgba(56, 189, 248, 0.2)',
                borderColor: '#38bdf8',
                borderWidth: 2,
                pointBackgroundColor: colors,
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: colors
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                r: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#94a3b8', backdropColor: 'transparent' },
                    pointLabels: { color: '#94a3b8', font: { size: 11 } }
                }
            }
        }
    });
}

function renderP0HistoryChart(historyData, metricName) {
    const chartDom = document.getElementById('p0HistoryChart');
    if (!chartDom) return;

    // Dispose existing instance if any (ECharts specific)
    const existingChart = echarts.getInstanceByDom(chartDom);
    if (existingChart) existingChart.dispose();

    const myChart = echarts.init(chartDom);

    const dates = historyData.map(item => item.timestamp);
    const values = historyData.map(item => item.value);

    const option = {
        title: {
            text: metricName.replace(/_/g, ' '),
            textStyle: { fontSize: 14, color: '#e2e8f0' },
            left: 'center'
        },
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
            type: 'category',
            data: dates,
            axisLabel: { formatter: (value) => value.substring(5, 16) } // MM-DD HH:MM
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { lineStyle: { color: '#334155' } }
        },
        series: [
            {
                name: metricName,
                type: 'line',
                data: values,
                smooth: true,
                lineStyle: { color: '#38bdf8' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(56, 189, 248, 0.5)' },
                        { offset: 1, color: 'rgba(56, 189, 248, 0.0)' }
                    ])
                }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}
