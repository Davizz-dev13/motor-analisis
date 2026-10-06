#!/usr/bin/env python3
"""Fixture sintetico para probar el motor SIN red.

Empresa ficticia DEMO (Demo Semiconductores SA). Numeros redondos e inventados
solo para pruebas: nunca se publican como datos reales. El fixture esta
pensado para disparar varias senales de alerta (conversion de caja cayendo,
cuentas por cobrar creciendo mucho mas que las ventas).
"""
from __future__ import annotations

Q = [  # 8 trimestres, antiguo -> reciente
    "2025-01-31", "2025-04-30", "2025-07-31", "2025-10-31",
    "2026-01-31", "2026-04-30", "2026-07-31", "2026-10-05",
]
REV = [20_000e6, 22_000e6, 24_000e6, 26_000e6, 28_000e6, 30_000e6, 33_000e6, 36_000e6]
NI  = [ 8_000e6,  8_800e6,  9_600e6, 10_400e6, 11_200e6, 12_000e6, 13_200e6, 14_400e6]
CFO = [ 8_800e6,  9_700e6, 10_600e6, 11_400e6,  7_800e6,  6_900e6,  7_500e6,  8_100e6]  # se rompe en el ano 2
CAP = [-2_000e6, -2_100e6, -2_200e6, -2_300e6, -2_600e6, -2_800e6, -3_100e6, -3_400e6]
AR  = [ 8_000e6,  8_500e6,  9_000e6, 10_000e6, 14_000e6, 16_000e6, 19_000e6, 23_000e6]  # +64% vs +38% ventas
INV = [ 5_000e6,  5_000e6,  5_200e6,  5_500e6,  6_000e6,  6_200e6,  6_500e6,  7_000e6]
SBC = [ 1_000e6,  1_000e6,  1_100e6,  1_100e6,  1_200e6,  1_200e6,  1_300e6,  1_300e6]
DA  = [ 1_500e6,  1_500e6,  1_500e6,  1_500e6,  1_600e6,  1_600e6,  1_700e6,  1_700e6]
SH  = [24_500e6, 24_450e6, 24_400e6, 24_350e6, 24_300e6, 24_250e6, 24_200e6, 24_150e6]


def _q(series):
    return list(zip(Q, series))


def build_raw() -> dict:
    gp = [r * 0.75 for r in REV]
    op = [n * 1.12 for n in NI]
    fcf = [c + x for c, x in zip(CFO, CAP)]
    return {
        "ticker": "DEMO",
        "fetched_at": "2026-10-05T21:30:00+00:00",
        "info": {
            "longName": "Demo Semiconductores SA (empresa ficticia de pruebas)",
            "currentPrice": 239.0,
            "marketCap": 239.0 * 24_150e6,
            "currency": "USD",
            "financialCurrency": "USD",
            "fiftyTwoWeekLow": 110.5,
            "fiftyTwoWeekHigh": 245.3,
            "sharesOutstanding": 24_150e6,
        },
        "fast_info": None,
        "q_income": {
            "Total Revenue": _q(REV),
            "Gross Profit": _q(gp),
            "Operating Income": _q(op),
            "Net Income": _q(NI),
            "Diluted Average Shares": _q(SH),
        },
        "a_income": {
            "Total Revenue": [("2026-01-31", 92_000e6), ("2025-01-31", 66_000e6),
                              ("2024-01-31", 48_000e6), ("2023-01-31", 36_000e6)],
            "Diluted EPS": [("2026-01-31", 5.5), ("2025-01-31", 4.2),
                            ("2024-01-31", 3.0), ("2023-01-31", 2.0)],
        },
        "q_balance": {
            "Accounts Receivable": _q(AR),
            "Inventory": _q(INV),
            "Cash Cash Equivalents And Short Term Investments": _q([40_000e6] * 8),
            "Total Debt": _q([10_000e6] * 8),
        },
        "q_cashflow": {
            "Operating Cash Flow": _q(CFO),
            "Capital Expenditure": _q(CAP),
            "Free Cash Flow": _q(fcf),
            "Stock Based Compensation": _q(SBC),
            "Depreciation And Amortization": _q(DA),
        },
        "a_cashflow": None,
        "earnings_estimate": {
            "avg": [("+1y", 12.5)], "low": [("+1y", 10.8)], "high": [("+1y", 14.2)],
            "numberOfAnalysts": [("+1y", 45.0)], "growth": [("+1y", 0.35)],
        },
        "revenue_estimate": {"growth": [("+1y", 0.30)]},
        "price_targets": {"low": 150.0, "mean": 290.0, "median": 300.0, "high": 400.0},
        "annual_close_means": {"2023": 60.0, "2024": 95.0, "2025": 140.0, "2026": 180.0},
        "financial_currency": "USD",
        "price_currency": "USD",
        "fx_fin_to_price": None,
        "data_quality": ["FIXTURE SINTETICO: numeros inventados solo para probar el formato"],
    }
