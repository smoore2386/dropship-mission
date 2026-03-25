#!/usr/bin/env python3
"""
Dropship Mission — Provider Rate Limit Dashboard

Shows Claude & Grok health across all openclaw agents:
  • Which profiles are in cooldown and when they reset
  • Recent rate limit events from gateway logs
  • Live API rate limit headers (if ANTHROPIC_API_KEY / XAI_API_KEY env vars set)

Usage:
  python3 dashboard.py           # one-shot check
  python3 dashboard.py -w        # watch mode (refresh every 30s)
  python3 dashboard.py -w 15     # watch mode every 15s
"""

import json
import os
import sys
import glob
import time
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ─── ANSI colors ──────────────────────────────────────────────────────────────
NO_COLOR = not sys.stdout.isatty() or os.environ.get("NO_COLOR")

def _c(code, t): return t if NO_COLOR else f"\033[{code}m{t}\033[0m"
def bold(t): return _c("1", t)
def dim(t): return _c("2", t)
def red(t): return _c("91", t)
def yellow(t): return _c("93", t)
def green(t): return _c("92", t)
def cyan(t): return _c("96", t)
def blue(t): return _c("94", t)
def white(t): return _c("97", t)
def magenta(t): return _c("95", t)

W = 62  # display width

# ─── Helpers ──────────────────────────────────────────────────────────────────

def fmt_ms(ms):
    """Convert millisecond epoch to human-readable relative time."""
    if ms is None:
        return dim("none")
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = dt - now
    secs = int(delta.total_seconds())
    if secs <= 0:
        return green("expired ✓")
    if secs < 60:
        return red(f"resets in {secs}s")
    if secs < 3600:
        m, s = divmod(secs, 60)
        return yellow(f"resets in {m}m {s}s")
    h, rem = divmod(secs, 3600)
    m = rem // 60
    return red(f"resets in {h}h {m}m")

def fmt_last_used(ms):
    if ms is None:
        return dim("never")
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"

def bar(remaining, total, width=12):
    if remaining is None or total is None or total == 0:
        return dim("─" * width)
    pct = remaining / total
    filled = max(0, min(width, int(pct * width)))
    b = "█" * filled + "░" * (width - filled)
    if pct > 0.5: return green(b)
    if pct > 0.2: return yellow(b)
    return red(b)

def fmt_num(n):
    if n is None: return dim("n/a")
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.0f}k"
    return str(n)

def fmt_reset_header(s):
    """Parse ISO 8601 reset timestamp from API headers."""
    if not s:
        return dim("n/a")
    try:
        s = s.replace("Z", "").split("+")[0]
        try:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        secs = int((dt - now).total_seconds())
        if secs <= 0: return green("< 1s")
        if secs < 60: return cyan(f"{secs}s")
        m, sc = divmod(secs, 60)
        return cyan(f"{m}m {sc}s")
    except Exception:
        return cyan(str(s))

def div(label=""):
    pad = W - 2 - len(label)
    print(dim("─" * 2 + label + "─" * max(0, pad)))

# ─── Data loading ─────────────────────────────────────────────────────────────

AGENT_FILE_PATTERNS = [
    os.path.expanduser("~/.openclaw/agents/*/agent/auth-profiles.json"),  # main, ceo, engineering, etc.
    os.path.expanduser("~/.openclaw/agents/*/auth-profiles.json"),        # sales flat layout
]

def load_profiles():
    """Load all agent auth profiles grouped by agent name."""
    agents = {}
    seen = set()
    for pattern in AGENT_FILE_PATTERNS:
        for path in sorted(glob.glob(pattern)):
            if path in seen: continue
            seen.add(path)
            try:
                d = json.load(open(path))
                # infer agent name from path
                parts = path.replace(os.path.expanduser("~/.openclaw/agents/"), "").split("/")
                agent = parts[0]
                agents[agent] = {
                    "profiles": d.get("profiles", {}),
                    "stats": d.get("usageStats", {}),
                    "last_good": d.get("lastGood", {}),
                }
            except Exception:
                pass
    return agents

def load_model_status():
    """Get openclaw model status via CLI."""
    try:
        r = subprocess.run(
            ["openclaw", "models", "status", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if r.stdout:
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}

def load_recent_ratelimit_events(n=8):
    """Grep err log for recent rate-limit events with clean formatting."""
    events = []
    for logname in ("gateway.err.log", "gateway.log"):
        log = os.path.expanduser(f"~/.openclaw/logs/{logname}")
        if not os.path.exists(log):
            continue
        try:
            with open(log) as f:
                for line in f:
                    low = line.lower()
                    if ("rate limit" in low or "rate_limit" in low or "429" in low
                            or "failover" in low or "all models failed" in low):
                        # Extract timestamp and key details
                        stripped = line.strip()
                        # Try to clean up: "2026-03-23T13:50:19.857-04:00 [tag] message"
                        parts = stripped.split(" ", 2)
                        if len(parts) >= 3:
                            ts = parts[0][:19].replace("T", " ")
                            tag = parts[1] if parts[1].startswith("[") else ""
                            msg = parts[2] if tag else parts[1] + " " + parts[2]
                        else:
                            ts, tag, msg = "", "", stripped
                        # Skip noisy/duplicate lines
                        if "auth profile failure state" in msg:
                            continue
                        if "embedded run failover decision" in msg:
                            continue
                        events.append((ts, msg[:80]))
        except Exception:
            pass
    # Deduplicate consecutive identical messages
    seen = []
    for ts, msg in events:
        if not seen or seen[-1][1] != msg:
            seen.append((ts, msg))
    return seen[-n:]

# ─── Live API check (needs real API key) ─────────────────────────────────────

def live_check_anthropic(api_key):
    if not api_key:
        return None
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            lh = {k.lower(): v for k, v in resp.headers.items()}
            return {"status": "ok", "headers": lh, "code": 200}
    except urllib.error.HTTPError as e:
        lh = {k.lower(): v for k, v in e.headers.items()}
        return {"status": "error" if e.code != 429 else "rate_limited",
                "headers": lh, "code": e.code}
    except Exception as ex:
        return {"status": "error", "headers": {}, "code": 0, "msg": str(ex)}

def live_check_xai(api_key):
    if not api_key:
        return None
    req = urllib.request.Request(
        "https://api.x.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            lh = {k.lower(): v for k, v in resp.headers.items()}
            return {"status": "ok", "headers": lh, "code": 200}
    except urllib.error.HTTPError as e:
        lh = {k.lower(): v for k, v in e.headers.items()}
        return {"status": "error" if e.code != 429 else "rate_limited",
                "headers": lh, "code": e.code}
    except Exception as ex:
        return {"status": "error", "headers": {}, "code": 0, "msg": str(ex)}

# ─── Display ─────────────────────────────────────────────────────────────────

PROVIDER_LABELS = {
    "anthropic": ("Claude (Anthropic)", "🧠"),
    "xai":       ("Grok (xAI)", "⚡"),
}

AGENT_ORDER = ["main", "ceo", "marketing-research", "sales", "engineering", "tradingbot"]

def render_provider_section(agents, provider):
    """Render health table for one provider across all agents."""
    label, icon = PROVIDER_LABELS.get(provider, (provider, ""))
    div(f" {icon}  {bold(label)} ")

    now_ms = int(time.time() * 1000)
    any_data = False
    for agent in AGENT_ORDER:
        data = agents.get(agent)
        if not data:
            continue

        profiles = data["profiles"]
        stats = data["stats"]

        # Find profiles for this provider
        p_profiles = [(pid, p) for pid, p in profiles.items()
                      if p.get("provider") == provider]
        if not p_profiles:
            continue
        any_data = True

        # Aggregate: are any in cooldown?
        active_cooldowns = []
        best_profile = None
        for pid, p in p_profiles:
            s = stats.get(pid, {})
            cooldown = s.get("cooldownUntil")
            errors = s.get("errorCount", 0)
            last_used = s.get("lastUsed")
            if cooldown and cooldown > now_ms:
                active_cooldowns.append((pid, cooldown))
            else:
                if best_profile is None or (last_used or 0) > (best_profile[2] or 0):
                    best_profile = (pid, errors, last_used)

        # Status icon
        if active_cooldowns and best_profile is None:
            # All profiles in cooldown
            status_icon = red("⏸")
        elif active_cooldowns:
            # Some in cooldown, some OK
            status_icon = yellow("◑")
        else:
            status_icon = green("●")

        # Build compact line
        agent_label = f"{agent:<18}"

        if active_cooldowns and best_profile is None:
            # Show earliest reset
            earliest = min(c for _, c in active_cooldowns)
            cooldown_str = fmt_ms(earliest)
            line = f"  {status_icon} {dim(agent_label)}  all profiles cooling down  {cooldown_str}"
        elif active_cooldowns:
            pid, cooldown = active_cooldowns[0]
            cooldown_str = fmt_ms(cooldown)
            last_used = stats.get(best_profile[0], {}).get("lastUsed")
            line = f"  {status_icon} {dim(agent_label)}  active ({best_profile[0].split(':')[1]})  {dim(cooldown_str)} cooldown on {pid.split(':')[1]}"
        else:
            pid_active = best_profile[0] if best_profile else "?"
            last_used = best_profile[2] if best_profile else None
            line = f"  {status_icon} {dim(agent_label)}  {green('OK')} via {pid_active.split(':')[1]:<9}  last: {dim(fmt_last_used(last_used))}"

        print(line)

    if not any_data:
        print(f"  {dim('no profiles found')}")


def render_live_section(anthropic_key, xai_key):
    """Render live API rate-limit headers if keys are available."""
    div(f" 📡  {bold('Live Rate Limit Headers')} ")

    if not anthropic_key and not xai_key:
        print(f"  {dim('Set env vars for live API rate-limit stats:')}")
        print(f"  {dim('  export ANTHROPIC_API_KEY=sk-ant-api03-...')}")
        print(f"  {dim('  export XAI_API_KEY=xai-...')}")
        print(f"  {dim('  (openclaw session tokens do not work for direct API checks)')}")
        return

    # Anthropic
    if anthropic_key:
        r = live_check_anthropic(anthropic_key)
        if r:
            lh = r["headers"]
            stat = r["status"]
            code = r["code"]
            icon = green("●") if stat == "ok" else (red("⏸") if stat == "rate_limited" else yellow("?"))
            status_str = green("OK") if stat == "ok" else (red(f"RATE LIMITED (429)") if stat == "rate_limited" else yellow(f"HTTP {code}"))
            print(f"\n  {icon} {bold('Claude (Anthropic)')}  {status_str}")

            req_lim = lh.get("anthropic-ratelimit-requests-limit")
            req_rem = lh.get("anthropic-ratelimit-requests-remaining")
            req_rst = lh.get("anthropic-ratelimit-requests-reset")
            tok_lim = lh.get("anthropic-ratelimit-input-tokens-limit") or lh.get("anthropic-ratelimit-tokens-limit")
            tok_rem = lh.get("anthropic-ratelimit-input-tokens-remaining") or lh.get("anthropic-ratelimit-tokens-remaining")
            tok_rst = lh.get("anthropic-ratelimit-input-tokens-reset") or lh.get("anthropic-ratelimit-tokens-reset")

            if req_lim:
                rl, rr = int(req_lim), int(req_rem or 0)
                b = bar(rr, rl)
                print(f"    Requests   {b}  {fmt_num(rr)}/{fmt_num(rl)}  resets {fmt_reset_header(req_rst)}")
            if tok_lim:
                tl, tr = int(tok_lim), int(tok_rem or 0)
                b = bar(tr, tl)
                print(f"    In Tokens  {b}  {fmt_num(tr)}/{fmt_num(tl)}  resets {fmt_reset_header(tok_rst)}")

            retry = lh.get("retry-after")
            if retry:
                print(f"    {yellow('Retry-After:')} {retry}s")

            if not req_lim and not tok_lim:
                print(f"    {dim('(no rate-limit headers on GET /v1/models — make a chat call to see live counters)')}")

    # xAI
    if xai_key:
        r = live_check_xai(xai_key)
        if r:
            lh = r["headers"]
            stat = r["status"]
            code = r["code"]
            icon = green("●") if stat == "ok" else (red("⏸") if stat == "rate_limited" else yellow("?"))
            status_str = green("OK") if stat == "ok" else (red(f"RATE LIMITED (429)") if stat == "rate_limited" else yellow(f"HTTP {code}"))
            print(f"\n  {icon} {bold('Grok (xAI)')}  {status_str}")

            req_lim = lh.get("x-ratelimit-limit-requests")
            req_rem = lh.get("x-ratelimit-remaining-requests")
            req_rst = lh.get("x-ratelimit-reset-requests")
            tok_lim = lh.get("x-ratelimit-limit-tokens")
            tok_rem = lh.get("x-ratelimit-remaining-tokens")
            tok_rst = lh.get("x-ratelimit-reset-tokens")

            if req_lim:
                rl, rr = int(req_lim), int(req_rem or 0)
                b = bar(rr, rl)
                print(f"    Requests  {b}  {fmt_num(rr)}/{fmt_num(rl)}  resets {fmt_reset_header(req_rst)}")
            if tok_lim:
                tl, tr = int(tok_lim), int(tok_rem or 0)
                b = bar(tr, tl)
                print(f"    Tokens    {b}  {fmt_num(tr)}/{fmt_num(tl)}  resets {fmt_reset_header(tok_rst)}")

            if not req_lim and not tok_lim:
                print(f"    {dim('(no rate-limit headers on GET /v1/models for this key)')}")


def render_log_tail(events):
    """Show recent rate limit log events."""
    if not events:
        return
    div(f" 📋  {bold('Recent Rate Limit Events')} ")
    for ts, msg in events[-5:]:
        # Strip module tag [x/y] for brevity
        if "] " in msg:
            msg = msg[msg.index("] ") + 2:]
        ts_str = dim(ts) + "  " if ts else ""
        avail = W - 4 - len(ts)
        print(f"  {ts_str}{msg[:avail]}")


def render_model_status(mstatus):
    """Show active model and fallback chain."""
    if not mstatus:
        return
    div(f" ⚙️   {bold('Active Model Config')} ")
    default = mstatus.get("defaultModel", dim("unknown"))
    fallbacks = mstatus.get("fallbacks", [])
    print(f"  Primary:   {cyan(default)}")
    if fallbacks:
        print(f"  Fallbacks: {dim(' → ').join(yellow(f) for f in fallbacks)}")


def render(watch=False, interval=30):
    """Full dashboard render."""
    if watch:
        print("\033[2J\033[H", end="")  # clear screen

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print(bold(cyan("╔" + "═" * (W - 2) + "╗")))
    title = "Rate Limit Dashboard  ·  Dropship Mission"
    print(bold(cyan("║")) + bold(white(title.center(W - 2))) + bold(cyan("║")))
    ts = f"Checked: {now_str}"
    print(bold(cyan("║")) + dim(ts.center(W - 2)) + bold(cyan("║")))
    print(bold(cyan("╚" + "═" * (W - 2) + "╝")))
    print()

    agents = load_profiles()
    mstatus = load_model_status()
    log_events = load_recent_ratelimit_events()

    render_model_status(mstatus)
    print()
    render_provider_section(agents, "anthropic")
    print()
    render_provider_section(agents, "xai")
    print()

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    xai_key = os.environ.get("XAI_API_KEY")
    render_live_section(anthropic_key, xai_key)
    print()

    render_log_tail(log_events)
    if log_events:
        print()

    div()
    if watch:
        print(dim(f"  Auto-refreshing every {interval}s  ·  Ctrl+C to quit"))
    else:
        print(dim("  Watch mode: python3 dashboard.py -w [seconds]"))
        print(dim("  Live headers: export ANTHROPIC_API_KEY=sk-ant-api03-..."))
    print()


def main():
    args = sys.argv[1:]
    watch = "-w" in args or "--watch" in args
    interval = 30
    for a in args:
        if a not in ("-w", "--watch") and a.isdigit():
            interval = int(a)
    try:
        if watch:
            while True:
                render(watch=True, interval=interval)
                time.sleep(interval)
        else:
            render()
    except KeyboardInterrupt:
        print(f"\n{dim('  Dashboard stopped.')}\n")


if __name__ == "__main__":
    main()
