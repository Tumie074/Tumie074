"""Draws themed GitHub stats + top-languages SVG cards for the profile README.
Runs in GitHub Actions with GITHUB_TOKEN; stdlib only. Use --mock to preview offline."""
import json, os, sys, urllib.request, urllib.parse
from html import escape

USER = os.environ.get("GH_USER", "Tumie074")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "assets")

BG, BORDER, TITLE, TEXT, MUTED, RING, ICON = "#100A2A", "#3A1A6E", "#5EF2FF", "#E4DCFF", "#9D92C9", "#7A48E2", "#B08CFF"
LANG_COLORS = ["#5EF2FF", "#B08CFF", "#FF78BE", "#7A48E2", "#4FB6FF", "#FFB86B", "#8CF5C1", "#E4DCFF"]
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

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
    contrib = None
    try:
        q = {"query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions}}}}",
             "variables": {"u": USER}}
        contrib = api("/graphql", q)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except Exception as e: print("graphql failed:", e)
    return {
        "stars": sum(r["stargazers_count"] for r in own),
        "repos": len(own),
        "commits": search_count(f"author:{USER}", "commits"),
        "prs": search_count(f"author:{USER} type:pr", "issues"),
        "issues": search_count(f"author:{USER} type:issue", "issues"),
        "contrib": contrib,
        "langs": langs,
    }

ICONS = {  # 16px stroke icons
    "star": '<path d="M8 1.8l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6z"/>',
    "commit": '<circle cx="8" cy="8" r="3"/><path d="M1 8h4M11 8h4"/>',
    "pr": '<circle cx="4" cy="3.5" r="1.8"/><circle cx="4" cy="12.5" r="1.8"/><circle cx="12" cy="12.5" r="1.8"/><path d="M4 5.3v5.4M12 10.7V6a2 2 0 0 0-2-2H7.5M9 2.5L7.5 4 9 5.5"/>',
    "issue": '<circle cx="8" cy="8" r="6.2"/><circle cx="8" cy="8" r="1.2"/>',
    "repo": '<path d="M3 2.5h8.5a1 1 0 0 1 1 1v10H4a1 1 0 0 1-1-1z"/><path d="M3 11.5h9.5"/>',
}

def fmt(n): return "—" if n is None else (f"{n/1000:.1f}k" if n >= 1000 else str(n))

def stats_svg(s):
    rows = [("star", "Total stars", s["stars"]), ("commit", "Commits", s["commits"]),
            ("pr", "Pull requests", s["prs"]), ("issue", "Issues", s["issues"]), ("repo", "Repositories", s["repos"])]
    W, H = 495, 195
    body = []
    for i, (ic, label, val) in enumerate(rows):
        y = 64 + i * 25
        body.append(f'<g class="row" style="animation-delay:{150 + i*120}ms" transform="translate(25,{y})">'
                    f'<g fill="none" stroke="{ICON}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">{ICONS[ic]}</g>'
                    f'<text x="26" y="12.5" class="lbl">{label}:</text><text x="200" y="12.5" class="val">{fmt(val)}</text></g>')
    ring_val, ring_lbl = (s["contrib"], "contributions") if s["contrib"] is not None else (s["commits"], "commits")
    r, cx, cy = 50, 400, 108
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
<circle cx="{cx}" cy="{cy - r}" r="4" fill="#FF78BE"/>
<text x="{cx}" y="{cy + 6}" text-anchor="middle" class="big">{fmt(ring_val)}</text>
<text x="{cx}" y="{cy + r + 24}" text-anchor="middle" class="sub">{ring_lbl}{" (last year)" if ring_lbl == "contributions" else ""}</text>
</svg>'''

def langs_svg(langs):
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

if __name__ == "__main__":
    s = ({"stars": 3, "repos": 17, "commits": 412, "prs": 9, "issues": 4, "contrib": 125,
          "langs": {"JavaScript": 52000, "C#": 41000, "Python": 30000, "HTML": 22000, "CSS": 12000, "Java": 9000, "TSQL": 6000, "C++": 2000}}
         if "--mock" in sys.argv else collect())
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "stats.svg"), "w").write(stats_svg(s))
    open(os.path.join(OUT, "top-langs.svg"), "w").write(langs_svg(s["langs"]))
    print(json.dumps({k: v for k, v in s.items() if k != "langs"}))
