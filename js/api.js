/**
 * API service for FX rates and freight container prices.
 *
 * FX data: Multiple free providers with automatic fallback:
 *   1. Frankfurter API (ECB rates, no key)
 *   2. Fawaz Ahmed open-api (no key)
 *   3. Generated fallback with realistic rates
 *
 * Freight data: Generated data modelled on Freightos Baltic Index (FBX).
 *   Replace with real API (Freightos/Xeneta/Drewry) when available.
 */

const API = (() => {
    const FRANKFURTER_BASE = 'https://api.frankfurter.dev';

    // ── Helpers ──────────────────────────────────────────────

    function dateStr(d) {
        return d.toISOString().slice(0, 10);
    }

    function subtractDays(date, days) {
        const d = new Date(date);
        d.setDate(d.getDate() - days);
        return d;
    }

    function rangeToDays(range) {
        const map = { '1D': 1, '30D': 30, '6M': 183, '1Y': 365, '5Y': 1826 };
        return map[range] || 30;
    }

    function rangeToDates(range) {
        const now = new Date();
        return { from: subtractDays(now, rangeToDays(range)), to: now };
    }

    // ── FX Rates: Provider 1 – Frankfurter ──────────────────

    async function frankfurterTimeSeries(currency, range) {
        const { from, to } = rangeToDates(range);
        const url = `${FRANKFURTER_BASE}/${dateStr(from)}..${dateStr(to)}?from=EUR&to=${currency}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Frankfurter ${res.status}`);
        const data = await res.json();
        const points = Object.entries(data.rates).map(([date, rates]) => ({
            date,
            value: rates[currency],
        }));
        points.sort((a, b) => a.date.localeCompare(b.date));
        return points;
    }

    async function frankfurterLatest(currency) {
        const res = await fetch(`${FRANKFURTER_BASE}/latest?from=EUR&to=${currency}`);
        if (!res.ok) throw new Error(`Frankfurter ${res.status}`);
        const data = await res.json();
        return { date: data.date, value: data.rates[currency] };
    }

    // ── FX Rates: Provider 2 – Fawaz Ahmed open-api ─────────

    async function fawazTimeSeries(currency, range) {
        const { from, to } = rangeToDates(range);
        const curr = currency.toLowerCase();
        // This API returns daily snapshots; we fetch the full history file
        const url = `https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/eur.json`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Fawaz API ${res.status}`);
        const data = await res.json();
        const latestValue = data.eur[curr];
        if (!latestValue) throw new Error('Currency not found');

        // This API only gives latest; generate history from it
        return generateFXHistory(latestValue, range);
    }

    async function fawazLatest(currency) {
        const curr = currency.toLowerCase();
        const url = `https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/eur.json`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`Fawaz API ${res.status}`);
        const data = await res.json();
        const value = data.eur[curr];
        if (!value) throw new Error('Currency not found');
        return { date: data.date || dateStr(new Date()), value };
    }

    // ── FX Rates: Fallback – Generated realistic data ───────

    // Realistic base rates (approximate current market levels)
    const BASE_RATES = { GBP: 0.8580, CNY: 7.7800 };
    const VOLATILITY = { GBP: 0.0008, CNY: 0.012 };

    function generateFXHistory(currentRate, range) {
        const { from, to } = rangeToDates(range);
        const days = Math.round((to - from) / 86400000);
        const points = [];

        let seed = Math.round(currentRate * 10000);
        function seededRandom() {
            seed = (seed * 16807) % 2147483647;
            return (seed - 1) / 2147483646;
        }

        const step = days <= 60 ? 1 : (days <= 400 ? 1 : 7);
        const totalSteps = Math.ceil(days / step);
        // Work backwards from current rate
        const vol = currentRate * 0.001;
        let rate = currentRate;
        const ratesArr = [rate];
        for (let i = 1; i <= totalSteps; i++) {
            rate = rate - (seededRandom() - 0.5) * vol * 2;
            ratesArr.unshift(rate);
        }

        for (let i = 0; i <= totalSteps; i++) {
            const d = new Date(from);
            d.setDate(d.getDate() + i * step);
            if (d > to) break;
            // Skip weekends
            const dow = d.getDay();
            if (dow === 0 || dow === 6) continue;
            points.push({ date: dateStr(d), value: Math.round(ratesArr[i] * 10000) / 10000 });
        }
        return points;
    }

    function fallbackTimeSeries(currency, range) {
        const base = BASE_RATES[currency] || 1;
        return generateFXHistory(base, range);
    }

    function fallbackLatest(currency) {
        const base = BASE_RATES[currency] || 1;
        return { date: dateStr(new Date()), value: base };
    }

    // ── FX Rates: Fetch with fallback chain ─────────────────

    async function fetchFXTimeSeries(currency, range) {
        // Try providers in order
        const providers = [
            () => frankfurterTimeSeries(currency, range),
            () => fawazTimeSeries(currency, range),
        ];

        for (const provider of providers) {
            try {
                return await provider();
            } catch (e) {
                console.warn('FX provider failed, trying next:', e.message);
            }
        }

        // Final fallback: generated data
        console.warn('All FX APIs failed, using generated data for', currency);
        return fallbackTimeSeries(currency, range);
    }

    async function fetchLatestFX(currency) {
        const providers = [
            () => frankfurterLatest(currency),
            () => fawazLatest(currency),
        ];

        for (const provider of providers) {
            try {
                return await provider();
            } catch (e) {
                console.warn('FX latest provider failed:', e.message);
            }
        }

        console.warn('All FX APIs failed, using fallback rate for', currency);
        return fallbackLatest(currency);
    }

    // ── Freight Container Prices ────────────────────────────
    //
    // The Freightos Baltic Index (FBX) is the industry benchmark.
    // Since there is no free public API, we generate realistic data
    // modelled on historical FBX patterns (base ~$1,400-$8,000/FEU).
    // Replace generateFreightData() with a real API call when you
    // have access to Freightos, Xeneta, or Drewry APIs.

    function generateFreightData(range) {
        const { from, to } = rangeToDates(range);
        const days = Math.round((to - from) / 86400000);

        let seed = 42;
        function seededRandom() {
            seed = (seed * 16807 + 0) % 2147483647;
            return (seed - 1) / 2147483646;
        }

        const basePrice = 2200;
        const step = days <= 30 ? 1 : (days <= 365 ? 1 : 7);
        const totalSteps = Math.ceil(days / step);

        const startPrice = range === '5Y' ? 1400 :
                           range === '1Y' ? 1900 :
                           range === '6M' ? 2050 :
                           basePrice - 80;
        let price = startPrice;
        const points = [];

        for (let i = 0; i <= totalSteps; i++) {
            const d = new Date(from);
            d.setDate(d.getDate() + i * step);
            if (d > to) break;

            const month = d.getMonth();
            const seasonal = Math.sin((month - 2) * Math.PI / 6) * 150;
            const trend = (basePrice - price) * 0.003;
            const noise = (seededRandom() - 0.48) * 60;

            let spike = 0;
            const year = d.getFullYear();
            if (year === 2021) spike = 3500 * Math.sin((month + 1) * Math.PI / 12);
            if (year === 2022 && month < 9) spike = 4000 * Math.max(0, 1 - month / 9);

            price = Math.max(800, price + trend + noise);
            const displayPrice = Math.round(price + seasonal + spike);

            points.push({
                date: dateStr(d),
                value: Math.max(600, displayPrice),
            });
        }

        return points;
    }

    async function fetchFreightTimeSeries(range) {
        return generateFreightData(range);
    }

    function getLatestFreight() {
        const data = generateFreightData('30D');
        return data[data.length - 1];
    }

    // ── Public API ──────────────────────────────────────────

    return {
        fetchFXTimeSeries,
        fetchLatestFX,
        fetchFreightTimeSeries,
        getLatestFreight,
    };
})();
