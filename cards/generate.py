#!/usr/bin/env python3
"""Generate GitHub stats + top-languages cards as static SVGs.

Data comes straight from GitHub's REST + GraphQL APIs, so nothing here
depends on github-readme-stats instances, Vercel, or any third party.
Runs locally with a token, or in Actions with the built-in GITHUB_TOKEN:

    GITHUB_TOKEN=ghp_xxx python cards/generate.py
"""

import json
import os
import sys
import urllib.request

LOGIN = "cameleonnbss"
NAME = "camzzz"
ACCENT = "#ef4444"
BG = "#0d1117"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
FONT = "Segoe UI,Ubuntu,Sans-Serif"

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    sys.exit("GITHUB_TOKEN env var is required")


def api(path_or_url, body=None):
    url = path_or_url if path_or_url.startswith("http") else "https://api.github.com" + path_or_url
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-cards",
    })
    method = "POST" if data else "GET"
    if body is not None:
        req.get_method = lambda: "POST"
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# ---------- gather data ----------
user = api(f"/users/{LOGIN}")
followers = user["followers"]

repos = []
page = 1
while True:
    chunk = api(f"/users/{LOGIN}/repos?per_page=100&page={page}&sort=updated")
    repos.extend(chunk)
    if len(chunk) < 100:
        break
    page += 1

own = [r for r in repos if not r["fork"]]
total_stars = sum(r["stargazers_count"] for r in own)
total_forks = sum(r["forks_count"] for r in own)
repo_count = len(repos)

langs = {}
for r in own:
    try:
        for lang, nbytes in api(f"/repos/{LOGIN}/{r['name']}/languages").items():
            langs[lang] = langs.get(lang, 0) + nbytes
    except Exception:
        pass

graph = api("https://api.github.com/graphql", body={
    "query": 'query($login:String!){ user(login:$login){ '
             'contributionsCollection { totalCommitContributions '
             'totalPullRequestContributions totalIssueContributions '
             'totalPullRequestReviewContributions contributionCalendar { totalContributions } } } }',
    "variables": {"login": LOGIN},
})
cc = graph["data"]["user"]["contributionsCollection"]
commits = cc["totalCommitContributions"]
prs = cc["totalPullRequestContributions"]
issues = cc["totalIssueContributions"]
reviews = cc["totalPullRequestReviewContributions"]
contribs = cc["contributionCalendar"]["totalContributions"]


# ---------- render ----------
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;")


def stat_row(y, emoji, label, value):
    return (f'<g transform="translate(0,{y})">'
            f'<text x="35" y="0" class="t">{emoji} {esc(label)}:</text>'
            f'<text x="260" y="0" class="t" style="font-weight:600">{esc(value)}</text></g>')


rows = [
    (50, "⭐", "Total Stars", total_stars),
    (80, "📝", "Total Commits (1y)", commits),
    (110, "🔀", "Total PRs (1y)", prs),
    (125 + 25, "🐛", "Total Issues (1y)", issues),
    (180, "👀", "PR Reviews (1y)", reviews),
    (210, "📦", "Contributions (1y)", contribs),
    (240, "👥", "Followers", followers),
    (270, "📚", "Repositories", repo_count),
]
rows_svg = "\n    ".join(stat_row(*r) for r in rows)

stats_svg = f'''<svg width="520" height="310" viewBox="0 0 520 310" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{NAME} GitHub stats">
  <style>
    .h {{ font: 700 18px {FONT}; fill: {ACCENT}; }}
    .t {{ font: 14px {FONT}; fill: {TEXT}; }}
    .m {{ font: 11px {FONT}; fill: {MUTED}; }}
  </style>
  <rect x="0.5" y="0.5" width="519" height="309" rx="4.5" fill="{BG}" stroke="#e4e2e2" stroke-opacity="0.2"/>
  <text x="27" y="38" class="h">{esc(NAME)}'s GitHub Stats</text>
    {rows_svg}
  <text x="27" y="298" class="m">updated by github actions - data from the github api</text>
</svg>
'''

total_bytes = sum(langs.values()) or 1
top = sorted(langs.items(), key=lambda kv: -kv[1])[:8]
bars = []
y = 78
bar_w = 320
x0 = 25
for i, (lang, nbytes) in enumerate(top):
    pct = nbytes * 100 / total_bytes
    color = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4", "#3b82f6", "#a855f7", "#ec4899"][i]
    w = max(2, round(bar_w * pct / 100))
    bars.append(f'<text x="{x0}" y="{y - 8}" class="t" style="font-weight:600;font-size:12px">{esc(lang)} {pct:.1f}%</text>')
    bars.append(f'<rect x="{x0}" y="{y}" width="{bar_w}" height="8" rx="3" fill="#21262d"/>')
    bars.append(f'<rect x="{x0}" y="{y}" width="{w}" height="8" rx="3" fill="{color}"/>')
    y += 30

langs_svg = f'''<svg width="450" height="{y + 30}" viewBox="0 0 450 {y + 30}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Top languages">
  <style>
    .h {{ font: 700 17px {FONT}; fill: {ACCENT}; }}
    .t {{ font: 13px {FONT}; fill: {TEXT}; }}
    .m {{ font: 11px {FONT}; fill: {MUTED}; }}
  </style>
  <rect x="0.5" y="0.5" width="449" height="{y + 29}" rx="4.5" fill="{BG}" stroke="#e4e2e2" stroke-opacity="0.2"/>
  <text x="25" y="38" class="h">Most Used Languages</text>
  {"".join(bars)}
  <text x="25" y="{y + 16}" class="m">by bytes of code across {len(own)} repos - updated by github actions</text>
</svg>
'''

with open(os.path.join(os.path.dirname(__file__), "stats.svg"), "w", encoding="utf-8") as f:
    f.write(stats_svg)
with open(os.path.join(os.path.dirname(__file__), "top-langs.svg"), "w", encoding="utf-8") as f:
    f.write(langs_svg)

print(f"stats: stars={total_stars} commits(1y)={commits} prs={prs} issues={issues} "
      f"reviews={reviews} contribs={contribs} followers={followers} repos={repo_count}")
print("languages:", ", ".join(f"{k} {v * 100 / total_bytes:.1f}%" for k, v in top))
print("cards written")
