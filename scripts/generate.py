#!/usr/bin/env python3
"""
Profil kartlarını üretir:
  assets/neofetch-dark.svg / neofetch-light.svg  -> ASCII yüz + bilgi kartı
  assets/radar.svg                               -> dil radarı + dil yüzdeleri + istatistikler

Kullanım:
  GITHUB_TOKEN=... GH_USER=kullaniciadi python scripts/generate.py
  python scripts/generate.py --demo        (API'ye bağlanmadan örnek veriyle)

Sadece Python standart kütüphanesi kullanır; ek kurulum gerekmez.
"""
import datetime as dt
import html
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# ─────────────────────────── KİŞİSEL BİLGİLER (buradan düzenle) ───────────────────────────
CONFIG = {
    "handle": "yigit@yiqirin",
    "birthday": dt.date(2002, 8, 21),          # Uptime satırı bundan hesaplanır. İstemezsen None yap.
    "info": [                                  # (anahtar, değer). None = boş satır
        ("OS", "macOS, Windows 11"),
        ("Uptime", "{uptime}"),
        ("Host", "Near East University"),
        ("Kernel", "Computer Engineering"),
        ("Role", "Computer & Software Engineer"),
        ("IDE", "VS Code, Xcode, Cursor, Windsurf, Antigravity"),
        None,
        ("Languages.Programming", "TypeScript, Swift, Python, C#"),
        ("Languages.Real", "Turkish, English"),
        ("Languages.Learning", "Russian, Korean"),
        None,
        ("AI.Coding", "Claude Code, Codex, Gemini CLI, Copilot"),
        ("AI.Builders", "v0, Lovable, Replit, Firebase"),
        ("AI.LLMs", "Claude, ChatGPT, Gemini, Grok, Qwen"),
        ("AI.Agents", "Hermes, OpenClaw, AionUi, n8n, Ollama"),
        ("AI.Image", "Higgsfield, Midjourney, Nano Banana"),
        ("AI.Video", "Runway, Kling, Veo, Sora, CapCut AI"),
        ("AI.Audio", "ElevenLabs, Suno"),
        None,
        ("Projects.Apps", "Stokta, FitPrep, Ca-Ching"),
        ("Projects.Web", "Booked, AKKA Trading"),
        ("Projects.Brand", "Lore Seekers"),
        ("3D.Game", "Blender, Unity, Unreal, Godot"),
    ],
    "contact": [
        ("Portfolio", "yigityazgan.vercel.app"),
        ("Email", "yiqirin@gmail.com"),
        ("LinkedIn", "yigityazgan"),
        ("X", "@loreseekerslog"),
    ],
    "show_github_stats": True,
    # Gizli repoların dil oranlarını ve sayılarını da kartlara katar (kod paylaşılmaz).
    # Çalışması için PROFILE_TOKEN gizli anahtarı 'repo' yetkili bir token olmalı.
    "include_private": True,
    "exclude_languages": [],                   # örn. ["HTML"] -> radarda sayılmaz
}

# Lore Seekers paleti
C = {
    "dark":  {"bg": "#160A0D", "border": "#7C2D3A", "key": "#C9A84C", "val": "#F0E6D2",
              "dim": "#6E5A5E", "title": "#C9A84C", "muted": "#B8A99A", "grid": "#3A2328"},
    "light": {"bg": "#FBF6EC", "border": "#C9A84C", "key": "#7C2D3A", "val": "#2B1A1D",
              "dim": "#B5A38A", "title": "#7C2D3A", "muted": "#6E5A5E", "grid": "#E5D8BF"},
}
FONT = "ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

QUERY = """
query($login: String!, $privacy: RepositoryPrivacy) {
  user(login: $login) {
    followers { totalCount }
    pullRequests { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY]) { totalCount }
    contributionsCollection { totalCommitContributions restrictedContributionsCount contributionYears }
    allRepos: repositories(ownerAffiliations: OWNER, privacy: $privacy) { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: $privacy) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


CAL_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def gql(query, variables, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_calendar(login, token, years):
    """Tüm yılların günlük katkı sayıları: {'2026-11-23': 4, ...} (gizli katkılar dahil)."""
    days = {}
    today = dt.date.today().isoformat()
    for y in sorted(years):
        res = gql(CAL_QUERY, {"login": login, "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"}, token)
        weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for w in weeks:
            for d in w["contributionDays"]:
                if d["date"] <= today:
                    days[d["date"]] = d["contributionCount"]
    return days


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login, "privacy": None if CONFIG.get("include_private") else "PUBLIC"}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    if not res.get("data") or not res["data"].get("user"):
        sys.exit(f"GitHub API hatası: {res.get('errors')}")
    u = res["data"]["user"]
    langs = {}
    stars = 0
    for repo in u["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            if n in CONFIG["exclude_languages"]:
                continue
            langs.setdefault(n, {"size": 0, "color": e["node"]["color"] or "#8b949e"})
            langs[n]["size"] += e["size"]
    cc = u["contributionsCollection"]
    return {
        "repos": u["allRepos"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "stars": stars,
        "commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
        "prs": u["pullRequests"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "languages": langs,
        "calendar": fetch_calendar(login, token, cc.get("contributionYears") or [dt.date.today().year]),
    }


DEMO = {
    "repos": 12, "contributed": 4, "stars": 9, "commits": 214, "prs": 6, "followers": 15,
    "languages": {
        "TypeScript": {"size": 420000, "color": "#3178c6"}, "C#": {"size": 260000, "color": "#178600"},
        "C++": {"size": 150000, "color": "#f34b7d"}, "Python": {"size": 90000, "color": "#3572A5"},
        "HTML": {"size": 70000, "color": "#e34c26"}, "CSS": {"size": 30000, "color": "#663399"},
    },
}
import random as _r
_r.seed(7)
DEMO["calendar"] = {(dt.date.today() - dt.timedelta(days=i)).isoformat(): (_r.choice([0, 0, 1, 2, 3, 5, 8]) if i > 6 else _r.randint(1, 6)) for i in range(400)}



def uptime(bday):
    t = dt.date.today()
    y = t.year - bday.year - ((t.month, t.day) < (bday.month, bday.day))
    last = bday.replace(year=bday.year + y)
    m = (t.year - last.year) * 12 + t.month - last.month - (t.day < last.day)
    mm = last.month - 1 + m
    anchor = last.replace(year=last.year + mm // 12, month=mm % 12 + 1)
    d = (t - anchor).days
    s = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{s(y, 'year')}, {s(m, 'month')}, {s(d, 'day')}"


esc = lambda s: html.escape(str(s), quote=True)


# ─────────────────────────────── NEOFETCH KARTI ───────────────────────────────
def neofetch(stats, ascii_rows, mode):
    p = C[mode]
    fs, lh, cw = 15, 19, 9.0          # font boyu, satır yüksekliği, karakter genişliği
    width_chars = 58                  # sağ blok genişliği (karakter)
    pad = 24
    afs, alh, acw = 12, 13.6, 7.2   # ASCII bloğu için daha küçük yazı
    ascii_w = len(ascii_rows[0]) * acw
    rx = pad + ascii_w + 28           # sağ blok x
    W = int(rx + width_chars * cw + pad)

    rows = []  # her satır: list of (text, color)
    def header(title):
        line = f"{title} "
        rows.append([(line, p["val"]), ("—" * (width_chars - len(line) - 2), p["dim"]), ("-—-", p["dim"])])
    def kv(k, v):
        dots = width_chars - len(k) - len(v) - 6
        rows.append([(". ", p["dim"]), (k, p["key"]), (":", p["val"]),
                     (" " + "." * max(dots, 2) + " ", p["dim"]), (v, p["val"])])
    def blank():
        rows.append([(". ", p["dim"])])

    header(CONFIG["handle"])
    for item in CONFIG["info"]:
        if item is None:
            blank(); continue
        k, v = item
        if "{uptime}" in v:
            if not CONFIG["birthday"]:
                continue
            v = uptime(CONFIG["birthday"])
        kv(k, v)
    blank()
    header("- Contact")
    for k, v in CONFIG["contact"]:
        kv(k, v)
    # iki sütunlu istatistik satırları
    def pair(k1, v1, k2, v2):
        left_w = 30
        d1 = left_w - len(k1) - len(v1) - 6
        d2 = width_chars - left_w - len(k2) - len(v2) - 6
        rows.append([(". ", p["dim"]), (k1, p["key"]), (":", p["val"]), (" " + "." * max(d1, 2) + " ", p["dim"]),
                     (v1, p["val"]), (" | ", p["val"]), (k2, p["key"]), (":", p["val"]),
                     (" " + "." * max(d2, 2) + " ", p["dim"]), (v2, p["val"])])
    if CONFIG.get("show_github_stats", True):
        blank()
        header("- GitHub Stats")
        pair("Repos", f"{stats['repos']} {{+{stats['contributed']}}}", "Stars", str(stats["stars"]))
        pair("Commits/yr", str(stats["commits"]), "Followers", str(stats["followers"]))

    info_h, ascii_h = len(rows) * lh, len(ascii_rows) * alh
    H = int(pad * 2 + max(info_h, ascii_h))
    ascii_top = pad + (max(info_h, ascii_h) - ascii_h) / 2
    info_top = pad + (max(info_h, ascii_h) - info_h) / 2

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="{FONT}" font-size="{fs}px">',
           f'<style>text{{white-space:pre}}</style>',
           f'<rect width="{W}" height="{H}" rx="14" fill="{p["bg"]}" stroke="{p["border"]}" stroke-width="1.5"/>']
    # ASCII
    for i, row in enumerate(ascii_rows):
        y = ascii_top + (i + 0.8) * alh
        spans = []
        for j, (ch, col) in enumerate(row):
            if ch == " ":
                continue
            fill = col if mode == "dark" else darken(col)
            spans.append(f'<tspan x="{pad + j*acw:.1f}" fill="{fill}">{esc(ch)}</tspan>')
        out.append(f'<text y="{y:.1f}" font-size="{afs}px" font-weight="700">{"".join(spans)}</text>')
    # bilgi bloğu
    for i, row in enumerate(rows):
        y = info_top + (i + 0.8) * lh
        spans = "".join(f'<tspan fill="{col}">{esc(t)}</tspan>' for t, col in row)
        out.append(f'<text x="{rx:.1f}" y="{y:.1f}" xml:space="preserve">{spans}</text>')
    out.append("</svg>")
    return "\n".join(out)


def darken(hex_):
    r, g, b = (int(hex_[i:i+2], 16) for i in (1, 3, 5))
    f = 0.55
    return "#%02x%02x%02x" % (int(r*f), int(g*f), int(b*f))


# ─────────────────────────────── RADAR KARTI ───────────────────────────────
def radar(stats):
    p = C["dark"]
    langs = sorted(stats["languages"].items(), key=lambda kv: -kv[1]["size"])[:5]
    total = sum(v["size"] for _, v in langs) or 1
    W, H = 920, 470
    g = 16
    cw = (W - 3 * g) / 2
    ch = 300
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{SANS}">',
           ]
    def card(x, y, w, h):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{p["bg"]}" stroke="{p["border"]}" stroke-width="1.5"/>')

    # 1) Radar
    x0, y0 = g, g
    card(x0, y0, cw, ch)
    out.append(f'<text x="{x0+22}" y="{y0+36}" fill="{p["title"]}" font-size="18" font-weight="600">Language Radar</text>')
    cx, cy, R = x0 + cw / 2, y0 + 165, 86
    n = max(len(langs), 3)
    ang = lambda i: -math.pi / 2 + 2 * math.pi * i / n
    for lvl in (0.25, 0.5, 0.75, 1):
        pts = " ".join(f"{cx + R*lvl*math.cos(ang(i)):.1f},{cy + R*lvl*math.sin(ang(i)):.1f}" for i in range(n))
        out.append(f'<polygon points="{pts}" fill="none" stroke="{p["grid"]}" stroke-width="1"/>')
    for i in range(n):
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + R*math.cos(ang(i)):.1f}" y2="{cy + R*math.sin(ang(i)):.1f}" stroke="{p["grid"]}"/>')
    if not langs:
        out.append(f'<text x="{cx}" y="{cy}" fill="{p["muted"]}" font-size="14" text-anchor="middle">No language data yet</text>')
    mx = max((v["size"] for _, v in langs), default=1)
    vals = [math.sqrt(v["size"] / mx) for _, v in langs] + [0] * (n - len(langs))
    pts = [(cx + R*max(v, .06)*math.cos(ang(i)), cy + R*max(v, .06)*math.sin(ang(i))) for i, v in enumerate(vals)]
    if langs:
        out.append(f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" fill="{p["key"]}" fill-opacity=".22" stroke="{p["key"]}" stroke-width="2"/>')
        for a, b in pts:
            out.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4" fill="{p["key"]}"/>')
    for i, (name, _) in enumerate(langs):
        lx, ly = cx + (R + 22) * math.cos(ang(i)), cy + (R + 22) * math.sin(ang(i))
        anchor = "middle" if abs(math.cos(ang(i))) < .3 else ("start" if math.cos(ang(i)) > 0 else "end")
        out.append(f'<text x="{lx:.1f}" y="{ly + 5:.1f}" fill="{p["val"]}" font-size="14" text-anchor="{anchor}">{esc(name)}</text>')
    out.append(f'<text x="{x0+22}" y="{y0+ch-18}" fill="{p["muted"]}" font-size="12">Share of code by language, square-root scale</text>')

    # 2) Top languages
    x1 = g * 2 + cw
    card(x1, y0, cw, ch)
    out.append(f'<text x="{x1+22}" y="{y0+36}" fill="{p["title"]}" font-size="18" font-weight="600">Top Languages</text>')
    bx, bw = x1 + 22, cw - 44
    out.append(f'<clipPath id="bar"><rect x="{bx}" y="{y0+54}" width="{bw}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">')
    acc = 0
    for name, v in langs:
        w = bw * v["size"] / total
        out.append(f'<rect x="{bx+acc:.1f}" y="{y0+54}" width="{w+0.5:.1f}" height="10" fill="{v["color"]}"/>')
        acc += w
    out.append("</g>")
    for i, (name, v) in enumerate(langs):
        ry = y0 + 96 + i * 40
        pct = 100 * v["size"] / total
        pct_s = f"{pct:.0f}%" if pct >= 10 else f"{pct:.1f}%"
        out.append(f'<circle cx="{bx+7}" cy="{ry-5}" r="6" fill="{v["color"]}"/>')
        out.append(f'<text x="{bx+22}" y="{ry}" fill="{p["val"]}" font-size="15">{esc(name)}</text>')
        out.append(f'<text x="{bx+bw}" y="{ry}" fill="{p["key"]}" font-size="15" text-anchor="end">{pct_s}</text>')
        out.append(f'<rect x="{bx}" y="{ry+9}" width="{bw}" height="5" rx="2.5" fill="{p["grid"]}"/>')
        out.append(f'<rect x="{bx}" y="{ry+9}" width="{max(bw*pct/100, 5):.1f}" height="5" rx="2.5" fill="{v["color"]}"/>')
    out.append(f'<text x="{bx}" y="{y0+ch-18}" fill="{p["muted"]}" font-size="12">updated {dt.date.today().isoformat()}</text>')

    # 3) İstatistik şeridi
    sy, sh = y0 + ch + g, H - (y0 + ch + g) - g
    card(g, sy, W - 2 * g, sh)
    items = [("Repositories", stats["repos"]), ("Commits (last year)", stats["commits"]),
             ("Pull Requests", stats["prs"]), ("Stars Earned", stats["stars"])]
    colw = (W - 2 * g) / 4
    for i, (label, val) in enumerate(items):
        tx = g + i * colw + 24
        if i:
            out.append(f'<line x1="{g + i*colw:.1f}" y1="{sy+22}" x2="{g + i*colw:.1f}" y2="{sy+sh-22}" stroke="{p["grid"]}"/>')
        out.append(f'<text x="{tx:.1f}" y="{sy+40}" fill="{p["muted"]}" font-size="14">{label}</text>')
        out.append(f'<text x="{tx:.1f}" y="{sy+84}" fill="{p["key"]}" font-size="36" font-weight="600">{val}</text>')
    out.append("</svg>")
    return "\n".join(out)


def streak_stats(cal):
    dates = sorted(cal)
    total = sum(cal.values())
    first = next((d for d in dates if cal[d] > 0), dates[0] if dates else dt.date.today().isoformat())
    # en uzun seri
    best = cur = 0; best_end = best_start = None; run_start = None
    for d in dates:
        if cal[d] > 0:
            if cur == 0:
                run_start = d
            cur += 1
            if cur > best:
                best, best_start, best_end = cur, run_start, d
        else:
            cur = 0
    # güncel seri (bugün henüz katkı yoksa dünden geriye sayılır)
    today = dt.date.today()
    day = today if cal.get(today.isoformat(), 0) > 0 else today - dt.timedelta(days=1)
    cur_len, cur_end = 0, day
    while cal.get(day.isoformat(), 0) > 0:
        cur_len += 1
        day -= dt.timedelta(days=1)
    cur_start = day + dt.timedelta(days=1)
    return {"total": total, "first": first, "current": cur_len, "cur_start": cur_start.isoformat(),
            "cur_end": cur_end.isoformat(), "longest": best, "best_start": best_start, "best_end": best_end}


def fmt_date(iso, year=True):
    if not iso:
        return "-"
    d = dt.date.fromisoformat(iso)
    return d.strftime("%b %-d, %Y") if year else d.strftime("%b %-d")


def streak_card(stats):
    p = C["dark"]
    st = streak_stats(stats["calendar"])
    W, H = 920, 220
    col = W / 3
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{SANS}">',
           f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="14" fill="{p["bg"]}" stroke="{p["border"]}" stroke-width="1.5"/>']
    for i in (1, 2):
        out.append(f'<line x1="{col*i:.1f}" y1="34" x2="{col*i:.1f}" y2="{H-34}" stroke="{p["border"]}"/>')
    def same_year(a, b):
        return a and b and a[:4] == b[:4] == str(dt.date.today().year)
    cur_range = (f'{fmt_date(st["cur_start"], False)} - {fmt_date(st["cur_end"], False)}' if st["current"] > 1
                 else fmt_date(st["cur_end"], False) if st["current"] == 1 else "No active streak")
    best_range = (f'{fmt_date(st["best_start"], not same_year(st["best_start"], st["best_end"]))} - '
                  f'{fmt_date(st["best_end"], not same_year(st["best_start"], st["best_end"]))}') if st["longest"] > 1 else fmt_date(st["best_end"])
    cols = [(st["total"], "Total Contributions", f'{fmt_date(st["first"])} - Present'),
            (st["current"], "Current Streak", cur_range),
            (st["longest"], "Longest Streak", best_range)]
    for i, (num, label, sub) in enumerate(cols):
        cx = col * i + col / 2
        if i == 1:
            out.append(f'<circle cx="{cx:.1f}" cy="82" r="44" fill="none" stroke="{p["key"]}" stroke-width="5"/>')
            out.append(f'<path d="M{cx:.1f} 26 c-9 10 -12 16 -5 23 c3 3 10 3 12 -3 c3 -7 -2 -12 -7 -20 z" fill="{p["key"]}"/>')
            out.append(f'<text x="{cx:.1f}" y="96" fill="{p["val"]}" font-size="38" font-weight="700" text-anchor="middle">{num}</text>')
            out.append(f'<text x="{cx:.1f}" y="160" fill="{p["key"]}" font-size="18" font-weight="700" text-anchor="middle">{label}</text>')
            out.append(f'<text x="{cx:.1f}" y="188" fill="{p["muted"]}" font-size="14" text-anchor="middle">{esc(sub)}</text>')
        else:
            out.append(f'<text x="{cx:.1f}" y="96" fill="{p["val"]}" font-size="40" font-weight="700" text-anchor="middle">{num}</text>')
            out.append(f'<text x="{cx:.1f}" y="140" fill="{p["key"]}" font-size="18" text-anchor="middle">{label}</text>')
            out.append(f'<text x="{cx:.1f}" y="168" fill="{p["muted"]}" font-size="14" text-anchor="middle">{esc(sub)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def activity_card(stats, days=31):
    p = C["dark"]
    today = dt.date.today()
    series = [(today - dt.timedelta(days=days - 1 - i)) for i in range(days)]
    vals = [stats["calendar"].get(d.isoformat(), 0) for d in series]
    W, H = 920, 320
    L, R, T, B = 56, 24, 56, 56
    pw, ph = W - L - R, H - T - B
    mx = max(max(vals), 1)
    step = max(1, math.ceil(mx / 4))
    top = step * 4
    X = lambda i: L + pw * i / (days - 1)
    Y = lambda v: T + ph * (1 - v / top)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{SANS}">',
           f'<rect width="{W}" height="{H}" rx="14" fill="{p["bg"]}"/>',
           f'<text x="{W/2}" y="34" fill="{p["key"]}" font-size="17" font-weight="700" text-anchor="middle">Contributions · last {days} days · {sum(vals)} total</text>']
    for k in range(5):
        v = step * k
        out.append(f'<line x1="{L}" y1="{Y(v):.1f}" x2="{W-R}" y2="{Y(v):.1f}" stroke="{p["grid"]}" stroke-dasharray="3 4"/>')
        out.append(f'<text x="{L-10}" y="{Y(v)+4:.1f}" fill="{p["muted"]}" font-size="12" text-anchor="end">{v}</text>')
    pts = [(X(i), Y(v)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out.append(f'<polygon points="{L},{Y(0):.1f} {line} {W-R},{Y(0):.1f}" fill="{p["border"]}" fill-opacity=".55"/>')
    out.append(f'<polyline points="{line}" fill="none" stroke="{p["key"]}" stroke-width="2.5" stroke-linejoin="round"/>')
    for (x, y), d in zip(pts, series):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{p["val"]}"/>')
        out.append(f'<text x="{x:.1f}" y="{H-B+20}" fill="{p["muted"]}" font-size="11" text-anchor="middle">{d.day}</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    if "--demo" in sys.argv:
        stats = DEMO
    else:
        token, login = os.environ.get("GITHUB_TOKEN"), os.environ.get("GH_USER")
        if not token or not login:
            sys.exit("GITHUB_TOKEN ve GH_USER ortam değişkenleri gerekli (ya da --demo kullan).")
        stats = fetch(login, token)
    ascii_rows = json.load(open(ASSETS / "ascii.json"))
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "neofetch-dark.svg").write_text(neofetch(stats, ascii_rows, "dark"), encoding="utf-8")
    (ASSETS / "neofetch-light.svg").write_text(neofetch(stats, ascii_rows, "light"), encoding="utf-8")
    (ASSETS / "radar.svg").write_text(radar(stats), encoding="utf-8")
    (ASSETS / "streak.svg").write_text(streak_card(stats), encoding="utf-8")
    (ASSETS / "activity.svg").write_text(activity_card(stats), encoding="utf-8")
    print("OK:", {k: v for k, v in stats.items() if k not in ("languages", "calendar")}, streak_stats(stats["calendar"]), list(stats["languages"])[:5])


if __name__ == "__main__":
    main()
