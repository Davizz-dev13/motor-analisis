#!/usr/bin/env python3
"""Genera la pagina del motor de analisis de tecnologicas.

Modo normal (GitHub Action): recorre el UNIVERSE, descarga Yahoo y escribe
  docs/analisis/index.html          (indice con el formato fijo de documento)
  docs/analisis/data/<TICKER>.json  (un informe por valor, mismo esquema siempre)

Modo --demo: sin red, usa el fixture sintetico y escribe un HTML autonomo
  /tmp/demo-analisis.html           (para verificar formato sin publicar nada)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analysis_core as ac

# ---------------------------------------------------------------------------
# Plantilla fija del documento (la misma en cada ticker, siempre)
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Motor de an&aacute;lisis &middot; tecnol&oacute;gicas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bungee&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&display=swap" rel="stylesheet">
<style>
  :root { --bg:#f4ecd8; --panel:#faf5e7; --border:#d8cdb2; --fg:#2a170f; --mut:#7a6a58; --acc:#d96b2a; --green:#2e7d50; --red:#d9402f; --amber:#c98a12; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg); font-family:'DM Sans',-apple-system,Segoe UI,Roboto,sans-serif; }
  header { padding:24px 28px 8px; max-width:900px; margin:0 auto; }
  h1 { margin:0 0 4px; font-size:22px; font-family:'Bungee',sans-serif; font-weight:400; letter-spacing:.02em; }
  .sub { color:var(--mut); font-size:13px; line-height:1.5; }
  main { padding:8px 28px 40px; max-width:900px; margin:0 auto; }
  .tickrow { display:flex; gap:6px; flex-wrap:wrap; margin:12px 0 4px; }
  .tickrow button { font-size:12px; font-weight:700; padding:5px 11px; border:2px solid var(--fg); background:var(--panel); color:var(--fg); cursor:pointer; font-family:'DM Sans',sans-serif; }
  .tickrow button.on { background:var(--acc); color:var(--panel); border-color:var(--acc); }
  .doc { background:var(--panel); border:3px solid var(--fg); padding:22px 24px; margin-top:14px; }
  .doc h2 { font-family:'Bungee',sans-serif; font-weight:400; font-size:14px; letter-spacing:.03em; margin:26px 0 8px; padding-top:18px; border-top:2px solid var(--border); }
  .doc h2:first-of-type { border-top:none; padding-top:0; margin-top:0; }
  .doctitle { margin:0 0 2px; font-size:26px; font-family:'Bungee',sans-serif; font-weight:400; }
  .docsub { color:var(--mut); font-size:12.5px; margin-bottom:6px; }
  table { border-collapse:collapse; width:100%; font-size:13px; margin-top:4px; }
  th, td { padding:6px 9px; text-align:right; border-bottom:2px solid var(--border); }
  th { background:var(--fg); color:var(--bg); font-family:'Bungee',sans-serif; font-weight:400; font-size:10px; letter-spacing:.03em; }
  th:first-child, td:first-child { text-align:left; }
  .pos { color:var(--green); } .neg { color:var(--red); }
  .kpis { display:flex; gap:22px; flex-wrap:wrap; margin:10px 0 2px; }
  .kpi { font-size:12px; color:var(--mut); }
  .kpi b { display:block; font-size:22px; color:var(--fg); font-family:'Bungee',sans-serif; font-weight:400; }
  .flag { font-size:13.5px; line-height:1.5; padding:7px 10px; border-left:4px solid var(--amber); background:var(--bg); margin:6px 0; }
  .flag.warn { border-color:var(--red); }
  .flag.info { border-color:var(--acc); }
  .flag .tag { font-size:10px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--mut); display:block; }
  .note { font-size:12px; color:var(--mut); line-height:1.55; }
  ul.tight { margin:6px 0; padding-left:18px; font-size:13px; line-height:1.6; }
  .dlbtn { display:inline-block; margin-top:14px; font-size:13px; font-weight:700; padding:9px 18px; border:3px solid var(--fg); background:var(--acc); color:var(--panel); cursor:pointer; font-family:'Bungee',sans-serif; }
  footer { color:var(--mut); font-size:11.5px; padding:20px 28px 40px; max-width:900px; margin:0 auto; line-height:1.6; }
  .warn-demo { border:3px solid var(--red); color:var(--red); font-weight:700; padding:10px 14px; margin-top:12px; font-size:13px; }
  @media print {
    body { background:#fff; }
    header .tickrow, .dlbtn, .noprint { display:none !important; }
    .doc { border:none; padding:0; }
    main { padding:0; }
  }
</style>
</head>
<body>
<header>
  <div class="sub" style="margin-bottom:6px"><a href="../">&larr; Sharpe Lab</a></div>
  <h1>Motor de an&aacute;lisis &middot; tecnol&oacute;gicas</h1>
  <div class="sub">Documento mec&aacute;nico por ticker: mismas secciones, mismo orden, cada cifra con fuente y fecha. Lo que el motor no puede verificar sale marcado. No cruza el 10-Q: la capa de criterio se hace a mano.</div>
  <div class="tickrow" id="tickrow"></div>
  <div class="warn-demo" id="demobanner" style="display:none">DEMO: datos sint&eacute;ticos para verificar el formato. Ninguna cifra es real.</div>
</header>
<main>
  <div class="doc" id="doc"><div class="note">Elige un ticker.</div></div>
  <button class="dlbtn noprint" id="dl" style="display:none" onclick="window.print()">Descargar PDF</button>
</main>
<footer id="foot"></footer>
<script>
/*__EMBEDDED__*/
const fmtM = v => v==null ? '-' : Number(v).toLocaleString('es-ES',{maximumFractionDigits:0}) + ' M';
const fmtN = (v,d=2) => v==null ? '-' : Number(v).toLocaleString('es-ES',{minimumFractionDigits:d,maximumFractionDigits:d});
const fmtPct = v => v==null ? '-' : (v>0?'+':'') + Number(v).toLocaleString('es-ES',{maximumFractionDigits:1}) + '%';
const fmtPct0 = v => v==null ? '-' : Number(v).toLocaleString('es-ES',{maximumFractionDigits:1}) + '%';
const cls = v => v==null ? '' : (v>=0?'pos':'neg');
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');

function row(k, v, c) { return `<tr><td>${k}</td><td class="${c||''}">${v}</td></tr>`; }
function rowN(cells) { return '<tr>' + cells.map((v,i)=>`<td>${v==null?'-':v}</td>`).join('') + '</tr>'; }

function render(d) {
  const f = d.fundamentals, e = d.estimates, v = d.valuation, p = d.price;
  const cur = p.currency || '';
  const fcy = f.currency || '';
  const fxNote = (fcy && cur && fcy !== cur)
    ? `<div class="note">Estados en ${esc(fcy)}, precio en ${esc(cur)}: conversi&oacute;n a tipo actual. Emisor extranjero: reporta en 20-F/6-K, no en 10-Q.</div>` : '';
  let h = '';
  h += `<div class="doctitle">${esc(d.ticker)}</div>`;
  h += `<div class="docsub">${esc(d.name)}<br>Generado ${esc((d.generated_at||'').slice(0,10))} &middot; motor mec&aacute;nico Sharpe Lab &middot; ${esc(d.sector_note||'')}</div>`;
  h += `<div class="kpis">
    <div class="kpi">Precio (${esc(cur)})<b>${fmtN(p.value)}</b></div>
    <div class="kpi">Capitalizaci&oacute;n<b>${fmtM(d.market_cap_m)} ${esc(cur)}</b></div>
    <div class="kpi">Rango 52 semanas<b style="font-size:15px">${fmtN(d.week52 && d.week52.low)} - ${fmtN(d.week52 && d.week52.high)}</b></div>
  </div>`;

  // 1. Objetivo mecanico
  h += `<h2>1 &middot; Objetivo mec&aacute;nico</h2>`;
  const b = v.blend, at = e.analyst_target || {};
  h += `<div class="kpis">
    <div class="kpi">Objetivo del motor (${esc(cur)})<b>${fmtN(b && b.target)}</b></div>
    <div class="kpi">vs precio<b class="${b&&b.upside_pct!=null?(b.upside_pct>=0?'pos':'neg'):''}">${fmtPct(b && b.upside_pct)}</b></div>
    <div class="kpi">Mezcla<b style="font-size:15px">${esc(b ? b.weights : '-')}</b></div>
    <div class="kpi">Consenso analistas (media)<b>${fmtN(at.mean)}</b></div>
  </div>`;
  h += `<div class="note">Objetivo a valor de hoy, sin dividendos. El consenso de analistas se muestra solo como referencia; no entra en la mezcla.</div>`;

  // 2. Fundamentales
  h += `<h2>2 &middot; Fundamentales TTM (${esc(fcy)})</h2>`;
  h += `<table><thead><tr><th>M&eacute;trica</th><th>Valor</th></tr></thead><tbody>`;
  h += row('Ventas TTM', fmtM(f.revenue_ttm_m));
  h += row('Crecimiento interanual', fmtPct(f.revenue_yoy_pct), cls(f.revenue_yoy_pct));
  h += row('M&aacute;rgen bruto / operativo / neto',
    `${fmtPct0(f.gross_margin_pct)} / ${fmtPct0(f.op_margin_pct)} / ${fmtPct0(f.net_margin_pct)}`);
  h += row('Caja operativa TTM', fmtM(f.cfo_ttm_m));
  h += row('Capex TTM', fmtM(f.capex_ttm_m));
  h += row('FCF TTM', fmtM(f.fcf_ttm_m));
  h += row('FCF interanual', fmtPct(f.fcf_yoy_pct), cls(f.fcf_yoy_pct));
  h += row('Conversi&oacute;n FCF / beneficio', fmtPct0(f.fcf_conversion_pct));
  h += row('Conversi&oacute;n CFO / beneficio', fmtPct0(f.cfo_conversion_pct));
  h += row('Cuentas por cobrar interanual', fmtPct(f.receivables_growth_pct), cls(f.receivables_growth_pct));
  h += row('Inventario interanual', fmtPct(f.inventory_growth_pct), cls(f.inventory_growth_pct));
  h += row('Deuda total', fmtM(f.debt_m));
  h += row('Deuda / EBITDA TTM', f.debt_to_ebitda==null?'-':fmtN(f.debt_to_ebitda,1)+'x');
  h += row('Pago en acciones (SBC) TTM', fmtM(f.sbc_ttm_m));
  h += row('Acciones en circulaci&oacute;n interanual', fmtPct(f.shares_yoy_pct), cls(f.shares_yoy_pct==null?null:-f.shares_yoy_pct));
  h += row('Caja neta', fmtM(f.net_cash_m));
  h += `</tbody></table>${fxNote}`;

  // 3. Senales de alerta
  h += `<h2>3 &middot; Se&ntilde;ales de alerta</h2>`;
  if (d.flags && d.flags.length) {
    for (const fl of d.flags) {
      const tag = fl.level === 'warn' ? 'Revisar a mano' : 'A tener en cuenta';
      h += `<div class="flag ${esc(fl.level)}"><span class="tag">${tag} &middot; sospecha mec&aacute;nica, no acusaci&oacute;n</span>${esc(fl.text)}</div>`;
    }
  } else {
    h += `<div class="note">Sin se&ntilde;ales mec&aacute;nicas en las cuentas publicadas. Que el motor no marque nada no significa que las cuentas est&eacute;n limpias: el fraude bien hecho no sale en estos agregados.</div>`;
  }

  // 4. Valoracion
  h += `<h2>4 &middot; Valoraci&oacute;n</h2>`;
  const ps = v.per_scenarios, pe = v.pe_hist;
  h += `<table><thead><tr><th>Escenarios PER</th><th>Adverso</th><th>Central</th><th>Favorable</th></tr></thead><tbody>`;
  h += rowN(['Objetivo', ps?fmtN(ps.adverse):'-', ps?fmtN(ps.central):'-', ps?fmtN(ps.favorable):'-']);
  if (ps) h += rowN(['BPA usado', fmtN(ps.eps_used.low), fmtN(ps.eps_used.avg), fmtN(ps.eps_used.high)]);
  if (ps) h += rowN(['PER usado', ps.pe_used.p25+'x', ps.pe_used.median+'x', ps.pe_used.p75+'x']);
  h += `</tbody></table>`;
  if (ps && ps.reliable === false) h += `<div class="flag warn"><span class="tag">PER no fiable &middot; excluido de la mezcla</span>El PER hist&oacute;rico (mediana ${fmtN(pe && pe.median, 1)}x) supera 2,5x el PER forward actual: en hipercrecimiento los PER pasados capturan la infravaloraci&oacute;n anterior y no son un ancla razonable. El objetivo mec&aacute;nico usa solo DCF.</div>`;
  if (pe) h += `<div class="note">PER hist&oacute;rico propio (${pe.n_years||0} a&ntilde;os): mediana ${fmtN(pe.median,1)}x, p25 ${fmtN(pe.p25,1)}x, p75 ${fmtN(pe.p75,1)}x.${pe.n_years===0?' Sin historia suficiente: bandas ancladas al PER forward actual (0,8x/1x/1,2x).':''}</div>`;
  const dc = v.dcf;
  h += `<table style="margin-top:10px"><thead><tr><th>DCF</th><th>Valor</th></tr></thead><tbody>`;
  h += row('Valor por acci&oacute;n', dc.value==null?'-':fmtN(dc.value));
  h += row('Supuestos', dc.value==null?'-':`descuento ${dc.params.discount*100}%, perpetuidad ${dc.params.terminal*100}%, ${dc.params.years} a&ntilde;os, margen FCF ${fmtPct0(dc.params.fcf_margin_pct)}, crecimiento ventas a&ntilde;o 1 ${fmtPct0(dc.params.rev_growth_next_pct)}`);
  h += `</tbody></table>`;
  if (v.dcf_sensitivity) {
    const s = v.dcf_sensitivity;
    h += `<table style="margin-top:10px"><thead><tr><th>Sensibilidad DCF</th>${s.terminals.map(t=>`<th>perp. ${t*100}%</th>`).join('')}</tr></thead><tbody>`;
    s.grid.forEach((r,i)=>{ h += `<tr><td>desc. ${s.discounts[i]*100}%</td>${r.map(x=>`<td>${x==null?'-':fmtN(x)}</td>`).join('')}</tr>`; });
    h += `</tbody></table>`;
  }
  h += `<div class="note" style="margin-top:8px">${esc(v.method)}</div>`;

  // 5. Consenso
  h += `<h2>5 &middot; Consenso (Yahoo)</h2>`;
  const ef = e.eps_next_fy || {};
  h += `<table><thead><tr><th>M&eacute;trica</th><th>Valor</th></tr></thead><tbody>`;
  h += row('BPA pr&oacute;ximo ejercicio (bajo / medio / alto)', `${fmtN(ef.low)} / ${fmtN(ef.avg)} / ${fmtN(ef.high)}`);
  h += row('Analistas', ef.analysts==null?'-':String(ef.analysts));
  h += row('Crecimiento de ventas esperado a&ntilde;o 1', fmtPct(e.revenue_growth_next_pct));
  h += row('Objetivos analistas (bajo / medio / mediana / alto)', `${fmtN(at.low)} / ${fmtN(at.mean)} / ${fmtN(at.median)} / ${fmtN(at.high)}`);
  h += `</tbody></table>`;

  // 6. Lo que el motor no mira
  h += `<h2>6 &middot; Lo que el motor no mira</h2><ul class="tight">`;
  for (const l of (d.limits||[])) h += `<li>${esc(l)}</li>`;
  h += `</ul>`;
  if (d.data_quality && d.data_quality.length) {
    h += `<div class="note">Notas de calidad de datos: ${d.data_quality.map(esc).join(' &middot; ')}</div>`;
  }
  h += `<div class="note" style="margin-top:10px">Fuentes: ${(d.sources||[]).map(esc).join(' &middot; ')}. Generado ${esc(d.generated_at||'')}.</div>`;
  h += `<div class="note"><b>An&aacute;lisis mec&aacute;nico con fines informativos; no es asesoramiento financiero regulado.</b></div>`;
  return h;
}

function show(t) {
  document.querySelectorAll('#tickrow button').forEach(b=>b.classList.toggle('on', b.dataset.t===t));
  const done = d => {
    document.getElementById('doc').innerHTML = render(d);
    document.getElementById('dl').style.display = 'inline-block';
    document.getElementById('foot').textContent = 'Analisis mecanico con fines informativos; no es asesoramiento financiero regulado.';
  };
  if (typeof EMBEDDED !== 'undefined' && EMBEDDED[t]) { done(EMBEDDED[t]); return; }
  fetch('data/'+t+'.json').then(r=>{ if(!r.ok) throw 0; return r.json(); }).then(done)
    .catch(()=>{ document.getElementById('doc').innerHTML = '<div class="note">Sin informe para '+esc(t)+'. Se genera cada noche; si falta, p&iacute;delo por chat.</div>'; });
}

(function init(){
  const row = document.getElementById('tickrow');
  let tickers = [];
  if (typeof EMBEDDED !== 'undefined') {
    tickers = Object.keys(EMBEDDED);
    document.getElementById('demobanner').style.display = 'block';
  } else {
    tickers = __TICKERS__;
  }
  for (const t of tickers) {
    const b = document.createElement('button');
    b.textContent = t; b.dataset.t = t; b.onclick = ()=>show(t);
    row.appendChild(b);
  }
  if (tickers.length) show(tickers[0]);
})();
</script>
</body>
</html>
"""


def build_report(ticker: str) -> dict:
    raw = ac.fetch_raw(ticker)
    return ac.compute_report(raw)


def main() -> None:
    if "--demo" in sys.argv:
        import demo_fixture
        report = ac.compute_report(demo_fixture.build_raw())
        html = PAGE.replace("/*__EMBEDDED__*/",
                            "const EMBEDDED = " + json.dumps({"DEMO": report}) + ";")
        html = html.replace("__TICKERS__", '["DEMO"]')
        out = Path("/tmp/demo-analisis.html")
        out.write_text(html, encoding="utf-8")
        Path("/tmp/demo-analisis.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"demo escrito en {out}")
        return

    out_dir = ROOT / "docs" / "analisis"
    (out_dir / "data").mkdir(parents=True, exist_ok=True)
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].upper().strip()
    tickers = [only] if only else list(ac.UNIVERSE)
    for ticker in tickers:
        try:
            report = build_report(ticker)
        except Exception as e:  # noqa: BLE001 - un ticker roto no para la noche
            print(f"[{ticker}] ERROR: {type(e).__name__}: {e}")
            continue
        (out_dir / "data" / f"{ticker}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
        print(f"[{ticker}] ok")
    # La portada lista el universo configurado mas cualquier ticker con informe
    # ya generado (p.ej. anadidos bajo demanda via workflow_dispatch).
    known = sorted({*ac.UNIVERSE,
                    *(p.stem for p in (out_dir / "data").glob("*.json"))})
    html = PAGE.replace("/*__EMBEDDED__*/", "")
    html = html.replace("__TICKERS__", json.dumps(known))
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"pagina: {out_dir}/index.html")


if __name__ == "__main__":
    main()
