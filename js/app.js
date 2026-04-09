/**
 * Main application – wires up data fetching, charts, and UI interactions.
 */

(() => {
    // Current selected range per chart
    const state = {
        eurgbp: '30D',
        eurcny: '30D',
        freight: '30D',
    };

    const COLORS = {
        eurgbp: '#4fc3f7',
        eurcny: '#ffb74d',
        freight: '#81c784',
    };

    const REFRESH_INTERVAL = 60_000; // 60 seconds

    // ── Data Loading ────────────────────────────────────────

    async function loadChart(key) {
        const canvasId = `chart-${key}`;
        Charts.showLoading(canvasId);

        try {
            let data;
            let label;
            let isCurrency;
            let symbol;

            switch (key) {
                case 'eurgbp':
                    data = await API.fetchFXTimeSeries('GBP', state.eurgbp);
                    label = 'EUR/GBP';
                    isCurrency = true;
                    break;
                case 'eurcny':
                    data = await API.fetchFXTimeSeries('CNY', state.eurcny);
                    label = 'EUR/CNY';
                    isCurrency = true;
                    break;
                case 'freight':
                    data = await API.fetchFreightTimeSeries(state.freight);
                    label = 'FBX Index';
                    isCurrency = false;
                    symbol = '$';
                    break;
            }

            Charts.createOrUpdate(canvasId, data, label, COLORS[key], isCurrency, symbol);
        } catch (err) {
            console.error(`Failed to load ${key}:`, err);
            Charts.hideLoading(canvasId);
            showError(`Failed to load ${key} data. Retrying...`);
        }
    }

    async function loadRateCards() {
        try {
            const [gbp, cny] = await Promise.all([
                API.fetchLatestFX('GBP'),
                API.fetchLatestFX('CNY'),
            ]);
            const freight = API.getLatestFreight();

            updateRateCard('eurgbp', gbp.value, 4);
            updateRateCard('eurcny', cny.value, 4);
            updateRateCard('freight', freight.value, 0, '$', '/FEU');

            document.getElementById('last-updated').textContent =
                `Updated ${new Date().toLocaleTimeString('en-GB')}`;
        } catch (err) {
            console.error('Failed to load rate cards:', err);
        }
    }

    function updateRateCard(key, value, decimals, prefix = '', suffix = '') {
        const el = document.getElementById(`rate-${key}`);
        const changeEl = document.getElementById(`change-${key}`);

        const prev = el.dataset.prev ? parseFloat(el.dataset.prev) : null;
        const formatted = prefix + value.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',') + suffix;
        el.textContent = formatted;
        el.dataset.prev = value;

        if (prev !== null) {
            const diff = value - prev;
            const pct = ((diff / prev) * 100).toFixed(2);
            const sign = diff >= 0 ? '+' : '';
            changeEl.textContent = `${sign}${diff.toFixed(decimals)} (${sign}${pct}%)`;
            changeEl.className = `rate-change ${diff >= 0 ? 'positive' : 'negative'}`;
        } else {
            changeEl.textContent = '--';
            changeEl.className = 'rate-change';
        }
    }

    // ── UI Interactions ─────────────────────────────────────

    function setupRangeButtons() {
        document.querySelectorAll('.time-range-selector').forEach(selector => {
            const chartKey = selector.dataset.chart;
            selector.querySelectorAll('.range-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    // Update active state
                    selector.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    // Update state and reload chart
                    state[chartKey] = btn.dataset.range;
                    loadChart(chartKey);
                });
            });
        });
    }

    function showError(msg) {
        // Remove existing toast
        const existing = document.querySelector('.error-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'error-toast';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 5000);
    }

    // ── Initialization ──────────────────────────────────────

    async function init() {
        setupRangeButtons();

        // Load everything in parallel
        await Promise.all([
            loadRateCards(),
            loadChart('eurgbp'),
            loadChart('eurcny'),
            loadChart('freight'),
        ]);

        // Auto-refresh
        setInterval(() => {
            loadRateCards();
            loadChart('eurgbp');
            loadChart('eurcny');
            loadChart('freight');
        }, REFRESH_INTERVAL);
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
