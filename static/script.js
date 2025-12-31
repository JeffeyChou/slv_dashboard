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
        document.getElementById('shfe-price').textContent = data.shfe.price_cny;
        document.getElementById('shfe-premium').textContent = data.shfe.premium_usd;
    }
}

function formatNumber(numStr) {
    if (!numStr) return 'N/A';
    // Remove commas if any, then format
    const num = parseFloat(numStr.toString().replace(/,/g, ''));
    if (isNaN(num)) return numStr;
    return num.toLocaleString();
}

function renderFuturesChart(futuresData) {
    const ctx = document.getElementById('futuresChart').getContext('2d');
    // Destroy existing chart if any (simple way: replace canvas, but here we just overwrite)
    // For production, we should track chart instances.

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
            plugins: {
                legend: { display: false }
            },
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

    const cmeRegTonnes = parseFloat(cmeData.registered.replace(/,/g, '')) / 32150.7;
    const cmeEligTonnes = parseFloat(cmeData.eligible.replace(/,/g, '')) / 32150.7;
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
                borderColor: [
                    '#f87171',
                    '#fbbf24',
                    '#34d399'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
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
