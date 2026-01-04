from __future__ import annotations
from html import escape

def _pct(x: float) -> str:
    return f"{x*100:.1f}%"

def build_daily_csv(result: dict) -> bytes:
    c = result.get("instrument_meta", {})
    contrib = result.get("contributions", {})
    macro_reasons = result.get("macro_reasons", [])
    flags = "; ".join(macro_reasons[:8]) if macro_reasons else ""

    headers = [
        "date","symbol","exchange","market_type","direction","prob_up","confidence","regime","regime_confidence",
        "score_raw","gate","perf_mult","score_final","macro_risk_level",
        "funding_rate","open_interest","oi_change_pct",
        "rsi","adx","macd_hist","vwap","vwap_std","close",
        "poc","vah","val","in_value",
        "raw_technical","raw_orderflow","raw_profile","raw_vwap",
        "contrib_technical","contrib_orderflow","contrib_profile","contrib_vwap",
        "macro_reasons"
    ]
    row = [
        result.get("date",""), result.get("symbol",""), c.get("exchange",""), c.get("market_type",""),
        result.get("direction",""), result.get("prob_up",""), result.get("confidence",""),
        result.get("regime",""), result.get("regime_confidence",""),
        result.get("ensemble_score_raw",""), result.get("macro_gate_multiplier",""),
        result.get("performance_multiplier",""), result.get("ensemble_score_final",""),
        result.get("macro_risk_level",""),
        result.get("funding_rate",""), result.get("open_interest",""), result.get("oi_change_pct",""),
        result.get("rsi",""), result.get("adx",""), result.get("macd_hist",""),
        result.get("rth_vwap",""), result.get("rth_vwap_std",""), result.get("rth_close",""),
        result.get("poc",""), result.get("vah",""), result.get("val",""), result.get("in_value",""),
        result.get("technical_bias",""), result.get("orderflow_bias",""), result.get("auction_bias",""), result.get("vwap_bias",""),
        contrib.get("technical",""), contrib.get("orderflow",""), contrib.get("auction",""), contrib.get("vwap",""),
        flags
    ]

    def esc(v):
        s = "" if v is None else str(v)
        if any(ch in s for ch in [",", '"', "\n"]):
            s = '"' + s.replace('"', '""') + '"'
        return s

    return (",".join(headers) + "\n" + ",".join(esc(x) for x in row) + "\n").encode("utf-8")

def format_daily_email_html(result: dict):
    sym = result["symbol"]
    prob_up = float(result["prob_up"])
    conf = result.get("confidence","")
    regime = result.get("regime","MIXED")
    direction = result.get("direction","")
    date = result.get("date","")
    c = result.get("instrument_meta", {})
    contrib = result.get("contributions", {})
    macro_reasons = result.get("macro_reasons", [])

    subject = f"[Daily Crypto Forecast] {sym} — {regime} — {conf} CONFIDENCE — P(UP)={_pct(prob_up)}"

    # Plain text audit
    text = []
    text.append(subject)
    text.append("")
    text.append("INSTRUMENT")
    text.append(f"Exchange: {c.get('exchange','')}  Market: {c.get('market_type','')}")
    text.append(f"Description: {c.get('description','')}")
    text.append("")
    text.append("REGIME")
    text.append(f"{regime} (conf={result.get('regime_confidence','')}) weights={result.get('regime_weights',{})}")
    text.append("")
    text.append("SIGNALS (raw -> contribution)")
    text.append(f"Technical {result.get('technical_bias','')} -> {contrib.get('technical','')}")
    text.append(f"Orderflow {result.get('orderflow_bias','')} -> {contrib.get('orderflow','')}")
    text.append(f"Profile {result.get('auction_bias','')} -> {contrib.get('auction','')}")
    text.append(f"VWAP {result.get('vwap_bias','')} -> {contrib.get('vwap','')}")
    text.append("")
    text.append("RISK GATE")
    text.append(f"Level={result.get('macro_risk_level','')} gate={result.get('macro_gate_multiplier','')} score={result.get('macro_risk_score','')}")
    for r in macro_reasons[:8]:
        text.append(f"- {r}")
    text.append("")
    text.append("FINAL")
    text.append(f"score_final={result.get('ensemble_score_final','')} P(up)={_pct(prob_up)} dir={direction} conf={conf}")
    text_body = "\n".join(text)

    def H(x): return escape("" if x is None else str(x))

    style = '''
    <style>
      body{font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.35}
      .k{color:#555}
      .box{border:1px solid #ddd;border-radius:10px;padding:12px;margin:10px 0}
      .title{font-size:16px;font-weight:700}
      table{border-collapse:collapse;width:100%}
      td,th{border:1px solid #ddd;padding:8px;vertical-align:top}
      th{text-align:left;background:#f6f6f6}
      summary{cursor:pointer;font-weight:700}
      .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:12px}
      .muted{color:#666}
    </style>
    '''

    def block(title, inner):
        return f"<details open><summary>{H(title)}</summary><div class='box'>{inner}</div></details>"

    instrument_html = f'''
    <div class='title'>Instrument & Data Context</div>
    <div><span class='k'>Symbol:</span> {H(sym)}</div>
    <div><span class='k'>Exchange / Market:</span> {H(c.get('exchange',''))} / {H(c.get('market_type',''))}</div>
    <div><span class='k'>Description:</span> {H(c.get('description',''))}</div>
    <div class='muted mono'>UTC rolling windows. Daily={H(result.get('daily_lookback_days',''))}d | Intraday={H(result.get('intraday_lookback_hours',''))}h @ {H(result.get('timeframe',''))}</div>
    '''

    regime_html = f'''
    <div class='title'>Regime</div>
    <div><span class='k'>Regime:</span> {H(regime)} <span class='muted'>(conf={H(result.get('regime_confidence',''))})</span></div>
    <div><span class='k'>ADX:</span> {H(result.get('adx',''))} &nbsp; <span class='k'>VWAP z:</span> {H(result.get('vwap_z',''))} &nbsp; <span class='k'>Vol pct:</span> {H(result.get('vol_pct',''))}</div>
    <div><span class='k'>Weights:</span> <span class='mono'>{H(result.get('regime_weights',{}))}</span></div>
    '''

    signals_html = f'''
    <div class='title'>Signals</div>
    <table>
      <tr><th>Agent</th><th>Raw</th><th>Contribution</th><th>Evidence</th></tr>
      <tr><td>Technical</td><td class='mono'>{H(result.get('technical_bias',''))}</td><td class='mono'>{H(contrib.get('technical',''))}</td>
          <td class='mono'>RSI={H(result.get('rsi',''))} | MACD_hist={H(result.get('macd_hist',''))} | ADX={H(result.get('adx',''))}</td></tr>
      <tr><td>Orderflow</td><td class='mono'>{H(result.get('orderflow_bias',''))}</td><td class='mono'>{H(contrib.get('orderflow',''))}</td>
          <td class='mono'>Funding={H(result.get('funding_rate',''))} | OI={H(result.get('open_interest',''))} | OIΔ={H(result.get('oi_change_pct',''))}%</td></tr>
      <tr><td>Profile</td><td class='mono'>{H(result.get('auction_bias',''))}</td><td class='mono'>{H(contrib.get('auction',''))}</td>
          <td class='mono'>POC={H(result.get('poc',''))} VAH={H(result.get('vah',''))} VAL={H(result.get('val',''))} in_value={H(result.get('in_value',''))}</td></tr>
      <tr><td>VWAP</td><td class='mono'>{H(result.get('vwap_bias',''))}</td><td class='mono'>{H(contrib.get('vwap',''))}</td>
          <td class='mono'>VWAP={H(result.get('rth_vwap',''))} σ={H(result.get('rth_vwap_std',''))} close={H(result.get('rth_close',''))}</td></tr>
    </table>
    '''

    gating_html = f'''
    <div class='title'>Crypto Risk Gating</div>
    <div><span class='k'>Risk Level:</span> {H(result.get('macro_risk_level',''))} &nbsp; <span class='k'>Gate:</span> <span class='mono'>{H(result.get('macro_gate_multiplier',''))}</span></div>
    <div class='muted'>Reasons:</div>
    <ul>{''.join([f"<li class='mono'>{H(r)}</li>" for r in macro_reasons[:8]]) or "<li class='muted'>None</li>"}</ul>
    '''

    final_html = f'''
    <div class='title'>Final</div>
    <div><span class='k'>Score raw:</span> <span class='mono'>{H(result.get('ensemble_score_raw',''))}</span></div>
    <div><span class='k'>After gate:</span> <span class='mono'>{H(result.get('ensemble_score_gated',''))}</span></div>
    <div><span class='k'>Perf mult:</span> <span class='mono'>{H(result.get('performance_multiplier',''))}</span></div>
    <div><span class='k'>Score final:</span> <span class='mono'>{H(result.get('ensemble_score_final',''))}</span></div>
    <div><span class='k'>P(UP):</span> {H(_pct(prob_up))} &nbsp; <span class='k'>Direction:</span> {H(direction)} &nbsp; <span class='k'>Confidence:</span> {H(conf)}</div>
    <div class='muted mono'>P(up) = 1 / (1 + e^(−score_final))</div>
    '''

    disclaimer = '''
    <div class='box muted'>
      Probabilistic forecast only. Not trading advice. Crypto trades 24/7; this model evaluates rolling UTC windows and gates conviction on funding/OI extremes.
    </div>
    '''

    html_body = f'''
    <html><head>{style}</head><body>
      <div class='box'>
        <div class='title'>{H(subject)}</div>
        <div class='muted'>Date: {H(date)}</div>
      </div>
      {block("1) Instrument & Data Context", instrument_html)}
      {block("2) Regime", regime_html)}
      {block("3) Signals", signals_html)}
      {block("4) Crypto Risk Gating", gating_html)}
      {block("5) Final", final_html)}
      {disclaimer}
    </body></html>
    '''
    return subject, text_body, html_body
