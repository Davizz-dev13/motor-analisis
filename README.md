# Motor de análisis de tecnológicas


Documento mecánico por ticker: mismas secciones, mismo orden, cada cifra con
fuente y fecha. Lo que el motor no puede verificar sale marcado; la capa de
criterio (cruzar el 10-Q, juzgar riesgos) sigue haciéndose a mano.

## Estructura

- `scripts/analysis_core.py` — el motor. Dos mitades: `fetch_raw(ticker)`
  (descarga de Yahoo, tolerante a fallos por partida) y `compute_report(raw)`
  (matemática pura: fundamentales TTM, señales de alerta, escenarios PER con
  múltiplos históricos propios, DCF con sensibilidad y mezcla 60/40).
- `scripts/generate_analysis.py` — genera `docs/analisis/index.html` (página
  con selector de ticker y botón Descargar PDF) y `docs/analisis/data/<T>.json`.
- `scripts/demo_fixture.py` — empresa ficticia DEMO para probar sin red:
  `python scripts/generate_analysis.py --demo` escribe `/tmp/demo-analisis.html`.
- `docs/analisis/index.html` — la página (los JSON de datos los genera la
  Action cada noche; no van en este paquete).
- `.github/workflows/analysis.yml` — Action nocturna propia que regenera los
  informes y los commitea (`docs/analisis/`).

## Cómo se ejecuta

- Cada noche laborable sola (21:30 UTC) con la Action "Motor de analisis".
- Un ticker suelto bajo demanda: pestaña Actions → "Motor de analisis" → Run
  workflow → campo `ticker` (p. ej. `ARM`, aunque no esté en el universo).
- En local: `pip install yfinance pandas numpy` y
  `python scripts/generate_analysis.py`.

## Parámetros (arriba de analysis_core.py)

Descuento DCF 9,5%, perpetuidad 4%, 5 años, mezcla 60% PER / 40% DCF,
universo UNIVERSE (15 tecnológicas/semis; editar la lista para añadir o quitar).

## Límites

- Datos Yahoo gratis: estimaciones y consenso son los de Yahoo; ASML y TSM
  reportan en 20-F/6-K y en EUR/TWD (conversión a USD a tipo actual, ADR
  aproximado vía capitalización).
- No cruza el 10-Q: concentración de clientes, garantías y partidas puntuales
  se miran a mano. Las señales de alerta son sospechas con cifra, no pruebas.
- Análisis mecánico con fines informativos; no es asesoramiento regulado.

## Nota sobre la página

`docs/analisis/index.html` se sirve con GitHub Pages (Source: `/docs`) cuando
el repo sea público; en privado se puede abrir en local. La página es solo la
carcasa: los informes (`docs/analisis/data/<TICKER>.json`) los genera la
Action.
