"""Builds the designed HTML report pages (used by bot.py)."""
import html
import math
from datetime import timedelta

CSS = """
:root{--paper:#F2F4F1;--card:#FFFFFF;--ink:#14212C;--muted:#5E6B74;--line:#D8DEDA;--up:#15805A;--down:#C0412E;--warn:#C98410;
 --band:#2E6FA8;--band15:rgba(46,111,168,.10);--band10:rgba(46,111,168,.22);--ma20:#8A6FB8;--ma50:#B89B5E;
 box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#10181F;--card:#17222C;--ink:#E3EAEF;--muted:#94A3AE;--line:#2A3743;--up:#3DBB88;--down:#EE6E5A;--warn:#E7A93A;--band:#6FA8DC;--band15:rgba(111,168,220,.12);--band10:rgba(111,168,220,.26);--ma20:#B7A0E0;--ma50:#D8BE83;color-scheme:dark}}
:root[data-theme="dark"]{--paper:#10181F;--card:#17222C;--ink:#E3EAEF;--muted:#94A3AE;--line:#2A3743;--up:#3DBB88;--down:#EE6E5A;--warn:#E7A93A;--band:#6FA8DC;--band15:rgba(111,168,220,.12);--band10:rgba(111,168,220,.26);--ma20:#B7A0E0;--ma50:#D8BE83;color-scheme:dark}
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
body{margin:0;background:var(--paper);color:var(--ink);font-family:Manrope,system-ui,-apple-system,"Segoe UI",sans-serif;font-size:15.5px;line-height:1.6;font-variant-numeric:tabular-nums}
.wrap{max-width:760px;margin:0 auto;padding:22px 16px 60px}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:13.5px}
.top b{color:var(--ink);font-weight:700}
.hero{margin:18px 0 8px}
.px{font-size:clamp(46px,14vw,76px);font-weight:800;letter-spacing:-.03em;line-height:1}
.chg{font-size:20px;font-weight:700;margin-top:6px}
.flat{color:var(--muted)}.upc{color:var(--up)}.dnc{color:var(--down)}
.verdict{margin:14px 0 0;font-size:17px;max-width:36em}
.rbar{margin:22px 0 6px;position:relative;height:44px}
.rtrack{position:absolute;left:0;right:0;top:18px;height:8px;border-radius:4px;background:var(--line)}
.rday{position:absolute;top:14px;height:16px;border-radius:4px;background:var(--ink)}
.rtick{position:absolute;top:8px;width:2px;height:28px;background:var(--muted)}
.rcap{display:flex;justify-content:space-between;font-size:12.5px;color:var(--muted)}
section{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 18px 16px;margin-top:14px}
h2{font-size:13px;font-weight:700;color:var(--muted);margin:0 0 10px;letter-spacing:.01em}
h3{font-size:19px;margin:0 0 8px;line-height:1.35}
p{margin:0 0 10px}
.chart svg{width:100%;height:auto;display:block}
.grid{stroke:var(--line);stroke-width:.6}
.ax{fill:var(--muted);font-size:10px;font-family:inherit}
.c15{fill:var(--band15)}.c10{fill:var(--band10)}
.px{}
path.px{fill:none;stroke:var(--ink);stroke-width:1.8;stroke-linejoin:round}
.ma20{fill:none;stroke:var(--ma20);stroke-width:1.2}
.ma50{fill:none;stroke:var(--ma50);stroke-width:1.2;stroke-dasharray:4 3}
.lvR{stroke:var(--down);stroke-width:.9;stroke-dasharray:2 3}.lvS{stroke:var(--up);stroke-width:.9;stroke-dasharray:2 3}
.lvt{font-size:9.5px;font-weight:800;paint-order:stroke;stroke:var(--card);stroke-width:3px;stroke-linejoin:round}.lvRt{fill:var(--down)}.lvSt{fill:var(--up)}
.exp{stroke:var(--band);stroke-width:1.2}
.dot{fill:var(--ink);stroke:var(--card);stroke-width:2}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12.5px;color:var(--muted);margin-top:8px}
.legend i{display:inline-block;width:14px;height:8px;border-radius:2px;margin-right:5px;vertical-align:1px}
.ladder{display:grid;grid-template-columns:48px 1fr auto;gap:0;font-size:15px}
.ladder div{padding:8px 0;border-top:1px solid var(--line)}
.ladder div:nth-child(-n+3){border-top:0}
.tag{font-weight:800;font-size:12px;padding-right:14px;min-width:44px;align-self:center}
.R{color:var(--down)}.S{color:var(--up)}.N{color:var(--ink)}
.lv{text-align:right;font-weight:700}
.now div{background:color-mix(in srgb,var(--ink) 7%,transparent)}
.vol{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.stat{border:1px solid var(--line);border-radius:12px;padding:10px 12px}
.stat .k{font-size:12.5px;color:var(--muted)}.stat .v{font-size:22px;font-weight:800;line-height:1.2}
.stat .s{font-size:12.5px}
.term svg{width:100%;height:auto;display:block;margin-top:4px}
.tbl{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14.5px;}
th,td{text-align:right;padding:9px 6px;border-top:1px solid var(--line);vertical-align:top}
thead th{border-top:0;font-size:12px;color:var(--muted);font-weight:600}
tbody th{text-align:left;font-weight:700}
td span,th span{display:block;font-size:12px;color:var(--muted);font-weight:500}
ul.pts{margin:0;padding-left:1.1em}ul.pts li{margin:6px 0}
.risk{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 12px}
.pill{border-radius:999px;padding:4px 12px;font-size:13px;font-weight:700;border:1.5px solid currentColor}
.cal li{list-style:none;padding:8px 0;border-top:1px solid var(--line)}.cal{margin:0;padding:0}.cal li:first-child{border-top:0}
.cal b{display:inline-block;min-width:58px}
.call{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;text-align:center}
.call .v{font-size:19px}
.gauge{height:10px;border-radius:5px;background:linear-gradient(90deg,var(--down),var(--line) 50%,var(--up));position:relative;margin:16px 4px 6px}
.gauge b{position:absolute;top:-5px;width:4px;height:20px;border-radius:2px;background:var(--ink)}
.gcap{display:flex;justify-content:space-between;font-size:12px;color:var(--muted)}
footer{color:var(--muted);font-size:12.5px;margin-top:22px}
@media (max-width:420px){.vol{grid-template-columns:1fr 1fr}.call{grid-template-columns:1fr 1fr 1fr}}

.evt{border-left:4px solid var(--warn);padding:2px 0 2px 12px;margin:10px 0}
.evt.quiet{border-color:var(--line)}
.evt b{display:block}
.arch a{display:flex;justify-content:space-between;padding:10px 0;border-top:1px solid var(--line);text-decoration:none}
.arch a:first-child{border-top:0}
"""

e = html.escape


def fmt(v, d=2):
    return f"{v:,.{d}f}"


def chart_svg(s, levels):
    """Price, 20/50-day averages, key levels and the expected-move cone."""
    dates, close, ma20, ma50 = s["hist_dates"], s["hist_close"], s["hist_ma20"], s["hist_ma50"]
    last, C = s["anchor_date"], s["price"]
    exps = s["expiries"]
    end = exps[-1] if exps else last + timedelta(days=45)

    def iv(dte):
        if dte <= 30 or s["vix3m"] != s["vix3m"]:
            return s["vix"]
        return s["vix"] + (s["vix3m"] - s["vix"]) * min(dte - 30, 63) / 63

    cone = [(last + timedelta(days=k), C * iv(max(k, 1)) / 100 * math.sqrt(k / 365))
            for k in range((end - last).days + 1)]
    lo = min(min(close), C - 1.5 * cone[-1][1])
    hi = max(max(close), C + 1.5 * cone[-1][1])
    for lv in levels:
        lo, hi = min(lo, lv["level"]), max(hi, lv["level"])
    pad = (hi - lo) * 0.04
    lo, hi = lo - pad, hi + pad
    W, H, ml, mr, mt, mb = 340, 250, 6, 42, 12, 26
    X = lambda t: ml + (t - dates[0]).days / max((end - dates[0]).days, 1) * (W - ml - mr)
    Y = lambda v: mt + (hi - v) / (hi - lo) * (H - mt - mb)
    step = next(x for x in (50, 100, 200, 250, 500, 1000) if (hi - lo) / x <= 7)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="SPX price with key levels and expected-move cone">']
    v = math.ceil(lo / step) * step
    while v < hi:
        out.append(f'<line x1="{ml}" x2="{W-mr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="grid"/>'
                   f'<text x="{W-mr+4}" y="{Y(v)+3.5:.1f}" class="ax">{v:,.0f}</text>')
        v += step
    for m in (1.5, 1.0):
        up = [f"{X(t):.1f},{Y(C+m*sd):.1f}" for t, sd in cone]
        dn = [f"{X(t):.1f},{Y(C-m*sd):.1f}" for t, sd in reversed(cone)]
        out.append(f'<polygon points="{" ".join(up + dn)}" class="{"c15" if m > 1 else "c10"}"/>')
    shown = [lv for lv in levels if lv["tag"] in ("R1", "R2", "S1", "S2")]
    for lv in shown:
        cls = "lvR" if lv["tag"].startswith("R") else "lvS"
        out.append(f'<line x1="{X(dates[0]):.1f}" x2="{X(last):.1f}" y1="{Y(lv["level"]):.1f}" '
                   f'y2="{Y(lv["level"]):.1f}" class="{cls}"/>')

    def path(ys):
        return "M" + " L".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in zip(dates, ys) if b == b)

    out.append(f'<path d="{path(ma50)}" class="ma50"/><path d="{path(ma20)}" class="ma20"/>'
               f'<path d="{path(close)}" class="px"/>')
    used = []
    for lv in sorted(shown, key=lambda l: -l["level"]):
        y = Y(lv["level"]) - 3
        if any(abs(y - u) < 11 for u in used):
            continue
        used.append(y)
        cls = "lvRt" if lv["tag"].startswith("R") else "lvSt"
        out.append(f'<text x="{X(dates[0]) + 2:.1f}" y="{y:.1f}" class="lvt {cls}">'
                   f'{e(lv["tag"])} {lv["level"]:,.0f}</text>')
    for ex in exps:
        dte = (ex - last).days
        sd = C * iv(dte) / 100 * math.sqrt(dte / 365)
        out.append(f'<line x1="{X(ex):.1f}" x2="{X(ex):.1f}" y1="{Y(C + 1.5 * sd):.1f}" '
                   f'y2="{Y(C - 1.5 * sd):.1f}" class="exp"/>'
                   f'<text x="{X(ex):.1f}" y="{H - 14}" class="ax" text-anchor="middle">{ex.day}</text>')
    if exps:
        mid = (X(exps[0]) + X(exps[-1])) / 2
        out.append(f'<text x="{mid:.1f}" y="{H - 2}" class="ax" text-anchor="middle">'
                   f'{" · ".join(x.strftime("%b %-d") for x in exps)}</text>')
    m = (dates[0].replace(day=28) + timedelta(days=4)).replace(day=1)
    while m <= last:
        out.append(f'<text x="{X(m):.1f}" y="{H - 14}" class="ax" text-anchor="middle">{m:%b}</text>')
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    out.append(f'<circle cx="{X(last):.1f}" cy="{Y(C):.1f}" r="3.5" class="dot"/></svg>')
    return "".join(out)


def term_svg(v9, v30, v3m):
    if any(v != v for v in (v9, v30, v3m)):
        return ""
    lo, hi = min(v9, v30, v3m) - 1, max(v9, v30, v3m) + 1
    Y = lambda v: 70 - (v - lo) / (hi - lo) * 54
    xs = (40, 170, 300)
    col = "var(--band)" if v9 < v30 < v3m else "var(--warn)" if v9 < v3m else "var(--down)"
    pts = " ".join(f"{x},{Y(v):.1f}" for x, v in zip(xs, (v9, v30, v3m)))
    out = [f'<svg viewBox="0 0 340 96" role="img" aria-label="VIX term structure {v9:.2f}, {v30:.2f}, {v3m:.2f}">',
           '<line x1="30" x2="320" y1="80" y2="80" stroke="var(--line)"/>',
           f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>']
    for x, v, lab in zip(xs, (v9, v30, v3m), ("9-day", "30-day", "3-month")):
        out.append(f'<circle cx="{x}" cy="{Y(v):.1f}" r="4" fill="{col}"/>'
                   f'<text x="{x}" y="{Y(v) - 9:.1f}" text-anchor="middle" font-size="11" font-weight="700" fill="var(--ink)">{v:.2f}</text>'
                   f'<text x="{x}" y="94" text-anchor="middle" font-size="10" fill="var(--muted)">{lab}</text>')
    out.append("</svg>")
    return "".join(out)


def stat(k, v, s="", cls=""):
    return f'<div class="stat"><div class="k">{e(k)}</div><div class="v">{v}</div><div class="s {cls}">{s}</div></div>'


def chg_cls(x, good_when_down=False):
    if x != x or abs(x) < 1e-9:
        return "flat"
    if good_when_down:
        return "dnc" if x > 0 else "upc"
    return "upc" if x > 0 else "dnc"


def render(kind, now, s, ai, nd):
    """kind: 'morning' or 'preclose'. s: numbers from bot.spx_stats. ai: Claude's JSON."""
    morning = kind == "morning"
    title = f"SPX {'Pre-market' if morning else 'Report'} · {now:%a %b %-d, %Y}"
    stamp = f"{now:%a %b %-d, %Y} · {'6:21 AM PT' if morning else '12:30 PM PT'}"
    P = s["price"]
    label = "pre-market report" if morning else "report · 30 min to close"
    parts = [f'<div class="top"><span><b>SPX</b> {label}</span><span>{stamp}</span></div>']

    if morning:
        one = s["em"][0]
        parts.append(
            '<header class="hero"><div class="top" style="margin-bottom:6px"><span>Expected move today</span></div>'
            f'<div class="px">±{one["sd"]:.0f}<span style="font-size:.4em;font-weight:700;letter-spacing:0"> pts</span></div>'
            f'<div class="chg flat">{one["sd"] / P * 100:.2f}% · range {one["lo"]:,.0f} – {one["hi"]:,.0f}</div>'
            f'<p class="verdict">{e(ai.get("headline", ""))}</p></header>')
    else:
        ch, pc = P - s["prev"], (P / s["prev"] - 1) * 100
        arrow = "▲" if ch > 0 else "▼" if ch < 0 else "■"
        lo_, hi_ = min(s["low"], s["prev"]) - 20, max(s["high"], s["prev"]) + 20
        pos = lambda v: (v - lo_) / (hi_ - lo_) * 100
        parts.append(
            f'<header class="hero"><div class="px">{fmt(P)}</div>'
            f'<div class="chg {chg_cls(ch)}">{arrow} {ch:+,.2f} ({"0.00" if abs(pc) < 0.005 else f"{pc:+.2f}"}%)</div>'
            f'<p class="verdict">{e(ai.get("headline", ""))}</p></header>'
            '<div class="rbar" aria-label="Today\'s range"><div class="rtrack"></div>'
            f'<div class="rday" style="left:{pos(s["low"]):.1f}%;width:{max(pos(s["high"]) - pos(s["low"]), 1):.1f}%"></div>'
            f'<div class="rtick" style="left:{pos(s["prev"]):.1f}%" title="Prior close"></div></div>'
            f'<div class="rcap"><span>L {fmt(s["low"])}</span><span>Range {s["high"] - s["low"]:.0f} pts · avg {s["atr"]:.0f}</span>'
            f'<span>H {fmt(s["high"])}</span></div>')

    ev = ai.get("events") or []
    if ev:
        head = "⚠️ Today's events" if morning else f"📅 Heads-up for {nd:%A}"
        items = "".join(f'<div class="evt{"" if x.get("important") else " quiet"}"><b>{e(str(x.get("title", "")))}</b>'
                        f'{e(str(x.get("detail", "")))}</div>' for x in ev)
        parts.append(f'<section><h2>{head}</h2>{items}</section>')

    drv = "".join(f"<li>{e(str(x))}</li>" for x in (ai.get("drivers") or []))
    if morning:
        cards = "".join(stat(k, v, sub, c) for k, v, sub, c in s.get("overnight", []))
        parts.append(f'<section><h2>Overnight</h2><div class="vol">{cards}</div>'
                     + (f'<ul class="pts" style="margin-top:12px">{drv}</ul>' if drv else "") + '</section>')
    elif drv:
        parts.append(f'<section><h2>Why it moved</h2><ul class="pts">{drv}</ul></section>')

    levels = []
    for l in ai.get("levels") or []:
        try:
            levels.append({"tag": str(l["tag"]).upper(), "label": str(l.get("label", "")), "level": float(l["level"])})
        except (KeyError, TypeError, ValueError):
            pass
    parts.append(
        f'<section class="chart"><h2>Price and the condor cone</h2><h3>{e(ai.get("chart_title", ""))}</h3>'
        f'{chart_svg(s, levels)}'
        '<div class="legend"><span><i style="background:var(--ink)"></i>SPX</span><span><i style="background:var(--ma20)"></i>20-day</span>'
        '<span><i style="background:var(--ma50)"></i>50-day</span><span><i style="background:var(--band10)"></i>1σ</span>'
        '<span><i style="background:var(--band15);outline:1px solid var(--band10)"></i>1.5σ</span></div></section>')

    if levels:
        res = sorted([l for l in levels if l["tag"].startswith("R")], key=lambda l: -l["level"])
        sup = sorted([l for l in levels if l["tag"].startswith("S")], key=lambda l: -l["level"])
        row = lambda l, c: (f'<div class="tag {c}">{e(l["tag"])}</div><div>{e(l["label"])}</div>'
                            f'<div class="lv">{l["level"]:,.0f}</div>')
        nt, nl = ("PREV", "Prior close") if morning else ("NOW", "SPX now")
        parts.append('<section><h2>Key levels</h2>'
                     f'<div class="ladder">{"".join(row(l, "R") for l in res)}</div>'
                     f'<div class="ladder now"><div class="tag N">{nt}</div><div>{nl}</div><div class="lv">{fmt(P)}</div></div>'
                     f'<div class="ladder">{"".join(row(l, "S") for l in sup)}</div>'
                     f'<p style="margin-top:10px;font-size:14.5px">{e(ai.get("level_note", ""))}</p></section>')

    vol = s["vol"]
    g = lambda k: vol.get(k, (float("nan"), float("nan")))
    vix, skew, vvix = g("VIX"), g("SKEW"), g("VVIX")
    prem = vix[0] - s["rv20"]
    cards = (stat("VIX", f"{vix[0]:.2f}", f"{vix[1]:+.2f}", chg_cls(vix[1], True))
             + stat("Realized 20d", f"{s['rv20']:.1f}%", f"IV premium {prem:+.1f}", "upc" if prem > 0 else "dnc")
             + stat("SKEW", f"{skew[0]:.1f}", f"{skew[1]:+.1f}" + (" · elevated" if skew[0] > 140 else ""),
                    "dnc" if skew[0] > 140 else "")
             + stat("VVIX", f"{vvix[0]:.1f}", "subdued" if vvix[0] < 90 else "normal" if vvix[0] < 110 else "high",
                    "dnc" if vvix[0] >= 110 else ""))
    parts.append(f'<section><h2>Volatility</h2><div class="vol">{cards}</div><div class="term">'
                 f'{term_svg(g("VIX9D")[0], vix[0], g("VIX3M")[0])}</div>'
                 f'<p style="font-size:14.5px;margin-top:6px">{e(ai.get("vol_note", ""))}</p></section>')

    rows = ""
    for r in s["em"]:
        extra = f'<span>1.5σ {r["lo15"]:,.0f} – {r["hi15"]:,.0f}</span>' if r.get("lo15") else ""
        rows += (f'<tr><th scope="row">{e(r["label"])}<span>{e(r["sub"])}</span></th>'
                 f'<td>±{r["sd"]:.0f}<span>{r["sd"] / P * 100:.2f}%</span></td>'
                 f'<td>{r["lo"]:,.0f} – {r["hi"]:,.0f}{extra}</td></tr>')
    parts.append(f'<section><h2>Expected moves from {P:,.0f}</h2><div class="tbl"><table>'
                 '<thead><tr><th style="text-align:left">Expiry</th><th>1σ</th><th>Range</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div>'
                 '<p style="font-size:13px;color:var(--muted);margin-top:8px">From the VIX term structure, symmetric. '
                 'Put skew puts real 16-delta puts further below and calls closer.</p></section>')

    tone = {"bad": "var(--down)", "warn": "var(--warn)", "good": "var(--up)"}
    tags = "".join(f'<span class="pill" style="color:{tone.get(t.get("tone"), "var(--muted)")}">{e(str(t.get("text", "")))}</span>'
                   for t in (ai.get("ic_tags") or []) if isinstance(t, dict))
    pts = "".join(f"<li>{e(str(x))}</li>" for x in (ai.get("ic_points") or []))
    parts.append(f'<section><h2>Iron condor read</h2><div class="risk">{tags}</div><ul class="pts">{pts}</ul></section>')

    c = ai.get("call") or {}
    try:
        gauge = max(-100, min(100, int(float(c.get("gauge", 0)))))
        conf = int(float(c.get("confidence", 0)))
    except (TypeError, ValueError):
        gauge, conf = 0, 0
    spike = str(c.get("spike_risk", "—"))
    scol = "var(--down)" if "High" in spike else "var(--warn)" if "Med" in spike else "var(--up)"
    who = "today" if morning else f"{nd:%A}"
    dirn = f"Direction: {e(str(c.get('direction')))}. " if c.get("direction") else ""
    parts.append(f'<section><h2>Call for {who}</h2><div class="call">'
                 f'{stat("Sentiment", e(str(c.get("sentiment", "—"))))}{stat("Confidence", f"{conf}%")}'
                 f'<div class="stat"><div class="k">Spike / crash</div><div class="v" style="color:{scol}">{e(spike)}</div></div></div>'
                 f'<div class="gauge" aria-label="Sentiment gauge"><b style="left:{50 + gauge / 2:.0f}%"></b></div>'
                 '<div class="gcap"><span>Bearish</span><span>Neutral</span><span>Bullish</span></div>'
                 f'<p style="margin-top:12px;font-size:14.5px">{dirn}{e(str(c.get("reason", "")))}</p></section>')

    parts.append('<footer>Data from Yahoo Finance (may be delayed). Commentary written by Claude. '
                 'Expected moves are estimates. Not financial advice. · <a href="../index.html">All reports</a></footer>')
    return page(title, "".join(parts))


def page(title, body):
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{e(title)}</title>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
            f'<style>{CSS}</style></head><body><div class="wrap">{body}</div></body></html>')


def render_index(files):
    """files: list of (filename, label), newest first."""
    links = "".join(f'<a href="reports/{e(f)}"><span>{e(l)}</span><span>›</span></a>' for f, l in files)
    body = (f'<div class="top"><span><b>SPX</b> reports</span><span>{len(files)} reports</span></div>'
            '<header class="hero"><div class="px" style="font-size:44px">SPX reports</div></header>'
            f'<section class="arch">{links or "No reports yet."}</section>')
    return page("SPX reports", body)
