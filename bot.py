"""SPX WhatsApp bot (SPX + iron-condor focus).

  python bot.py update     -> SPX price / change every 30 min, 9:30-16:00 ET
  python bot.py morning    -> pre-market report, sent ~9:21 ET (6:21 AM PT)
  python bot.py preclose   -> market report 30 min before close, 15:30 ET (12:30 PM PT)

Secrets: WHATSAPP_PHONE, CALLMEBOT_APIKEY, ANTHROPIC_API_KEY.
FORCE_SEND=1 ignores the time window and sends right away (testing).
DRY_RUN=1 prints instead of sending.
"""
import os
import sys
import time
from datetime import date, datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

import holidays
import numpy as np
import requests
import yfinance as yf

# ---- Settings you may want to change -------------------------------------
LANGUAGE = "English"           # e.g. "Simplified Chinese" for 中文报告
MODEL = "claude-sonnet-5"      # Claude model used for the reports
MORNING_SEND = (9, 21)         # ET  (= 6:21 AM Pacific)
PRECLOSE_SEND = (15, 30)       # ET  (= 12:30 PM Pacific)
# --------------------------------------------------------------------------

ET = ZoneInfo("America/New_York")
FORCE = os.environ.get("FORCE_SEND") == "1"
DRY = os.environ.get("DRY_RUN") == "1"


# ---------- sending ----------
def split_message(text, limit=1400):
    """Split on blank lines, never inside a ``` monospace block."""
    chunks, buf = [], ""
    for para in text.split("\n\n"):
        cand = f"{buf}\n\n{para}" if buf else para
        if len(cand) > limit and buf and buf.count("```") % 2 == 0:
            chunks.append(buf)
            buf = para
        else:
            buf = cand
    if buf:
        chunks.append(buf)
    return [c.strip() for c in chunks if c.strip()]


def send(text):
    """Send to WhatsApp via CallMeBot, split into parts if long."""
    parts = split_message(text)
    if not parts:
        raise RuntimeError("Nothing to send (empty message).")
    print(f"---- message ({len(text)} chars, {len(parts)} part(s)) ----\n{text}\n----")
    for i, part in enumerate(parts):
        if DRY:
            continue
        if i:
            time.sleep(10)
        r = requests.get(
            "https://api.callmebot.com/whatsapp.php",
            params={"phone": os.environ["WHATSAPP_PHONE"],
                    "apikey": os.environ["CALLMEBOT_APIKEY"], "text": part},
            timeout=60,
        )
        reply = " ".join(r.text.split())[:300]
        print(f"CallMeBot part {i + 1}: HTTP {r.status_code}: {reply}")
        bad = ("error", "invalid", "blocked", "too long", "not allowed")
        ok = "queued" in reply.lower() or "sent" in reply.lower()
        if r.status_code != 200 or (not ok and any(w in reply.lower() for w in bad)):
            raise RuntimeError(f"CallMeBot did not accept part {i + 1}: {reply}")
    print("Sent.")


# ---------- time helpers ----------
def now_et():
    return datetime.now(ET)


def trading_day(d):
    return d.weekday() < 5 and d not in holidays.NYSE(years=d.year)


def in_window(now, start, end):
    return dtime(*start) <= now.time() < dtime(*end)


def wait_until(hm):
    """Sleep until hh:mm ET today (reports are written early, sent on time)."""
    if FORCE:
        return
    target = now_et().replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
    secs = (target - now_et()).total_seconds()
    if secs > 0:
        print(f"Report ready, waiting {secs / 60:.1f} min to send at {hm[0]}:{hm[1]:02d} ET")
        time.sleep(secs)


def next_trading_day(d):
    d += timedelta(days=1)
    while not trading_day(d):
        d += timedelta(days=1)
    return d


# ---------- market data ----------
def history(sym, period="5d"):
    for i in range(3):
        try:
            h = yf.Ticker(sym).history(period=period, interval="1d").dropna(subset=["Close"])
            if len(h) >= 2:
                return h
        except Exception:
            pass
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"No data for {sym}")


def last_and_prev(sym):
    c = history(sym)["Close"]
    return float(c.iloc[-1]), float(c.iloc[-2])


def pct_line(name, sym):
    try:
        last, prev = last_and_prev(sym)
        return f"- {name}: {last:,.2f} ({(last - prev) / prev * 100:+.2f}%)"
    except Exception:
        return f"- {name}: unavailable"


def ic_expirations(today, lo=28, hi=46):
    """Fridays 28-46 days out (standard 30-45 DTE iron condor window)."""
    out, d = [], today + timedelta(days=lo)
    while (d - today).days <= hi:
        if d.weekday() == 4:
            out.append(d)
        d += timedelta(days=1)
    return out


def spx_stats(now, session):
    """Deterministic SPX numbers. session='pre' (before open) or 'live'."""
    h = history("^GSPC", "1y")
    today_row = h.index[-1].date() == now.date()
    if session == "pre" and today_row:
        h = h.iloc[:-1]
    c = h["Close"]
    price = float(c.iloc[-1])
    if session == "live":
        try:
            live = float(yf.Ticker("^GSPC").fast_info["lastPrice"])
            price = live if live > 0 else price
        except Exception:
            pass
    live_today = session == "live" and today_row
    prev = float(c.iloc[-2]) if live_today else float(c.iloc[-1])
    closes = c.iloc[:-1] if live_today else c
    r = np.log(closes).diff().dropna()
    rv = {n: r.tail(n).std() * np.sqrt(252) * 100 for n in (5, 10, 20)}
    ma = {n: float(closes.tail(n).mean()) for n in (20, 50, 100, 200)}
    rng = (h["High"] - h["Low"]).tail(14).mean()

    vol = {}
    for s in ["^VIX9D", "^VIX", "^VIX3M", "^VVIX", "^SKEW"]:
        try:
            vol[s] = last_and_prev(s)
        except Exception:
            vol[s] = (float("nan"), float("nan"))
    vix, vix3m = vol["^VIX"][0], vol["^VIX3M"][0]

    def iv_for(dte):
        if dte <= 30 or np.isnan(vix3m):
            return vix
        return vix + (vix3m - vix) * min(dte - 30, 63) / 63

    lines = []
    if session == "live":
        o, hi_, lo_ = h.iloc[-1][["Open", "High", "Low"]]
        lines.append(f"SPX now {price:,.2f}, {price - prev:+,.2f} ({(price / prev - 1) * 100:+.2f}%) "
                     f"vs prior close {prev:,.2f}. Today open {o:,.2f}, high {hi_:,.2f}, "
                     f"low {lo_:,.2f}, range {hi_ - lo_:.0f} pts vs 14-day avg range {rng:.0f}.")
    else:
        lines.append(f"SPX prior close {price:,.2f} ({(price / float(c.iloc[-2]) - 1) * 100:+.2f}% that day). "
                     f"14-day avg daily range {rng:.0f} pts.")
    lines.append("Moving averages: " + ", ".join(
        f"{n}d {v:,.0f} ({(price / v - 1) * 100:+.1f}%)" for n, v in ma.items()))
    lines.append(f"52-week high {h['High'].max():,.1f} on {h['High'].idxmax():%b %d}. "
                 f"20-day high {h['High'].tail(20).max():,.1f}, 20-day low "
                 f"{h['Low'].tail(20).min():,.1f} on {h['Low'].tail(20).idxmin():%b %d}. "
                 f"5-day change {price - float(closes.iloc[-6]):+,.0f} pts.")
    lines.append("Last 5 sessions (O/H/L/C): " + "; ".join(
        f"{i:%m-%d} {rw.Open:,.0f}/{rw.High:,.0f}/{rw.Low:,.0f}/{rw.Close:,.0f}"
        for i, rw in h.tail(5).iterrows()))
    lines.append("Vol: " + ", ".join(
        f"{k.strip('^')} {v[0]:.2f} ({v[0] - v[1]:+.2f})" for k, v in vol.items()))
    lines.append(f"Realized vol: 5d {rv[5]:.1f}%, 10d {rv[10]:.1f}%, 20d {rv[20]:.1f}% "
                 f"(VIX minus RV20 = {vix - rv[20]:+.1f} pts).")

    em = []
    nd = now.date() if session == "pre" else next_trading_day(now.date())
    one = price * vix / 100 / np.sqrt(252)
    em.append(f"{'Today' if session == 'pre' else 'Next session ' + nd.strftime('%a %b %d')}: "
              f"±{one:.0f} pts ({one / price * 100:.2f}%), {price - one:,.0f}–{price + one:,.0f}")
    for ex in ic_expirations(now.date()):
        dte = (ex - now.date()).days
        s = price * iv_for(dte) / 100 * np.sqrt(dte / 365)
        em.append(f"{ex:%b %d} ({dte} DTE): 1σ ±{s:.0f} ({price - s:,.0f}–{price + s:,.0f}), "
                  f"1.5σ {price - 1.5 * s:,.0f}–{price + 1.5 * s:,.0f}")
    lines.append("Expected moves (from VIX term structure, symmetric):\n  " + "\n  ".join(em))
    return "\n".join(lines)


HIGH_IMPACT = """FOMC decisions / statements / minutes, Powell and other Fed \
speeches, CPI, core CPI, PPI, nonfarm payrolls, PCE / core PCE, GDP, retail sales, \
ISM, JOLTS, jobless claims, UMich sentiment, big Treasury auctions, monthly \
options expiration / quad witching, VIX expiration, index rebalances, market \
holidays / early closes, quarter-end, and mega-cap earnings (NVDA, AAPL, MSFT, \
AMZN, GOOGL, META, TSLA, etc.)."""

STYLE = f"""Audience: an SPX iron-condor trader. Focus only on SPX; mention other \
markets only as they affect SPX. Use the numbers provided; do not invent levels. \
Write in {LANGUAGE}. Event times in ET with PT in parentheses. Be honest about \
uncertainty. Output only the report.

FORMAT (WhatsApp, follow the template exactly):
- Only WhatsApp formatting: *bold*, _italic_, and ``` monospace blocks. No markdown \
headers (#), no **double asterisks**, no tables, no links.
- Section titles are one line: emoji + *BOLD CAPS TITLE*.
- Put every group of numbers in a ``` block, one item per line, labels padded \
with spaces so the numbers line up in columns. Max 30 characters per line inside \
blocks (phone width). No blank lines inside a block.
- Exactly one blank line between sections. Text lines start with "▸ ".
- Keep the whole report under 2,000 characters.
- Last line: _Not financial advice._"""

MORNING_TEMPLATE = """*☀️ SPX PRE-MARKET · {day}*
━━━━━━━━━━━━━━━━━━

*⚠️ TODAY*
▸ <biggest scheduled event with time ET (PT), or "No major scheduled events">
▸ <other events; big events later this week>

*🌙 OVERNIGHT*
```
ES      <price>  <+x.xx%>
Open    ~<implied SPX open>
VIX     <x.xx>
```
▸ <one line on what's driving it>

*📐 LEVELS*
```
R2  <level>  <label>
R1  <level>  <label>
──  <prior close>  Close
S1  <level>  <label>
S2  <level>  <label>
```

*🌡️ VOLATILITY*
```
VIX9D/VIX/3M  <a> / <b> / <c>
Curve         <contango/backwardation>
RV20 vs VIX   <x.x> vs <x.x>
SKEW          <xxx>
```

*📏 EXPECTED MOVE*
```
Today   ±<pts> (<x.xx%>)
        <low> – <high>
<Mon DD> 1σ   <low> – <high>
       1.5σ   <low> – <high>
```
(repeat the last two lines for each expiration given)

*🦅 IRON CONDOR*
▸ <open/adjust today? calm enough?>
▸ <riskier side and why>

*🎯 CALL*
```
Sentiment   <Bullish/Neutral/Bearish>
Confidence  <xx%>
Direction   <e.g. +0.2% to +0.5%>
Spike/crash <Low/Medium/High>
```
▸ <one-line reason>

_Not financial advice._"""

PRECLOSE_TEMPLATE = """*🔔 SPX · 30 MIN TO CLOSE · {day}*
━━━━━━━━━━━━━━━━━━

*<SPX price>*  <🟢▲/🔴▼>  <+pts> (<+x.xx%>)
```
Range   <low> – <high>
Size    <pts> vs avg <pts>
Type    <trend/inside/reversal day>
```

*📰 WHY*
▸ <driver 1>
▸ <driver 2>

*📐 LEVELS*
```
R2  <level>  <label>
R1  <level>  <label>
──  <price>  Now
S1  <level>  <label>
S2  <level>  <label>
```
▸ <what a close above R1 / below S1 would mean>

*🌡️ VOLATILITY*
```
VIX9D/VIX/3M  <a> / <b> / <c>
Curve         <contango/backwardation>
RV20 vs VIX   <x.x> vs <x.x>
SKEW / VVIX   <xxx> / <xx>
```

*📏 EXPECTED MOVE*
```
{next_day}   ±<pts> (<x.xx%>)
        <low> – <high>
<Mon DD> 1σ   <low> – <high>
       1.5σ   <low> – <high>
```
(repeat the last two lines for each expiration given)

*🦅 IRON CONDOR*
▸ <credit rich/thin, environment>
▸ <riskier side and why>
▸ <what would change the view>

*📅 {next_day_upper}*
▸ <⚠️ events with times, e.g. "⚠️ FOMC decision 2:00 PM ET (11:00 AM PT)", or "No major events">
▸ <next big event this week/next>

*🎯 CALL FOR {next_day_upper}*
```
Sentiment   <Bullish/Neutral/Bearish>
Confidence  <xx%>
Spike/crash <Low/Medium/High>
```

_Not financial advice._"""


# ---------- Claude ----------
def ask_claude(prompt):
    """Call Claude with web search. Continues if the search loop pauses."""
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(4):
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": 16000,
                  "tools": [{"type": "web_search_20250305", "name": "web_search",
                             "max_uses": 8}],
                  "messages": messages},
            timeout=500,
        )
        if r.status_code != 200:
            raise RuntimeError(f"Anthropic API error {r.status_code}: {r.text[:300]}")
        data = r.json()
        blocks, stop = data["content"], data.get("stop_reason")
        print(f"Claude call {attempt + 1}: stop_reason={stop}, blocks={len(blocks)}")
        if stop == "pause_turn":
            messages.append({"role": "assistant", "content": blocks})
            continue
        tool_types = ("server_tool_use", "web_search_tool_result")
        last_tool = max((i for i, b in enumerate(blocks) if b["type"] in tool_types), default=-1)
        final = "".join(b.get("text", "") for b in blocks[last_tool + 1:] if b["type"] == "text").strip()
        if stop == "max_tokens" and not final:
            # Ran out of room before writing the report: ask it to write it now.
            messages.append({"role": "assistant", "content": blocks})
            messages.append({"role": "user", "content":
                             "Stop researching. Write the final report now, following the template exactly."})
            continue
        text = final
        if not text:
            text = "\n".join(b["text"] for b in blocks if b["type"] == "text").strip()
        if not text:
            raise RuntimeError(f"Claude returned no report text (stop_reason={stop}).")
        return text
    raise RuntimeError("Claude kept pausing and never finished the report.")


# ---------- jobs ----------
def job_update(now):
    if not FORCE and not (trading_day(now.date()) and in_window(now, (9, 30), (16, 30))):
        print(f"Outside market hours ({now:%a %H:%M} ET)."); return
    price, prev = last_and_prev("^GSPC")
    try:
        live = float(yf.Ticker("^GSPC").fast_info["lastPrice"])
        price = live if live > 0 else price
    except Exception:
        pass
    chg = price - prev
    arrow = "🟢▲" if chg > 0 else "🔴▼" if chg < 0 else "■"
    tag = " (close)" if now.time() >= dtime(16, 0) else ""
    send(f"SPX {price:,.2f} {arrow} {chg:+,.2f} ({chg / prev * 100:+.2f}%) · {now:%H:%M} ET{tag}")


def job_morning(now):
    if not FORCE and not (trading_day(now.date()) and in_window(now, (9, 0), (9, 45))):
        print(f"Not pre-market on a trading day ({now:%a %H:%M} ET)."); return
    overnight = "\n".join(pct_line(n, s) for n, s in {
        "S&P 500 futures (ES)": "ES=F", "Nasdaq 100 futures (NQ)": "NQ=F",
        "10Y yield": "^TNX", "WTI crude": "CL=F", "US dollar index": "DX-Y.NYB",
        "Nikkei": "^N225", "Hang Seng": "^HSI", "Euro Stoxx 50": "^STOXX50E"}.items())
    prompt = f"""It is {now:%A %Y-%m-%d, %H:%M} ET, just before the US open.

SPX data:
{spx_stats(now, "pre")}

Overnight / global (vs prior close):
{overnight}

Web search: today's US economic calendar with times, Fed speakers, earnings \
before/after the bell that matter for SPX, and important overnight news. Also \
note any big event later this week. High-impact events: {HIGH_IMPACT}

Fill in this template (replace every <...>, keep the layout):
{MORNING_TEMPLATE.format(day=now.strftime("%a %b %d").upper())}

{STYLE}"""
    report = ask_claude(prompt)
    wait_until(MORNING_SEND)
    send(report)


def job_preclose(now):
    if not FORCE and not (trading_day(now.date()) and in_window(now, (15, 0), (15, 55))):
        print(f"Not the pre-close window on a trading day ({now:%a %H:%M} ET)."); return
    nd = next_trading_day(now.date())
    prompt = f"""It is {now:%A %Y-%m-%d, %H:%M} ET, about 30 minutes before the US close.

SPX data (intraday, may be slightly delayed):
{spx_stats(now, "live")}

Web search: why SPX is moving today (main drivers), notable news, and the US \
economic calendar for the next trading day ({nd:%A %b %d}) with times, plus the \
rest of the week. Flag anything like FOMC, CPI, jobs report, PCE. After-hours \
earnings today that could move SPX. High-impact events: {HIGH_IMPACT}

Fill in this template (replace every <...>, keep the layout):
{PRECLOSE_TEMPLATE.format(day=now.strftime("%a %b %d").upper(), next_day=nd.strftime("%a"), next_day_upper=nd.strftime("%A").upper())}

{STYLE}"""
    report = ask_claude(prompt)
    wait_until(PRECLOSE_SEND)
    send(report)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "update"
    jobs = {"update": job_update, "morning": job_morning, "preclose": job_preclose}
    try:
        jobs[mode](now_et())
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
