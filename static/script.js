document.addEventListener('DOMContentLoaded', () => {
    fetchData();
});

async function fetchData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Error fetching data:', error);
    }
}

function updateDashboard(data) {
    // Futures
    if (data.futures && !data.futures.error) {
        document.getElementById('futures-price').textContent = `$${data.futures.price}`;
        document.getElementById('futures-volume').textContent = formatNumber(data.futures.volume);
        document.getElementById('futures-oi').textContent = formatNumber(data.futures.open_interest);

        renderFuturesChart(data.futures);
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

        renderInventoryChart(data.cme, data.lbma);
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
        document.getElementById('p0-paper-physical').textContent = formatValue(p0.paper_to_physical);
        document.getElementById('p0-slv-coverage').textContent = formatValue(p0.slv_coverage);
        document.getElementById('p0-dominance').textContent = formatValue(p0.comex_dominance);
        document.getElementById('p0-shanghai-prem').textContent = formatValue(p0.shanghai_premium, '$');
        document.getElementById('p0-shfe-turnover').textContent = formatValue(p0.shfe_turnover);
        document.getElementById('p0-shfe-conc').textContent = formatValue(p0.shfe_concentration);
        document.getElementById('p0-curve-slope').textContent = formatValue(p0.shfe_curve_slope);

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

function renderFuturesChart(futuresData) {
    const ctx = document.getElementById('futuresChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Volume', 'Open Interest'],
            datasets: [{
                label: 'Contracts',
                data: [futuresData.volume, futuresData.open_interest],
                backgroundColor: ['rgba(56, 189, 248, 0.5)', 'rgba(148, 163, 184, 0.5)'],
                borderColor: ['#38bdf8', '#94a3b8'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

function renderSlvChart(slvData) {
    const ctx = document.getElementById('slvChart').getContext('2d');
    const tonnes = parseFloat(slvData.inventory_tonnes.replace(/,/g, ''));

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['SLV Inventory (Tonnes)'],
            datasets: [{
                data: [tonnes],
                backgroundColor: ['rgba(56, 189, 248, 0.8)'],
                borderColor: ['#1e293b'],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8' } }
            }
        }
    });
}

function renderInventoryChart(cmeData, lbmaData) {
    const ctx = document.getElementById('inventoryChart').getContext('2d');

    const cmeRegTonnes = parseFloat(cmeData.registered.toString().replace(/,/g, '')) / 32150.7;
    const cmeEligTonnes = parseFloat(cmeData.eligible.toString().replace(/,/g, '')) / 32150.7;
    const lbmaTonnes = parseFloat(lbmaData.holdings_tonnes.replace(/,/g, ''));

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['CME Registered', 'CME Eligible', 'LBMA Vaults'],
            datasets: [{
                label: 'Inventory (Tonnes)',
                data: [cmeRegTonnes, cmeEligTonnes, lbmaTonnes],
                backgroundColor: [
                    'rgba(248, 113, 113, 0.6)',
                    'rgba(251, 191, 36, 0.6)',
                    'rgba(52, 211, 153, 0.6)'
                ],
                borderColor: ['#f87171', '#fbbf24', '#34d399'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    ticks: { color: '#94a3b8' },
                    title: { display: true, text: 'Tonnes', color: '#94a3b8' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

function renderP0Chart(p0) {
    const ctx = document.getElementById('p0Chart').getContext('2d');

    // Filter out null/N/A values for visualization
    const labels = [];
    const values = [];
    const colors = [];

    const metrics = [
        { label: 'Paper/Phys', value: p0.paper_to_physical, color: 'rgba(248, 113, 113, 0.7)' },
        { label: 'SLV Cov', value: p0.slv_coverage, color: 'rgba(251, 191, 36, 0.7)' },
        { label: 'Dominance', value: p0.comex_dominance, color: 'rgba(56, 189, 248, 0.7)' },
        { label: 'Premium', value: p0.shanghai_premium, color: 'rgba(52, 211, 153, 0.7)' },
        { label: 'Turnover', value: p0.shfe_turnover, color: 'rgba(167, 139, 250, 0.7)' },
        { label: 'Concentration', value: p0.shfe_concentration, color: 'rgba(236, 72, 153, 0.7)' }
    ];

    metrics.forEach(m => {
        if (m.value !== null && m.value !== undefined && m.value !== 'N/A') {
            labels.push(m.label);
            values.push(Math.abs(m.value)); // Use abs for visualization
            colors.push(m.color);
        }
    });

    if (values.length === 0) {
        // Show placeholder
        ctx.font = '14px Inter';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'center';
        ctx.fillText('No P0 data available yet', ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    new Chart(ctx, {
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
            plugins: {
                legend: { display: false }
            },
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
