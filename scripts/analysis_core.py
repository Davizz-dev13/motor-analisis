#!/usr/bin/env python3
"""Nucleo del motor de analisis de tecnologicas (Sharpe Lab).

Dos piezas separadas:
- fetch_raw(ticker): descarga de Yahoo Finance (corre en la Action o en local con red).
- compute_report(raw): matematica pura y testeable -> dict JSON-serializable.

Reglas del motor:
- Cada cifra lleva fuente y fecha; lo que no se puede verificar queda en None
  y la pagina lo muestra como "-".
- El motor es mecanico: no cruza el 10-Q/10-K ni juzga riesgos. Las senales de
  alerta son eso, senales a revisar a mano; nunca acusaciones.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics

# ---------------------------------------------------------------------------
# Parametros del motor (visibles en la pagina; no son consenso, son del motor)
# ---------------------------------------------------------------------------
DCF_DISCOUNT = 0.095          # tipo de descuento central
DCF_DISCOUNT_GRID = [0.085, 0.095, 0.105]
DCF_TERMINAL = 0.04           # crecimiento en perpetuidad central
DCF_TERMINAL_GRID = [0.03, 0.04, 0.05]
DCF_YEARS = 5
BLEND_W_PER = 0.60            # 60% escenarios PER + 40% DCF: igual para las 15 empresas
BLEND_W_DCF = 0.40
PE_BAND = 1.5                 # el multiplo historico se acota a [1/1,5 ; 1,5] veces el PER forward actual
FCF_YEARS = 3                 # ejercicios anuales + TTM para normalizar el margen FCF (capex incluido)

# Universo tecnologico/semis (ampliable; David 2026-10-05)
UNIVERSE = [
    "NVDA", "MSFT", "GOOGL", "AAPL", "AMZN", "META", "TSLA",
    "AVGO", "AMD", "TSM", "ASML", "MU", "INTC", "QCOM", "TXN",
]

LIMITS = [
    "No cruza el 10-Q/10-K ni las presentaciones: partidas puntuales, garantias, financiacion de clientes y letra pequena quedan fuera.",
    "La concentracion de clientes no esta en Yahoo: se mira a mano en la memoria anual.",
    "ASML y TSM reportan como emisor extranjero (20-F/6-K, no 10-Q) y en EUR/TWD: conversion a USD a tipo de cambio actual y ratio de ADR aproximado via capitalizacion.",
    "Las estimaciones son consenso de Yahoo, no propias; los escenarios usan multiplos historicos del propio valor.",
    "Las senales de alerta salen de las cuentas publicadas: indican donde mirar, no prueban maquillaje.",
    "No mira insiders, interes corto, opciones ni analisis tecnico.",
    "Analisis mecanico con fines informativos; no es asesoramiento financiero regulado.",
]


# ---------------------------------------------------------------------------
# Capa de datos (Yahoo). Cada descarga es independiente: si una falla, el
# resto sigue y el fallo queda registrado en data_quality.
# ---------------------------------------------------------------------------
def _safe(fn, quality, label):
    try:
        out = fn()
        if out is None:
            quality.append(f"sin datos: {label}")
        return out
    except Exception as e:  # noqa: BLE001 - el motor nunca muere por una fuente
        quality.append(f"fallo en {label}: {type(e).__name__}")
        return None


def _est_to_records(df):
    """DataFrame de estimaciones yfinance (filas=periodos 0q/+1q/0y/+1y, cols=metricas)
    -> {metrica: [(periodo, valor)]}. Las etiquetas de periodo NO son fechas."""
    if df is None or getattr(df, "empty", True):
        return None
    out = {}
    for col in df.columns:
        vals = []
        for per, v in df[col].items():
            try:
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                vals.append((str(per), float(v)))
            except Exception:  # noqa: BLE001
                continue
        if vals:
            out[str(col)] = vals
    return out or None


def _df_to_records(df):
    """DataFrame de yfinance (filas=partidas, cols=fechas) -> {partida: [(fecha, valor)]}."""
    if df is None or getattr(df, "empty", True):
        return None
    import pandas as pd
    out = {}
    for row_label, row in df.iterrows():
        vals = []
        for col, v in row.items():
            try:
                if v is None or (isinstance(v, float) and math.isnan(v)):
                    continue
                vals.append((str(pd.Timestamp(col).date()), float(v)))
            except Exception:  # noqa: BLE001
                continue
        if vals:
            out[str(row_label)] = vals
    return out or None


def fetch_raw(ticker: str) -> dict:
    import yfinance as yf

    quality: list[str] = []
    t = yf.Ticker(ticker)

    info = _safe(lambda: t.info, quality, "info")
    fast = _safe(lambda: dict(t.fast_info), quality, "fast_info")

    q_inc = _safe(lambda: t.quarterly_income_stmt, quality, "resultados trimestrales")
    a_inc = _safe(lambda: t.income_stmt, quality, "resultados anuales")
    q_bal = _safe(lambda: t.quarterly_balance_sheet, quality, "balance trimestral")
    q_cf = _safe(lambda: t.quarterly_cashflow, quality, "flujos trimestrales")
    a_cf = _safe(lambda: t.cashflow, quality, "flujos anuales")
    est = _safe(lambda: t.earnings_estimate, quality, "estimaciones BPA")
    rev_est = _safe(lambda: t.revenue_estimate, quality, "estimaciones ventas")
    targets = _safe(lambda: t.analyst_price_targets, quality, "objetivos de analistas")

    closes = _safe(lambda: _annual_price_means(ticker), quality, "historico de precios")

    fin_ccy = (info or {}).get("financialCurrency") or "USD"
    price_ccy = (info or {}).get("currency") or "USD"
    fx = None
    if fin_ccy != price_ccy:
        fx = _safe(lambda: _fx_rate(f"{fin_ccy}{price_ccy}=X", f"{price_ccy}{fin_ccy}=X"),
                   quality, f"divisa {fin_ccy}->{price_ccy}")

    return {
        "ticker": ticker,
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "info": info,
        "fast_info": fast,
        "q_income": _df_to_records(q_inc),
        "a_income": _df_to_records(a_inc),
        "q_balance": _df_to_records(q_bal),
        "q_cashflow": _df_to_records(q_cf),
        "a_cashflow": _df_to_records(a_cf),
        "earnings_estimate": _est_to_records(est),
        "revenue_estimate": _est_to_records(rev_est),
        "price_targets": targets,
        "annual_close_means": closes,
        "financial_currency": fin_ccy,
        "price_currency": price_ccy,
        "fx_fin_to_price": fx,
        "data_quality": quality,
    }


def _annual_price_means(ticker: str) -> dict:
    """Media de cierres por ano natural (para PER historico). Usa core.data si esta en el repo."""
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from core.data import history
        df = history(ticker, "10y", "1d")
    except Exception:  # noqa: BLE001 - fuera del repo, yfinance directo
        import yfinance as yf
        df = yf.download(ticker, period="10y", interval="1d", auto_adjust=True, progress=False)
        if hasattr(df.columns, "get_level_values"):
            df.columns = df.columns.get_level_values(0)
    if df is None or df.empty:
        return None
    close = df["Close"] if "Close" in df.columns else df["close"]
    by_year: dict[str, list[float]] = {}
    for ts, v in close.items():
        by_year.setdefault(str(ts.year), []).append(float(v))
    return {y: sum(v) / len(v) for y, v in sorted(by_year.items())}


def _fx_rate(pair: str, inverse_pair: str) -> float | None:
    import yfinance as yf
    for p, inv in ((pair, False), (inverse_pair, True)):
        d = yf.download(p, period="5d", interval="1d", progress=False)
        if not d.empty:
            c = d["Close"]
            v = float(getattr(c, "values", c).flatten()[-1])
            return (1.0 / v) if inv else v
    return None


# ---------------------------------------------------------------------------
# Matematica pura
# ---------------------------------------------------------------------------
def _series(records: dict | None, *keys: str) -> list[tuple[str, float]]:
    """Serie (fecha, valor) de la primera partida que exista, reciente primero."""
    if not records:
        return []
    for k in keys:
        if k in records and records[k]:
            return sorted(records[k], key=lambda x: x[0], reverse=True)
    return []


def _ttm(series: list[tuple[str, float]], skip: int = 0) -> float | None:
    vals = [v for _, v in series[skip:skip + 4]]
    return sum(vals) if len(vals) == 4 else None


def _pct(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return (a / b - 1.0) * 100.0


def _growth_from_estimate(rec: dict | None) -> float | None:
    if not rec:
        return None
    growth = rec.get("growth")
    if growth:
        d = dict(growth)
        for per in ("+1y", "0y"):
            if per in d:
                return float(d[per]) * 100.0
    return None


def _est_row(rec: dict | None, metric: str, period: str) -> float | None:
    if not rec or metric not in rec:
        return None
    d = dict(rec[metric])
    v = d.get(period)
    return float(v) if v is not None else None


def _dcf(fcf_ttm, rev_ttm, rev_growth_next_pct, net_cash, shares, fx,
         discount, terminal):
    # fcf_ttm aqui es el FCF NORMALIZADO (margen medio TTM + ejercicios x ventas TTM):
    # el capex pesado de un ciclo de inversion baja el margen en vez de eximir a la empresa.
    if fcf_ttm is None or rev_ttm in (None, 0) or not shares or shares <= 0:
        return None
    if rev_ttm <= 0:
        return None
    if fcf_ttm < 0:
        fcf_ttm = 0.0
    g1 = max(-20.0, min(40.0, rev_growth_next_pct)) / 100.0 if rev_growth_next_pct else 0.10
    fcf_margin = fcf_ttm / rev_ttm
    rev = rev_ttm
    pv = 0.0
    fcf_last = None
    for yr in range(1, DCF_YEARS + 1):
        g = g1 + (terminal - g1) * (yr - 1) / (DCF_YEARS - 1)
        rev *= (1 + g)
        fcf_last = rev * fcf_margin
        pv += fcf_last / (1 + discount) ** yr
    tv = fcf_last * (1 + terminal) / (discount - terminal)
    pv += tv / (1 + discount) ** DCF_YEARS
    equity = pv + (net_cash or 0.0)
    if fx:
        equity *= fx
    return equity / shares


def compute_report(raw: dict) -> dict:
    info = raw.get("info") or {}
    fast = raw.get("fast_info") or {}
    quality = list(raw.get("data_quality") or [])

    price = (info.get("currentPrice") or info.get("regularMarketPrice")
             or fast.get("last_price") or fast.get("lastPrice"))
    mcap = info.get("marketCap") or fast.get("market_cap") or fast.get("marketCap")
    price = float(price) if price else None
    mcap = float(mcap) if mcap else None
    shares = (mcap / price) if (mcap and price) else (info.get("sharesOutstanding") or None)
    if shares:
        shares = float(shares)

    q_inc, a_inc = raw.get("q_income"), raw.get("a_income")
    q_cf = raw.get("q_cashflow")
    q_bal = raw.get("q_balance")

    rev_q = _series(q_inc, "Total Revenue")
    rev_ttm = _ttm(rev_q)
    rev_ttm_prev = _ttm(rev_q, skip=4)
    rev_yoy = _pct(rev_ttm, rev_ttm_prev)
    if rev_yoy is None:
        rev_a = _series(a_inc, "Total Revenue")
        if len(rev_a) >= 2:
            rev_yoy = _pct(rev_a[0][1], rev_a[1][1])
            quality.append("crecimiento interanual calculado con datos anuales (faltan trimestres)")

    gp_ttm = _ttm(_series(q_inc, "Gross Profit"))
    op_ttm = _ttm(_series(q_inc, "Operating Income", "Operating Income Loss"))
    ni_ttm = _ttm(_series(q_inc, "Net Income", "Net Income Common Stockholders"))
    if ni_ttm is None:
        ni_a = _series(a_inc, "Net Income", "Net Income Common Stockholders")
        ni_ttm = ni_a[0][1] if ni_a else None

    cfo_series = _series(q_cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
    cfo_ttm = _ttm(cfo_series)
    capex_series = _series(q_cf, "Capital Expenditure", "Capital Expenditures")
    capex_ttm = _ttm(capex_series)  # viene negativo
    sbc_ttm = _ttm(_series(q_cf, "Stock Based Compensation"))
    da_ttm = _ttm(_series(q_cf, "Depreciation And Amortization", "Depreciation Amortization",
                          "Depreciation Amortization Depletion"))
    ebitda_ttm = (op_ttm + da_ttm) if (op_ttm is not None and da_ttm is not None) else None

    fcf_series = _series(q_cf, "Free Cash Flow")
    if not fcf_series and cfo_series and capex_series:
        ocf = dict(cfo_series)
        capex = dict(capex_series)
        common = sorted(set(ocf) & set(capex), reverse=True)
        fcf_series = [(d, ocf[d] + capex[d]) for d in common]  # capex viene negativo
        if fcf_series:
            quality.append("FCF calculado como CFO - CapEx (partida directa no disponible)")
    fcf_ttm = _ttm(fcf_series)
    fcf_ttm_prev = _ttm(fcf_series, skip=4)
    fcf_yoy = _pct(fcf_ttm, fcf_ttm_prev)
    fcf_conv = (fcf_ttm / ni_ttm * 100.0) if (fcf_ttm is not None and ni_ttm not in (None, 0)) else None
    cfo_conv = (cfo_ttm / ni_ttm * 100.0) if (cfo_ttm is not None and ni_ttm not in (None, 0)) else None

    ar = _series(q_bal, "Accounts Receivable", "Receivables", "Net Receivables")
    ar_growth = _pct(ar[0][1], ar[4][1]) if len(ar) >= 5 else None
    inv = _series(q_bal, "Inventory")
    inv_growth = _pct(inv[0][1], inv[4][1]) if len(inv) >= 5 else None
    sh = _series(q_inc, "Diluted Average Shares", "Basic Average Shares")
    shares_yoy = _pct(sh[0][1], sh[4][1]) if len(sh) >= 5 else None

    cash = _series(q_bal, "Cash Cash Equivalents And Short Term Investments",
                   "Cash And Cash Equivalents")
    debt = _series(q_bal, "Total Debt")
    debt_total = debt[0][1] if debt else None
    net_cash = None
    if cash and debt:
        net_cash = cash[0][1] - debt[0][1]
    elif cash:
        net_cash = cash[0][1]

    fin_ccy = raw.get("financial_currency") or "USD"
    price_ccy = raw.get("price_currency") or "USD"
    fx = raw.get("fx_fin_to_price")
    if fin_ccy != price_ccy and fx is None:
        quality.append(f"sin tipo de cambio {fin_ccy}->{price_ccy}: el DCF por accion queda desactivado")

    # --- estimaciones consenso (Yahoo) ---
    est, rev_est = raw.get("earnings_estimate"), raw.get("revenue_estimate")
    eps_next = _est_row(est, "avg", "+1y")
    eps_next_low = _est_row(est, "low", "+1y")
    eps_next_high = _est_row(est, "high", "+1y")
    eps_n_analysts = _est_row(est, "numberOfAnalysts", "+1y")
    rev_growth_next = _growth_from_estimate(rev_est)
    pt = raw.get("price_targets") or {}

    # --- PER historico propio (no circular: multiplos del pasado del valor) ---
    pe_hist = None
    a_eps = _series(a_inc, "Diluted EPS", "Basic EPS")
    close_means = raw.get("annual_close_means") or {}
    # Si reporta en otra divisa (ASML EUR, TSM TWD), el BPA historico es por
    # accion ordinaria y el precio es del ADR: convierte con FX actual y ratio
    # ADR aproximado (ordinarias = NI/EPS anual; ratio = ordinarias / acciones Yahoo).
    fx_pe = None
    if fin_ccy != price_ccy:
        if fx:
            sh_out = (raw.get("info") or {}).get("sharesOutstanding")
            ni_a = _series(a_inc, "Net Income", "Net Income Common Stockholders")
            if sh_out and ni_a and a_eps and a_eps[0][1] and a_eps[0][1] > 0:
                ord_shares = ni_a[0][1] / a_eps[0][1]
                if ord_shares > 0:
                    fx_pe = fx * (ord_shares / sh_out)
                    quality.append("PER historico convertido con tipo de cambio actual y "
                                   "ratio ADR aproximado (NI/BPA entre acciones Yahoo): revisar a mano")
        if fx_pe is None:
            quality.append(f"sin conversion fiable {fin_ccy}->{price_ccy}: escenarios PER desactivados")
    pes = []
    for date_str, eps in a_eps:
        if eps is None or eps <= 0:
            continue
        if fin_ccy != price_ccy and fx_pe is None:
            continue
        year = date_str[:4]
        mean_close = close_means.get(year) or close_means.get(str(int(year) - 1))
        if mean_close:
            denom = eps * fx_pe if fx_pe else eps
            if denom > 0:
                pes.append(mean_close / denom)
    if len(pes) >= 2:
        pes_s = sorted(pes)
        pe_hist = {
            "median": statistics.median(pes_s),
            "p25": pes_s[max(0, len(pes_s) // 4)],
            "p75": pes_s[min(len(pes_s) - 1, (3 * len(pes_s)) // 4)],
            "n_years": len(pes_s),
        }
    elif eps_next:
        fwd = price / eps_next if (price and eps_next > 0) else None
        if fwd:
            pe_hist = {"median": fwd, "p25": fwd * 0.8, "p75": fwd * 1.2, "n_years": 0}
            quality.append("PER historico insuficiente: bandas ancladas al PER forward actual (0,8x/1x/1,2x)")

    per_scen = None
    pe_clamped = False
    if pe_hist and eps_next and eps_next > 0 and price:
        fwd_now = price / eps_next
        lo_pe, hi_pe = fwd_now / PE_BAND, fwd_now * PE_BAND
        def _cl(x):
            return max(lo_pe, min(hi_pe, x))
        pe_u = {k: _cl(pe_hist[k]) for k in ("p25", "median", "p75")}
        pe_clamped = any(abs(pe_u[k] - pe_hist[k]) > 1e-9 for k in pe_u)
        per_scen = {
            "adverse": round((eps_next_low or eps_next * 0.9) * pe_u["p25"], 2),
            "central": round(eps_next * pe_u["median"], 2),
            "favorable": round((eps_next_high or eps_next * 1.1) * pe_u["p75"], 2),
            "eps_used": {"low": eps_next_low, "avg": eps_next, "high": eps_next_high},
            "pe_used": {"p25": round(pe_u["p25"], 1), "median": round(pe_u["median"], 1),
                        "p75": round(pe_u["p75"], 1)},
            "pe_hist_raw_median": round(pe_hist["median"], 1),
            "pe_forward_now": round(fwd_now, 1),
            "clamped": pe_clamped,
        }
        if pe_clamped:
            quality.append(
                f"Multiplo PER acotado: mediana historica {pe_hist['median']:.1f}x frente a PER forward "
                f"actual {fwd_now:.1f}x; el motor limita el multiplo a {1/PE_BAND:.2f}-{PE_BAND:.1f} veces el forward "
                f"(gradual, sin saltos de metodo).")
    elif eps_next is not None and eps_next <= 0:
        quality.append("BPA estimado negativo: escenarios PER no aplicables")

    # --- DCF (margen FCF normalizado: TTM + ultimos ejercicios, con capex) ---
    a_cf = raw.get("a_cashflow")
    a_rev = dict(_series(a_inc, "Total Revenue"))
    a_fcf = dict(_series(a_cf, "Free Cash Flow"))
    if not a_fcf:
        _o = dict(_series(a_cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities"))
        _c = dict(_series(a_cf, "Capital Expenditure", "Capital Expenditures"))
        a_fcf = {d: _o[d] + _c[d] for d in _o if d in _c}
    margins = []
    for d in sorted(set(a_fcf) & set(a_rev), reverse=True)[:FCF_YEARS]:
        if a_rev[d]:
            margins.append(a_fcf[d] / a_rev[d])
    fcf_margin_ttm = (fcf_ttm / rev_ttm) if (fcf_ttm is not None and rev_ttm) else None
    if fcf_margin_ttm is not None:
        margins.append(fcf_margin_ttm)
    fcf_margin = (sum(margins) / len(margins)) if margins else None
    fcf_norm = (fcf_margin * rev_ttm) if (fcf_margin is not None and rev_ttm) else None
    if fcf_margin is not None:
        quality.append(f"Margen FCF normalizado {fcf_margin*100:.1f}% (media de {len(margins)} periodos: TTM + "
                       f"{len(margins)-1 if fcf_margin_ttm is not None else len(margins)} ejercicios, ya neto de capex); "
                       f"TTM solo: {('%.1f%%' % (fcf_margin_ttm*100)) if fcf_margin_ttm is not None else 'n/d'}")
    dcf_val = None
    if fin_ccy == price_ccy or fx:
        dcf_val = _dcf(fcf_norm, rev_ttm, rev_growth_next, net_cash, shares,
                       fx if fin_ccy != price_ccy else None, DCF_DISCOUNT, DCF_TERMINAL)
    elif shares:
        quality.append("DCF desactivado por falta de tipo de cambio")
    if fcf_norm is not None and fcf_norm <= 0:
        quality.append("Margen FCF normalizado <= 0 (capex absorbe la caja): el DCF solo valora la caja neta, sin flujos futuros")

    sens = []
    if dcf_val is not None:
        for r in DCF_DISCOUNT_GRID:
            row = []
            for tg in DCF_TERMINAL_GRID:
                v = _dcf(fcf_norm, rev_ttm, rev_growth_next, net_cash, shares,
                         fx if fin_ccy != price_ccy else None, r, tg)
                row.append(round(v, 2) if v else None)
            sens.append(row)

    # Mezcla unica para las 15 empresas: 60% PER (multiplo acotado) + 40% DCF
    # (margen FCF normalizado). Si falta una pata por datos, se dice en data_quality.
    blend = None
    if per_scen and dcf_val is not None:
        target = BLEND_W_PER * per_scen["central"] + BLEND_W_DCF * dcf_val
        blend = {
            "target": round(target, 2),
            "upside_pct": round((target / price - 1) * 100, 1) if price else None,
            "weights": f"{int(BLEND_W_PER*100)}/{int(BLEND_W_DCF*100)}",
        }
    elif dcf_val is not None:
        blend = {"target": round(dcf_val, 2),
                 "upside_pct": round((dcf_val / price - 1) * 100, 1) if price else None,
                 "weights": "solo DCF (falta la pata PER por datos)"}
    elif per_scen:
        blend = {"target": per_scen["central"],
                 "upside_pct": round((per_scen["central"] / price - 1) * 100, 1) if price else None,
                 "weights": "solo PER (falta la pata DCF por datos)"}

    # Lectura individual: cada informe explica que tratamiento recibio y si sus dos patas
    # son coherentes entre si (no se compara con otras empresas).
    if blend and per_scen and dcf_val is not None and price:
        gap = per_scen["central"] / dcf_val if dcf_val > 0 else None
        if gap is None or gap > 2.0 or gap < 0.5:
            quality.append(
                f"Patas en desacuerdo: PER {per_scen['central']:.0f} vs DCF {dcf_val:.0f}"
                f"{'' if gap is None else f' (x{gap:.1f})'}. El objetivo mezcla dos lecturas muy distintas: "
                "confianza baja; mirar el rango entre ambas, no el punto.")
    capex_cfo = (abs(capex_ttm) / cfo_ttm) if (capex_ttm is not None and cfo_ttm and cfo_ttm > 0) else None
    if capex_cfo is not None and capex_cfo >= 0.6:
        quality.append(
            f"Empresa en ciclo de inversion: el capex absorbe el {capex_cfo*100:.0f}% de la caja operativa. "
            "El DCF usa el margen FCF normalizado (neto de capex) y no premia la inversion hasta que "
            "aparezca en ventas o margen; su resultado es conservador por construccion.")

    # --- senales de alerta mecanicas (umbrales visibles; senales, no acusaciones) ---
    flags = []
    if cfo_conv is not None and cfo_conv < 70:
        flags.append({"level": "warn",
                      "text": f"La caja operativa solo convierte el {cfo_conv:.0f}% del beneficio neto: revisar circulante y reconocimiento de ingresos. Senal clasica de cuentas maquilladas; aqui puede ser crecimiento de cobros."})
    if fcf_conv is not None and fcf_conv < 60:
        flags.append({"level": "warn",
                      "text": f"Conversion de caja baja: el FCF TTM es el {fcf_conv:.0f}% del beneficio neto."})
    if fcf_yoy is not None and fcf_yoy < -25:
        flags.append({"level": "warn",
                      "text": f"El FCF TTM cae un {abs(fcf_yoy):.0f}% interanual."})
    if ar_growth is not None and rev_yoy is not None and ar_growth > rev_yoy + 10:
        flags.append({"level": "warn",
                      "text": f"Las cuentas por cobrar crecen ({ar_growth:+.0f}%) mas que las ventas ({rev_yoy:+.0f}%): revisar plazos de cobro y calidad del crecimiento."})
    if inv_growth is not None and rev_yoy is not None and inv_growth > rev_yoy + 10:
        flags.append({"level": "warn",
                      "text": f"El inventario crece ({inv_growth:+.0f}%) mas que las ventas ({rev_yoy:+.0f}%): riesgo de obsolescencia o de demanda frenandose."})
    if debt_total and ebitda_ttm and ebitda_ttm > 0 and debt_total / ebitda_ttm > 3:
        flags.append({"level": "warn",
                      "text": f"Deuda elevada: {debt_total / ebitda_ttm:.1f}x EBITDA TTM."})
    if capex_ttm is not None and capex_ttm < 0 and rev_ttm:
        capex_int = abs(capex_ttm) / rev_ttm * 100.0
        capex_prev = _ttm(capex_series, skip=4)
        capex_yoy = _pct(abs(capex_ttm), abs(capex_prev)) if capex_prev else None
        if capex_int > 25 and (capex_yoy or 0) > (rev_yoy or 0) + 10:
            flags.append({"level": "warn",
                          "text": f"Capex muy intenso ({capex_int:.0f}% de ventas) y creciendo mas que los ingresos ({capex_yoy:+.0f}% vs {rev_yoy:+.0f}%): vigilar retorno de esa inversion."})
        if cfo_ttm and abs(capex_ttm) > cfo_ttm:
            flags.append({"level": "warn",
                          "text": "El capex supera a la caja operativa: la inversion se financia con deuda, caja o emision."})
    if shares_yoy is not None and shares_yoy > 3:
        flags.append({"level": "info",
                      "text": f"Dilucion: las acciones en circulacion crecen un {shares_yoy:+.1f}% interanual."})
    if sbc_ttm is not None and ni_ttm not in (None, 0) and ni_ttm > 0 and sbc_ttm / ni_ttm > 0.25:
        flags.append({"level": "info",
                      "text": f"Pago en acciones alto: la SBC TTM equivale al {sbc_ttm / ni_ttm * 100:.0f}% del beneficio neto."})
    if pe_hist and eps_next and price and eps_next > 0:
        fwd_pe = price / eps_next
        if pe_hist["n_years"] >= 2 and fwd_pe > pe_hist["median"] * 1.3:
            flags.append({"level": "info",
                          "text": f"Multiplo exigido: PER forward {fwd_pe:.1f}x vs mediana historica {pe_hist['median']:.1f}x."})
    pt_mean = pt.get("mean") if isinstance(pt, dict) else None
    if pt_mean and price and pt_mean < price:
        flags.append({"level": "info",
                      "text": f"El objetivo medio de analistas ({pt_mean:.2f}) esta por debajo del precio actual."})
    if rev_yoy is not None and rev_yoy < 0:
        flags.append({"level": "warn", "text": f"Ventas TTM en caida ({rev_yoy:+.0f}% interanual)."})

    def _m(x):
        return round(x / 1e6, 1) if x is not None else None  # a millones

    return {
        "ticker": raw["ticker"],
        "name": info.get("longName") or info.get("shortName") or raw["ticker"],
        "generated_at": raw.get("fetched_at"),
        "sector_note": "Plantilla calibrada para tecnologia y semiconductores de gran capitalizacion.",
        "price": {"value": price, "currency": price_ccy,
                  "as_of": (raw.get("fetched_at") or "")[:10]},
        "market_cap_m": _m(mcap),
        "week52": {"low": info.get("fiftyTwoWeekLow"), "high": info.get("fiftyTwoWeekHigh")},
        "fundamentals": {
            "currency": fin_ccy,
            "revenue_ttm_m": _m(rev_ttm),
            "revenue_yoy_pct": round(rev_yoy, 1) if rev_yoy is not None else None,
            "gross_margin_pct": round(gp_ttm / rev_ttm * 100, 1) if (gp_ttm and rev_ttm) else None,
            "op_margin_pct": round(op_ttm / rev_ttm * 100, 1) if (op_ttm and rev_ttm) else None,
            "net_margin_pct": round(ni_ttm / rev_ttm * 100, 1) if (ni_ttm and rev_ttm) else None,
            "cfo_ttm_m": _m(cfo_ttm),
            "capex_ttm_m": _m(abs(capex_ttm)) if capex_ttm is not None else None,
            "fcf_ttm_m": _m(fcf_ttm),
            "fcf_yoy_pct": round(fcf_yoy, 1) if fcf_yoy is not None else None,
            "fcf_conversion_pct": round(fcf_conv, 1) if fcf_conv is not None else None,
            "cfo_conversion_pct": round(cfo_conv, 1) if cfo_conv is not None else None,
            "receivables_growth_pct": round(ar_growth, 1) if ar_growth is not None else None,
            "inventory_growth_pct": round(inv_growth, 1) if inv_growth is not None else None,
            "debt_m": _m(debt_total),
            "debt_to_ebitda": (round(debt_total / ebitda_ttm, 1)
                               if (debt_total and ebitda_ttm and ebitda_ttm > 0) else None),
            "sbc_ttm_m": _m(sbc_ttm),
            "shares_yoy_pct": round(shares_yoy, 1) if shares_yoy is not None else None,
            "net_cash_m": _m(net_cash),
        },
        "estimates": {
            "eps_next_fy": {"avg": eps_next, "low": eps_next_low, "high": eps_next_high,
                            "analysts": eps_n_analysts},
            "revenue_growth_next_pct": (round(rev_growth_next, 1)
                                        if rev_growth_next is not None else None),
            "analyst_target": {k: pt.get(k) for k in ("low", "mean", "median", "high")}
                              if isinstance(pt, dict) else None,
        },
        "valuation": {
            "pe_hist": pe_hist,
            "per_scenarios": per_scen,
            "dcf": {"value": round(dcf_val, 2) if dcf_val else None, "params": {
                "discount": DCF_DISCOUNT, "terminal": DCF_TERMINAL, "years": DCF_YEARS,
                "fcf_margin_pct": (round(fcf_margin * 100, 1) if fcf_margin else None),
                "rev_growth_next_pct": (round(rev_growth_next, 1)
                                        if rev_growth_next is not None else None),
                "net_cash_m": _m(net_cash)}},
            "dcf_sensitivity": {"discounts": DCF_DISCOUNT_GRID, "terminals": DCF_TERMINAL_GRID,
                                "grid": sens} if sens else None,
            "blend": blend,
            "method": ("Punto de partida 60% PER + 40% DCF; cada informe indica abajo que ajustes recibio y si sus patas concuerdan. "
                       "PER: BPA consenso proximo ejercicio x multiplos historicos propios "
                       "(p25/mediana/p75), acotados a 1/1,5-1,5 veces el PER forward actual "
                       "(gradual, sin cortes: un multiplo historico de hipercrecimiento no puede "
                       "dar mas de un 50% de re-rating). DCF deliberadamente conservador: margen FCF "
                       "normalizado (media de TTM y ultimos 3 ejercicios, neto de capex, asi que el "
                       "gasto en inversion cuesta nota), consenso de ventas ano 1 limitado a "
                       "[-20%, +40%], desvanecimiento lineal a perpetuidad en 5 anos, descuento 9,5%, "
                       "terminal 4%; el DCF queda a 0 de flujos si el margen normalizado es <= 0. "
                       "Objetivo a valor de hoy, sin dividendos."),
        },
        "flags": flags,
        "limits": LIMITS,
        "data_quality": quality,
        "sources": ["Yahoo Finance via yfinance (precios, estados, estimaciones y consenso)",
                    "Tipo de cambio Yahoo Finance cuando la divisa de reporte difiere de la de cotizacion"],
    }
