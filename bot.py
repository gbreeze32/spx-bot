"""SPX WhatsApp bot (SPX + iron-condor focus).

  python bot.py update     -> SPX price / change every 30 min, 9:30-16:00 ET
  python bot.py morning    -> pre-market report, sent ~9:21 ET (6:21 AM PT)
  python bot.py preclose   -> report 30 min before the close, 15:30 ET (12:30 PM PT)

The two reports are published as designed web pages (GitHub Pages, /docs folder)
and WhatsApp gets a short summary with the link.

Reports go to Telegram (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID). The 30-min
updates go to WhatsApp via CallMeBot (WHATSAPP_PHONE, CALLMEBOT_APIKEY) unless
UPDATES_TO = "telegram". Claude needs ANTHROPIC_API_KEY.
FORCE_SEND=1 ignores the time window and sends right away (testing).
DRY_RUN=1 writes the page locally and prints instead of publishing/sending.
"""
import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

import holidays
import numpy as np
import requests
import yfinance as yf

import page

# ---- Settings you may want to change -------------------------------------
LANGUAGE = "English"           # e.g. "Simplified Chinese" for 中文报告
MODEL = "claude-sonnet-5"      # Claude model used for the reports
MORNING_SEND = (9, 21)         # ET  (= 6:21 AM Pacific)
PRECLOSE_SEND = (15, 30)       # ET  (= 12:30 PM Pacific)
UPDATES_TO = "whatsapp"        # 30-min updates: "whatsapp" or "telegram"
# --------------------------------------------------------------------------

ET = ZoneInfo("America/New_York")
FORCE = os.environ.get("FORCE_SEND") == "1"
DRY = os.environ.get("DRY_RUN") == "1"
NAN = float("nan")


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


def whatsapp_fix(text):
    """WhatsApp only shows ``` monospace when the backticks touch the text."""
    return re.sub(r"```[ \t]*\n(.*?)\n[ \t]*```", r"```\1```", text, flags=re.S)


def _callmebot(text):
    r = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": os.environ["WHATSAPP_PHONE"],
                "apikey": os.environ["CALLMEBOT_APIKEY"], "text": text},
        timeout=60,
    )
    reply = " ".join(r.text.split())[:200]
    print(f"CallMeBot: HTTP {r.status_code}: {reply}")
    bad = ("error", "invalid", "blocked", "too long", "not allowed")
    ok = "queued" in reply.lower() or "sent" in reply.lower()
    return r.status_code == 200 and (ok or not any(w in reply.lower() for w in bad)), r.status_code


LINK = re.compile(r"(?:https?://)?[\w.-]+\.github\.io/\S*")


def _safe(text):
    """Remove characters that web firewalls often flag (&, quotes, <>, ; ...)."""
    text = "\n".join(l for l in text.splitlines() if not set(l.strip()) <= {"━"})
    for a_, b_ in (("S&P", "S+P"), (" & ", " and "), ("&", "+"), ("/", "-"), ("±", "+-"),
                   ("–", "-"), ("—", "-"), ("`", "")):
        text = text.replace(a_, b_)
    return re.sub(r"[\"'<>;{}\\|$%^=]", "", text)


def _ascii(text):
    return _safe(text).encode("ascii", "ignore").decode()


def send(text):
    """Send to WhatsApp via CallMeBot, split into parts if long.

    CallMeBot's firewall sometimes refuses a message (HTTP 403) because of its
    content. Then the bot retries step by step: without the link, then with
    risky characters removed, then plain ASCII, and sends the link on its own.
    The log shows which step worked.
    """
    text = whatsapp_fix(text)
    parts = split_message(text)
    if not parts:
        raise RuntimeError("Nothing to send (empty message).")
    print(f"---- message ({len(text)} chars, {len(parts)} part(s)) ----\n{text}\n----")
    if DRY:
        return
    for i, part in enumerate(parts):
        if i:
            time.sleep(10)
        part = re.sub(r"https?://", "", part)
        links = LINK.findall(part)
        body = "\n".join(l for l in part.splitlines() if not LINK.search(l))
        note = "\n\n📊 Full report: link in next message" if links else ""
        steps = [("as written", part),
                 ("without the link", body + note),
                 ("with risky characters removed", _safe(body + note)),
                 ("plain ASCII", _ascii(body) + ("\n\nFull report: link in next message" if links else ""))]
        sent_step = None
        for n, (label, msg) in enumerate(steps):
            if n == 1 and not links:
                continue
            if n:
                time.sleep(10)
            ok, code = _callmebot(msg)
            if ok:
                sent_step = n
                print(f"Part {i + 1} sent {label}.")
                break
            if code != 403:
                raise RuntimeError(f"CallMeBot did not accept part {i + 1} (HTTP {code}).")
        if sent_step is None:
            raise RuntimeError(f"CallMeBot refused part {i + 1} in every form (HTTP 403).")
        if sent_step > 0 and links:
            url = links[0]
            index = url.split("/reports/")[0] + "/"
            for cand in (url, index, index.replace(".", " . ")):
                time.sleep(10)
                if _callmebot(cand)[0]:
                    print("Link sent as:", cand)
                    break
            else:
                print("Could not send the link; open your reports page bookmark.")
    print("Sent.")


def telegram_ready():
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def send_telegram(text_html, button=None):
    """Send an HTML-formatted Telegram message, optionally with a link button."""
    print(f"---- telegram ({len(text_html)} chars) ----\n{text_html}\n----")
    if DRY:
        return
    body = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text_html,
            "parse_mode": "HTML", "disable_web_page_preview": True}
    if button:
        body["reply_markup"] = {"inline_keyboard": [[{"text": button[0], "url": button[1]}]]}
    r = requests.post(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                      json=body, timeout=60)
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error {r.status_code}: {data.get('description', r.text[:200])}")
    print("Sent to Telegram.")


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


def futures_change(sym):
    """Futures last price and % change since yesterday's 4 PM ET (same contract)."""
    x = yf.Ticker(sym).history(period="5d", interval="15m").dropna(subset=["Close"])
    x.index = x.index.tz_convert(ET)
    last = float(x["Close"].iloc[-1])
    before = x[(x.index.date < x.index[-1].date()) & (x.index.time <= dtime(16, 0))]
    base = float(before["Close"].iloc[-1])
    return last, (last / base - 1) * 100


def ic_expirations(today, lo=28, hi=46):
    """Fridays 28-46 days out (standard 30-45 DTE iron condor window)."""
    out, d = [], today + timedelta(days=lo)
    while (d - today).days <= hi:
        if d.weekday() == 4:
            out.append(d)
        d += timedelta(days=1)
    return out


def spx_stats(now, session):
    """All SPX numbers. session='pre' (before open) or 'live'. Returns (text, data)."""
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
    rv = {n: float(r.tail(n).std() * np.sqrt(252) * 100) for n in (5, 10, 20)}
    ma = {n: float(closes.tail(n).mean()) for n in (20, 50, 100, 200)}
    atr = float((h["High"] - h["Low"]).tail(14).mean())

    vol = {}
    for sym in ["^VIX9D", "^VIX", "^VIX3M", "^VVIX", "^SKEW"]:
        try:
            last, prv = last_and_prev(sym)
            vol[sym.strip("^")] = (last, last - prv)
        except Exception:
            vol[sym.strip("^")] = (NAN, NAN)
    vix, vix3m = vol["VIX"][0], vol["VIX3M"][0]

    def iv_for(dte):
        if dte <= 30 or vix3m != vix3m:
            return vix
        return vix + (vix3m - vix) * min(dte - 30, 63) / 63

    anchor = now.date() if session == "live" else h.index[-1].date()
    exps = ic_expirations(now.date())
    em = []
    one = price * vix / 100 / np.sqrt(252)
    nd = now.date() if session == "pre" else next_trading_day(now.date())
    em.append({"label": "Today" if session == "pre" else nd.strftime("%a %b %-d"), "sub": "1 day",
               "sd": one, "lo": price - one, "hi": price + one})
    for ex in exps:
        dte = (ex - now.date()).days
        sd = price * iv_for(dte) / 100 * np.sqrt(dte / 365)
        em.append({"label": ex.strftime("%b %-d"), "sub": f"{dte} DTE", "sd": sd,
                   "lo": price - sd, "hi": price + sd, "lo15": price - 1.5 * sd, "hi15": price + 1.5 * sd})

    ma20s, ma50s = c.rolling(20).mean(), c.rolling(50).mean()
    n = 45
    data = {
        "price": price, "prev": prev, "atr": atr, "rv20": rv[20], "vol": vol, "vix": vix, "vix3m": vix3m,
        "em": em, "expiries": exps, "anchor_date": anchor,
        "hist_dates": [d.date() for d in h.index[-n:]], "hist_close": [float(x) for x in c.tail(n)],
        "hist_ma20": [float(x) for x in ma20s.tail(n)], "hist_ma50": [float(x) for x in ma50s.tail(n)],
    }
    if live_today:
        data["hist_close"][-1] = price
        o, hi_, lo_ = (float(x) for x in h.iloc[-1][["Open", "High", "Low"]])
        data.update(open=o, high=max(hi_, price), low=min(lo_, price))

    lines = []
    if live_today:
        lines.append(f"SPX now {price:,.2f}, {price - prev:+,.2f} ({(price / prev - 1) * 100:+.2f}%) "
                     f"vs prior close {prev:,.2f}. Today open {data['open']:,.2f}, high {data['high']:,.2f}, "
                     f"low {data['low']:,.2f}, range {data['high'] - data['low']:.0f} pts vs 14-day avg {atr:.0f}.")
    else:
        lines.append(f"SPX prior close {price:,.2f} ({(price / float(c.iloc[-2]) - 1) * 100:+.2f}% that day). "
                     f"14-day avg daily range {atr:.0f} pts.")
    lines.append("Moving averages: " + ", ".join(
        f"{k}d {v:,.0f} ({(price / v - 1) * 100:+.1f}%)" for k, v in ma.items()))
    lines.append(f"52-week high {h['High'].max():,.1f} on {h['High'].idxmax():%b %d}. "
                 f"20-day high {h['High'].tail(20).max():,.1f}, 20-day low "
                 f"{h['Low'].tail(20).min():,.1f} on {h['Low'].tail(20).idxmin():%b %d}. "
                 f"5-day change {price - float(closes.iloc[-6]):+,.0f} pts.")
    lines.append("Last 5 sessions (O/H/L/C): " + "; ".join(
        f"{i:%m-%d} {rw.Open:,.0f}/{rw.High:,.0f}/{rw.Low:,.0f}/{rw.Close:,.0f}"
        for i, rw in h.tail(5).iterrows()))
    lines.append("Vol: " + ", ".join(f"{k} {v[0]:.2f} ({v[1]:+.2f})" for k, v in vol.items()))
    lines.append(f"Realized vol: 5d {rv[5]:.1f}%, 10d {rv[10]:.1f}%, 20d {rv[20]:.1f}% "
                 f"(VIX minus RV20 = {vix - rv[20]:+.1f} pts).")
    lines.append("Expected moves (VIX term structure, symmetric):\n  " + "\n  ".join(
        f"{x['label']} ({x['sub']}): 1σ ±{x['sd']:.0f} ({x['lo']:,.0f}–{x['hi']:,.0f})"
        + (f", 1.5σ {x['lo15']:,.0f}–{x['hi15']:,.0f}" if "lo15" in x else "") for x in em))
    return "\n".join(lines), data


def overnight(prev_close):
    """Cards for the pre-market page + text for the prompt."""
    cards, text = [], []
    try:
        es, pct = futures_change("ES=F")
        cards.append(("ES futures", f"{es:,.2f}", f"{pct:+.2f}% · open ~{prev_close * (1 + pct / 100):,.0f}",
                      page.chg_cls(pct)))
        text.append(f"- ES futures {es:,.2f} ({pct:+.2f}% since 4 PM ET), implied SPX open ~{prev_close * (1 + pct / 100):,.0f}")
    except Exception:
        pass
    try:
        nq, pct = futures_change("NQ=F")
        cards.append(("NQ futures", f"{nq:,.0f}", f"{pct:+.2f}%", page.chg_cls(pct)))
        text.append(f"- NQ futures {nq:,.0f} ({pct:+.2f}%)")
    except Exception:
        pass
    for name, sym, fmt_ in [("WTI crude", "CL=F", "${:,.2f}"), ("10-year yield", "^TNX", "{:.2f}%")]:
        try:
            last, prv = last_and_prev(sym)
            pct = (last / prv - 1) * 100
            cards.append((name, fmt_.format(last), f"{pct:+.2f}%", page.chg_cls(pct, True)))
            text.append(f"- {name} {fmt_.format(last)} ({pct:+.2f}%)")
        except Exception:
            pass
    for name, sym in [("Nikkei", "^N225"), ("Hang Seng", "^HSI"), ("Euro Stoxx 50", "^STOXX50E")]:
        try:
            last, prv = last_and_prev(sym)
            text.append(f"- {name} {(last / prv - 1) * 100:+.2f}% (latest session)")
        except Exception:
            pass
    return cards[:4], "\n".join(text)


# ---------- Claude ----------
HIGH_IMPACT = """FOMC decisions / statements / minutes, Powell or other Fed \
speeches, CPI, core CPI, PPI, nonfarm payrolls, PCE / core PCE, GDP, retail sales, \
ISM, JOLTS, jobless claims, UMich sentiment, big Treasury auctions, monthly \
options expiration / quad witching, VIX expiration, index rebalances, market \
holidays / early closes, quarter-end, and mega-cap earnings (NVDA, AAPL, MSFT, \
AMZN, GOOGL, META, TSLA, etc.)."""

JSON_SPEC = """Return ONLY a JSON object (no markdown fences, no other text) with these keys:
{
 "headline": "one sentence, the key takeaway, max 30 words",
 "chart_title": "short sentence about where SPX sits vs levels/expected-move cone, max 16 words",
 "events": [{"title": "short title with time ET (PT) if scheduled", "detail": "one sentence", "important": true}],
 "drivers": ["2-3 short bullets: %DRIVERS%"],
 "levels": [{"tag": "R2", "label": "what it is", "level": 7816.7}],
 "level_note": "one sentence: what a break above R1 / below S1 would mean",
 "vol_note": "one or two sentences on the term structure, IV vs RV, SKEW",
 "ic_tags": [{"text": "e.g. Call side: higher risk", "tone": "bad|warn|good"}],
 "ic_points": ["2-3 bullets for an SPX iron-condor trader"],
 "call": {"sentiment": "Bullish|Neutral|Bearish (may add +/-)", "confidence": 55,
          "spike_risk": "Low|Low–Med|Medium|High", "gauge": 20,
          "direction": "rough expected move, e.g. +0.2% to +0.5%", "reason": "one sentence"}
}
Rules: levels = 2 resistances (R1 nearest, R2) and 2-4 supports (S1 nearest...), \
taken from the numbers given (prior closes, highs/lows, moving averages, gaps). \
gauge: -100 (very bearish) to +100 (very bullish). 2-4 ic_tags. Put the most \
important event first and mark big ones (FOMC, CPI, jobs, PCE...) important=true. \
Plain text inside strings (no markdown). Write in """ + LANGUAGE + "."


def ask_claude(prompt, use_search=True):
    """Call Claude (with web search). Continues if the search loop pauses."""
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(4):
        body = {"model": MODEL, "max_tokens": 16000, "messages": messages}
        if use_search:
            body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json=body, timeout=500,
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
            messages.append({"role": "assistant", "content": blocks})
            messages.append({"role": "user", "content":
                             "Stop researching. Write the final answer now, exactly in the requested format."})
            continue
        if not final:
            final = "\n".join(b["text"] for b in blocks if b["type"] == "text").strip()
        if not final:
            raise RuntimeError(f"Claude returned no text (stop_reason={stop}).")
        return final
    raise RuntimeError("Claude never finished the report.")


def parse_json(text):
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("no JSON object found")
    return json.loads(text[a:b + 1])


def get_ai(prompt):
    raw = ask_claude(prompt)
    try:
        return parse_json(raw)
    except Exception as err:
        print(f"JSON problem ({err}); asking Claude to repair it.")
        fixed = ask_claude("Convert this into ONE valid JSON object with the same content and keys. "
                           "Output only the JSON.\n\n" + raw, use_search=False)
        return parse_json(fixed)


# ---------- publishing (GitHub Pages) ----------
def pages_url():
    repo = os.environ.get("GITHUB_REPOSITORY", "owner/spx-bot")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/"


def publish(filename, html_text):
    """Write docs/reports/<file>, rebuild docs/index.html, commit and push."""
    os.makedirs("docs/reports", exist_ok=True)
    open("docs/.nojekyll", "a").close()
    with open(f"docs/reports/{filename}", "w", encoding="utf-8") as f:
        f.write(html_text)
    files = sorted(os.listdir("docs/reports"), reverse=True)
    items = []
    for f in files:
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(morning|preclose)\.html$", f)
        if m:
            d = datetime.strptime(m.group(1), "%Y-%m-%d")
            items.append((f, f"{d:%a %b %-d, %Y} · {'Pre-market' if m.group(2) == 'morning' else 'Pre-close'}"))
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(page.render_index(items))
    url = pages_url() + "reports/" + filename
    if DRY:
        print(f"(dry run) page written to docs/reports/{filename}")
        return url
    git = lambda *a: subprocess.run(["git", *a], check=True)
    git("config", "user.name", "spx-bot")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "docs")
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        git("commit", "-m", f"Report {filename}")
        for _ in range(3):
            if subprocess.run(["git", "pull", "--rebase", "-q"]).returncode == 0 and \
               subprocess.run(["git", "push", "-q"]).returncode == 0:
                break
            time.sleep(5)
        else:
            raise RuntimeError("Could not push the report page.")
    print("Published:", url)
    return url


def wait_for_page(url, limit=240):
    """GitHub Pages takes ~1 minute to go live; wait so the link works."""
    if DRY:
        return
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            if requests.get(url, timeout=15).status_code == 200:
                print("Page is live.")
                return
        except Exception:
            pass
        time.sleep(15)
    print("Page not live yet; sending the link anyway.")


# ---------- WhatsApp summaries ----------
def pct_str(p):
    return "0.00%" if abs(p) < 0.005 else f"{p:+.2f}%"


def summary(kind, now, s, ai, url, nd):
    c = ai.get("call") or {}
    call = f"{c.get('sentiment')} · {c.get('confidence')}%" if c.get("sentiment") else "—"
    ev = [x for x in (ai.get("events") or []) if x.get("important")][:2] or (ai.get("events") or [])[:1]
    lines = []
    if kind == "morning":
        one = s["em"][0]
        lines += [f"*☀️ SPX PRE-MARKET · {now:%a %b %-d}*".upper(), "━━━━━━━━━━━━━━━━━━",
                  f"▸ {ai.get('headline', '')}", "",
                  "```" + "\n".join([
                      f"Move    ±{one['sd']:.0f} pts ({one['sd'] / s['price'] * 100:.2f}%)",
                      f"Range   {one['lo']:,.0f} – {one['hi']:,.0f}",
                      f"Call    {call}",
                      f"Risk    {c.get('spike_risk', '—')}"]) + "```"]
    else:
        ch = s["price"] - s["prev"]
        arrow = "🟢▲" if ch > 0 else "🔴▼" if ch < 0 else "■"
        one = s["em"][0]
        lines += [f"*🔔 SPX · 30 MIN TO CLOSE · {now:%a %b %-d}*".upper(), "━━━━━━━━━━━━━━━━━━",
                  f"*{s['price']:,.2f}*  {arrow} {ch:+,.2f} ({pct_str(ch / s['prev'] * 100)})",
                  f"▸ {ai.get('headline', '')}", "",
                  "```" + "\n".join([
                      f"{nd:%a}     ±{one['sd']:.0f} pts ({one['sd'] / s['price'] * 100:.2f}%)",
                      f"Range   {one['lo']:,.0f} – {one['hi']:,.0f}",
                      f"Call    {call}",
                      f"Risk    {c.get('spike_risk', '—')}"]) + "```"]
    if ev:
        lines += [""] + [f"{'⚠️' if x.get('important') else '▸'} {x.get('title', '')}" for x in ev]
    lines += ["", f"📊 Full report: {url.replace('https://', '')}"]
    return "\n".join(lines)


def summary_telegram(kind, now, s, ai, nd):
    t = html.escape
    c = ai.get("call") or {}
    call = f"{c.get('sentiment')} · {c.get('confidence')}%" if c.get("sentiment") else "—"
    one = s["em"][0]
    ev = [x for x in (ai.get("events") or []) if x.get("important")][:2] or (ai.get("events") or [])[:1]
    if kind == "morning":
        head = "<b>" + f"☀️ SPX PRE-MARKET · {now:%a %b %-d}".upper() + "</b>"
        rows = [f"Move    ±{one['sd']:.0f} pts ({one['sd'] / s['price'] * 100:.2f}%)"]
        top = ""
    else:
        ch = s["price"] - s["prev"]
        arrow = "🟢▲" if ch > 0 else "🔴▼" if ch < 0 else "■"
        head = "<b>" + f"🔔 SPX · 30 MIN TO CLOSE · {now:%a %b %-d}".upper() + "</b>"
        top = f"<b>{s['price']:,.2f}</b>  {arrow} {ch:+,.2f} ({pct_str(ch / s['prev'] * 100)})\n"
        rows = [f"{nd:%a}     ±{one['sd']:.0f} pts ({one['sd'] / s['price'] * 100:.2f}%)"]
    rows += [f"Range   {one['lo']:,.0f} – {one['hi']:,.0f}", f"Call    {call}",
             f"Risk    {c.get('spike_risk', '—')}"]
    lines = [head, top + t(ai.get("headline", "")), "<pre>" + t("\n".join(rows)) + "</pre>"]
    if ev:
        lines.append("\n".join(f"{'⚠️' if x.get('important') else '▸'} {t(str(x.get('title', '')))}" for x in ev))
    return "\n\n".join(lines)


def fallback_ai(err):
    return {"headline": f"Commentary unavailable today ({str(err)[:80]}). Numbers below are still current.",
            "chart_title": "", "events": [], "drivers": [], "levels": [], "level_note": "",
            "vol_note": "", "ic_tags": [], "ic_points": [], "call": {}}


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
    msg = f"SPX {price:,.2f} {arrow} {chg:+,.2f} ({pct_str(chg / prev * 100)}) · {now:%H:%M} ET{tag}"
    if UPDATES_TO == "telegram" and telegram_ready():
        send_telegram(html.escape(msg))
    else:
        send(msg)


def run_report(kind, now):
    session = "pre" if kind == "morning" else "live"
    nd = now.date() if kind == "morning" else next_trading_day(now.date())
    text, s = spx_stats(now, session)
    if kind == "morning":
        s["overnight"], on_text = overnight(s["price"])
        prompt = f"""It is {now:%A %Y-%m-%d, %H:%M} ET, just before the US open.

SPX data:
{text}

Overnight / global:
{on_text}

Web search: today's US economic calendar with times, Fed speakers, earnings \
before/after the bell that matter for SPX, important overnight news, and big \
events later this week. High-impact events: {HIGH_IMPACT}

Audience: an SPX iron-condor trader. Focus on SPX only. Use the numbers given; \
do not invent levels. Events = today's events first, then big ones later this week.

{JSON_SPEC.replace("%DRIVERS%", "what is driving futures / the open")}"""
    else:
        prompt = f"""It is {now:%A %Y-%m-%d, %H:%M} ET, about 30 minutes before the US close.

SPX data (intraday, may be slightly delayed):
{text}

Web search: why SPX is moving today, notable news, after-hours earnings that could \
move SPX, and the US economic calendar for the next trading day ({nd:%A %b %d}) \
with times plus the rest of the week. High-impact events: {HIGH_IMPACT}

Audience: an SPX iron-condor trader. Focus on SPX only. Use the numbers given; \
do not invent levels. Events = the next trading day's events (heads-up), then \
the next big event if nothing major. The "call" is for {nd:%A}.

{JSON_SPEC.replace("%DRIVERS%", "why SPX moved today")}"""
    try:
        ai = get_ai(prompt)
    except Exception as err:
        print("Claude failed:", err)
        ai = fallback_ai(err)
    html_text = page.render(kind, now, s, ai, nd)
    url = publish(f"{now:%Y-%m-%d}-{kind}.html", html_text)
    wait_until(MORNING_SEND if kind == "morning" else PRECLOSE_SEND)
    wait_for_page(url)
    if telegram_ready():
        send_telegram(summary_telegram(kind, now, s, ai, nd), ("📊 Open full report", url))
    else:
        send(summary(kind, now, s, ai, url, nd))


def job_morning(now):
    if not FORCE and not (trading_day(now.date()) and in_window(now, (9, 0), (9, 45))):
        print(f"Not pre-market on a trading day ({now:%a %H:%M} ET)."); return
    run_report("morning", now)


def job_preclose(now):
    if not FORCE and not (trading_day(now.date()) and in_window(now, (15, 0), (15, 55))):
        print(f"Not the pre-close window on a trading day ({now:%a %H:%M} ET)."); return
    run_report("preclose", now)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "update"
    jobs = {"update": job_update, "morning": job_morning, "preclose": job_preclose}
    try:
        jobs[mode](now_et())
    except Exception as e:
        print("Error:", e)
        sys.exit(1)
