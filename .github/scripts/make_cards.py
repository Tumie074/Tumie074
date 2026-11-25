"""Draws themed GitHub stats, top-languages and contribution-streak SVG cards for the profile README.
Runs in GitHub Actions with GITHUB_TOKEN; stdlib only. Use --mock to preview offline."""
import datetime as dt, json, os, sys, urllib.request, urllib.parse
from html import escape

USER = os.environ.get("GH_USER", "Tumie074")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "assets")

BG, BORDER, TITLE, TEXT, MUTED, RING, ICON, PINK = "#100A2A", "#3A1A6E", "#5EF2FF", "#E4DCFF", "#9D92C9", "#7A48E2", "#B08CFF", "#FF78BE"
LANG_COLORS = ["#5EF2FF", "#B08CFF", "#FF78BE", "#7A48E2", "#4FB6FF", "#FFB86B", "#8CF5C1", "#E4DCFF"]
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

# Markup, styling, config and notebook formats are left out so the card shows real programming languages.
SKIP_LANGS = {"HTML", "CSS", "SCSS", "Sass", "Less", "HCL", "Dockerfile", "Makefile", "Shell", "PowerShell",
              "Batchfile", "Procfile", "Jupyter Notebook", "Smarty", "Mustache", "Handlebars", "EJS", "Twig"}

def api(path, data=None):
    url = path if path.startswith("http") else "https://api.github.com" + path
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "profile-cards",
                 **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def search_count(q, kind):
    try: return api(f"/search/{kind}?q=" + urllib.parse.quote(q) + "&per_page=1")["total_count"]
    except Exception as e: print("search failed:", q, e); return None

def calendar_days():
    """Every day since the account was created, as [(date, count)], oldest first."""
    q_user = {"query": "query($u:String!){user(login:$u){createdAt}}", "variables": {"u": USER}}
    created = dt.date.fromisoformat(api("/graphql", q_user)["data"]["user"]["createdAt"][:10])
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=2))).date()   # SAST
    days, start = {}, created
    while start <= today:
        end = min(start + dt.timedelta(days=364), today)
        q = {"query": """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t){
               contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}""",
             "variables": {"u": USER, "f": f"{start}T00:00:00Z", "t": f"{end}T23:59:59Z"}}
        weeks = api("/graphql", q)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        for w in weeks:
            for d in w["contributionDays"]:
                day = dt.date.fromisoformat(d["date"])
                if created <= day <= today: days[day] = d["contributionCount"]
        start = end + dt.timedelta(days=1)
    return sorted(days.items())

def streaks(days):
    total = sum(c for _, c in days)
    best, best_span, run, run_start = 0, None, 0, None
    for day, c in days:
        if c > 0:
            if run == 0: run_start = day
            run += 1
            if run > best: best, best_span = run, (run_start, day)
        else:
            run = 0
    # current streak: today counts if active; a quiet "today so far" doesn't break it
    cur, cur_start = 0, None
    seq = list(days)
    if seq and seq[-1][1] == 0: seq = seq[:-1]
    for day, c in reversed(seq):
        if c == 0: break
        cur, cur_start = cur + 1, day
    year = days[-1][0].year if days else dt.date.today().year
    this_year = sum(c for d, c in days if d.year == year)
    return {"total": total, "since": days[0][0] if days else None, "best": best, "best_span": best_span,
            "cur": cur, "cur_start": cur_start, "this_year": this_year, "year": year,
            "active_days": sum(1 for _, c in days if c > 0)}

def collect():
    repos, page = [], 1
    while True:
        batch = api(f"/users/{USER}/repos?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100: break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = {}
    for r in own:
        try:
            for k, v in api(r["languages_url"]).items(): langs[k] = langs.get(k, 0) + v
        except Exception as e: print("langs failed:", r["name"], e)
    st = None
    try: st = streaks(calendar_days())
    except Exception as e: print("calendar failed:", e)
    return {
        "stars": sum(r["stargazers_count"] for r in own),
        "repos": len(own),
        "commits": search_count(f"author:{USER}", "commits"),
        "prs": search_count(f"author:{USER} type:pr", "issues"),
        "issues": search_count(f"author:{USER} type:issue", "issues"),
        "streak": st,
        "langs": langs,
    }

ICONS = {  # 16px stroke icons
    "star": '<path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z"/>',
    "commit": '<circle cx="8" cy="8" r="3"/><path d="M1 8h4M11 8h4"/>',
    "pr": '<circle cx="4" cy="3.5" r="1.8"/><circle cx="4" cy="12.5" r="1.8"/><circle cx="12" cy="12.5" r="1.8"/><path d="M4 5.3v5.4M12 10.7V6a2 2 0 0 0-2-2H7.5M9 2.5L7.5 4 9 5.5"/>',
    "issue": '<circle cx="8" cy="8" r="6.2"/><circle cx="8" cy="8" r="1.2"/>',
    "repo": '<path d="M3 2.5h8.5a1 1 0 0 1 1 1v10H4a1 1 0 0 1-1-1z"/><path d="M3 11.5h9.5"/>',
    "day": '<rect x="2" y="3" width="12" height="11" rx="1.5"/><path d="M2 6.5h12M5.5 1.5v3M10.5 1.5v3"/>',
}

def fmt(n): return "—" if n is None else (f"{n/1000:.1f}k" if n >= 1000 else str(n))
def d(x): return x.strftime("%-d %b %Y") if x else ""

def stats_svg(s):
    st = s.get("streak") or {}
    rows = [("commit", "Commits", s["commits"]), ("pr", "Pull requests", s["prs"]), ("issue", "Issues", s["issues"]),
            ("star", "Total stars", s["stars"]), ("repo", "Repositories", s["repos"])]
    rows = [r for r in rows if r[2]][:5]            # zero or unknown values are left out
    W, H = 495, 195
    top = 56 + (5 - len(rows)) * 12.5               # keep the rows centred
    body = []
    for i, (ic, label, val) in enumerate(rows):
        y = top + i * 25
        body.append(f'<g class="row" style="animation-delay:{150 + i*120}ms" transform="translate(25,{y})">'
                    f'<g fill="none" stroke="{ICON}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">{ICONS[ic]}</g>'
                    f'<text x="26" y="12.5" class="lbl">{label}:</text><text x="200" y="12.5" class="val">{fmt(val)}</text></g>')
    ring_val = st.get("total") if st.get("total") else s["commits"]
    ring_lbl = "total contributions" if st.get("total") else "commits"
    r, cx, cy = 50, 400, 102
    circ = 2 * 3.14159 * r
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(USER)} GitHub stats">
<style>
.ttl{{font:700 18px {FONT};fill:{TITLE}}} .lbl{{font:600 14px {FONT};fill:{TEXT}}} .val{{font:700 14px {FONT};fill:{TEXT}}}
.big{{font:800 26px {FONT};fill:{TITLE}}} .sub{{font:600 11px {FONT};fill:{MUTED}}}
.row{{opacity:0;animation:fade .5s ease-out forwards}} @keyframes fade{{to{{opacity:1}}}}
.arc{{stroke-dasharray:{circ:.1f};stroke-dashoffset:{circ:.1f};animation:fill 1.4s ease-out .3s forwards}} @keyframes fill{{to{{stroke-dashoffset:{circ*0.18:.1f}}}}}
</style>
<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text x="25" y="38" class="ttl">Itumeleng’s GitHub Stats</text>
{''.join(body)}
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{BORDER}" stroke-width="7"/>
<circle class="arc" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{RING}" stroke-width="7" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
<circle cx="{cx}" cy="{cy - r}" r="4" fill="{PINK}"/>
<text x="{cx}" y="{cy + 9}" text-anchor="middle" class="big">{fmt(ring_val)}</text>
<text x="{cx}" y="{cy + r + 22}" text-anchor="middle" class="sub">{ring_lbl}</text>
</svg>'''

def langs_svg(langs):
    langs = {k: v for k, v in langs.items() if k not in SKIP_LANGS and v > 0}
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:8]
    total = sum(v for _, v in top) or 1
    W = 350; rows = (len(top) + 1) // 2; H = max(195, 90 + rows * 24)
    bar, x = [], 25
    for i, (name, v) in enumerate(top):
        w = 300 * v / total
        bar.append(f'<rect x="{x:.2f}" y="52" width="{max(w,0.5):.2f}" height="9" fill="{LANG_COLORS[i]}"/>'); x += w
    legend = []
    for i, (name, v) in enumerate(top):
        cx = 25 + (i % 2) * 155; y = 86 + (i // 2) * 24
        legend.append(f'<g class="row" style="animation-delay:{200 + i*90}ms"><circle cx="{cx+5}" cy="{y-4}" r="5" fill="{LANG_COLORS[i]}"/>'
                      f'<text x="{cx+16}" y="{y}" class="lbl">{escape(name)} <tspan class="pct">{100*v/total:.1f}%</tspan></text></g>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Most used languages">
<style>
.ttl{{font:700 18px {FONT};fill:{TITLE}}} .lbl{{font:600 12px {FONT};fill:{TEXT}}} .pct{{fill:{MUTED}}}
.row{{opacity:0;animation:fade .5s ease-out forwards}} @keyframes fade{{to{{opacity:1}}}}
</style>
<defs><clipPath id="bar"><rect x="25" y="52" width="300" height="9" rx="4.5"/></clipPath></defs>
<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<text x="25" y="38" class="ttl">Most Used Languages</text>
<g clip-path="url(#bar)">{''.join(bar)}</g>
{''.join(legend)}
</svg>'''

def streak_svg(st):
    """Three panels: total contributions · current streak (or this year if the streak is 0) · longest streak."""
    W, H = 855, 195
    if st["cur"] > 0:
        mid_val, mid_lbl, mid_sub = st["cur"], "Current Streak", f'{d(st["cur_start"])} – today'
    else:
        mid_val, mid_lbl, mid_sub = st["this_year"], f'Contributions in {st["year"]}', "this year so far"
    left = (fmt(st["total"]), "Total Contributions", f'{d(st["since"])} – present')
    right = (fmt(st["best"]), "Longest Streak", f'{d(st["best_span"][0])} – {d(st["best_span"][1])}' if st["best_span"] else "")
    def side(x, v, l, sub):
        return (f'<text x="{x}" y="84" text-anchor="middle" class="num">{v}</text>'
                f'<text x="{x}" y="122" text-anchor="middle" class="lbl">{l}</text>'
                f'<text x="{x}" y="150" text-anchor="middle" class="sub">{sub}</text>')
    r, cx, cy = 40, W / 2, 72
    circ = 2 * 3.14159 * r
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Contributions and streaks">
<style>
.num{{font:800 30px {FONT};fill:{TEXT}}} .cnum{{font:800 28px {FONT};fill:{TITLE}}}
.lbl{{font:600 15px {FONT};fill:{ICON}}} .clbl{{font:700 15px {FONT};fill:{TITLE}}} .sub{{font:500 12px {FONT};fill:{MUTED}}}
.p{{opacity:0;animation:fade .6s ease-out forwards}} @keyframes fade{{to{{opacity:1}}}}
.arc{{stroke-dasharray:{circ:.1f};stroke-dashoffset:{circ:.1f};animation:fill 1.2s ease-out .4s forwards}} @keyframes fill{{to{{stroke-dashoffset:0}}}}
</style>
<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="10" fill="{BG}" stroke="{BORDER}"/>
<line x1="{W/3:.0f}" y1="28" x2="{W/3:.0f}" y2="{H-28}" stroke="{BORDER}" stroke-width="1.5"/>
<line x1="{2*W/3:.0f}" y1="28" x2="{2*W/3:.0f}" y2="{H-28}" stroke="{BORDER}" stroke-width="1.5"/>
<g class="p" style="animation-delay:.1s">{side(W/6, *left)}</g>
<g class="p" style="animation-delay:.3s">
<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{BORDER}" stroke-width="6"/>
<circle class="arc" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{RING}" stroke-width="6" stroke-linecap="round" transform="rotate(-90 {cx} {cy})"/>
<path d="M{cx} {cy-r-14} c5 5 7 9 4 13 c-2 3-8 3-9-1 c-1-3 1-5 2-7 c0 2 1 3 2 3 c1-3 0-5 1-8z" fill="{PINK}"/>
<text x="{cx}" y="{cy+10}" text-anchor="middle" class="cnum">{fmt(mid_val)}</text>
<text x="{cx}" y="{cy+r+30}" text-anchor="middle" class="clbl">{mid_lbl}</text>
<text x="{cx}" y="{cy+r+56}" text-anchor="middle" class="sub">{mid_sub}</text>
</g>
<g class="p" style="animation-delay:.5s">{side(5*W/6, *right)}</g>
</svg>'''

if __name__ == "__main__":
    if "--mock" in sys.argv:
        start = dt.date(2024, 7, 10); today = dt.date(2026, 11, 25)
        import random; rnd = random.Random(2)
        days = [(start + dt.timedelta(i), rnd.choice([0, 0, 0, 0, 0, 0, 0, 0, 1, 2])) for i in range((today - start).days + 1)]
        days[-1] = (today, 0); days[-2] = (today - dt.timedelta(1), 0)
        s = {"stars": 1, "repos": 21, "commits": 71, "prs": 3, "issues": 0, "streak": streaks(days),
             "langs": {"Python": 33.5, "HTML": 24.8, "Java": 18.1, "TSQL": 6.9, "C++": 4.9, "C#": 4.2, "HCL": 4.0, "CSS": 3.7}}
    else:
        s = collect()
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "stats.svg"), "w").write(stats_svg(s))
    open(os.path.join(OUT, "top-langs.svg"), "w").write(langs_svg(s["langs"]))
    if s.get("streak"):
        open(os.path.join(OUT, "streak.svg"), "w").write(streak_svg(s["streak"]))
    print(json.dumps({k: (v if k != "streak" else {kk: str(vv) for kk, vv in (v or {}).items()}) for k, v in s.items() if k != "langs"}))
