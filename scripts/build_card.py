#!/usr/bin/env python3
"""Build the profile card: one SVG that looks like a small copy of loonuh.dev.

Usage: GITHUB_TOKEN=... python3 scripts/build_card.py [snake.svg] [out.svg]

Live numbers (languages, repo count) come from the GitHub GraphQL API.
Everything else is static copy below. Images are inlined as data URIs because
an SVG shown through <img> is not allowed to load anything external.
"""
import base64
import html
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

USER = "LooNuH-dev"
ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT = 880, 1280
HIDDEN_LANGS = {"Procfile", "Shell", "Batchfile", "Makefile", "Dockerfile"}

PROJECTS = [
    ("SnapCode", "live", "QR guest services for hotels and rentals. four services, one Postgres.",
     ["Go", "FastAPI", "Next.js"]),
    ("RentaGrad", "live", "multilingual property management site for the Montenegrin market.",
     ["React", "Vite", "Cloudflare"]),
    ("Loom", "cooking", "native music player for macOS & iOS that syncs between devices over Bonjour.",
     ["Swift", "SwiftUI", "C++"]),
    ("danser-mac", "open source", "macOS port of danser-go, universal build for Apple Silicon & Intel.",
     ["Go", "macOS"]),
]
STACK = ["TypeScript", "Python", "Go", "Swift", "C / C++", "React", "Next.js", "FastAPI",
         "PostgreSQL", "Docker", "Cloudflare", "ESP32", "nRF52"]
TYPED = ["fullstack & embedded dev from Montenegro",
         "from bare-metal C to Next.js",
         "currently building a music player",
         "powered by baguettes"]


def gql(query, variables):
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]


def fetch_stats():
    q = """query($login:String!){ user(login:$login){
      repositories(ownerAffiliations:OWNER, isFork:false, first:100){
        totalCount
        nodes{ languages(first:12, orderBy:{field:SIZE, direction:DESC}){
          edges{ size node{ name color } } } } } } }"""
    data = gql(q, {"login": USER})
    if data is None:
        print("no GITHUB_TOKEN, using placeholder numbers", file=sys.stderr)
        return {"repos": 0, "langs": [("Swift", 60, "#F05138"), ("C", 20, "#555555"),
                                                     ("Go", 10, "#00ADD8"), ("Python", 10, "#3572A5")]}
    u = data["user"]
    totals, colors = {}, {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            if name in HIDDEN_LANGS:
                continue
            totals[name] = totals.get(name, 0) + e["size"]
            colors[name] = e["node"]["color"] or "#8e8e96"
    total = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    langs = [(n, s * 100 / total, colors[n]) for n, s in top]
    rest = 100 - sum(p for _, p, _ in langs)
    if rest > 0.5:
        langs.append(("other", rest, "#3a3a42"))
    return {
        "repos": u["repositories"]["totalCount"],
        "langs": langs,
    }


def data_uri(path, mime):
    return f"data:{mime};base64,{base64.b64encode(Path(path).read_bytes()).decode()}"


def inline_snake(path):
    """Paste the snake SVG in as markup. Nested as an <img> it renders as a
    still frame: browsers do not run animations inside an image inside an image."""
    if not path or not Path(path).exists():
        return ""
    svg = Path(path).read_text(encoding="utf-8")
    svg = re.sub(r"<\?xml[^>]*>\s*", "", svg)
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg.split(">", 1)[0], count=2) + ">" + svg.split(">", 1)[1]
    # Move the snake cell by cell instead of gliding. A smooth snake changes
    # every frame, and each change repaints the whole card (~3x the raster
    # work), which makes the page lag. Stepping needs one keyframe per cell,
    # so straight runs that snk writes as a single keyframe get expanded.
    svg = re.sub(r"@keyframes (s\d+)\{(.*?)\}\}", lambda m: step_keyframes(m[1], m[2]), svg)
    svg = re.sub(r"\blinear\b", "steps(1,end)", svg)
    # Drop the progress bar under the grid and the empty band it leaves.
    svg = re.sub(r'<rect class="u[^>]*/>', "", svg)
    svg = re.sub(r'viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"',
                 lambda m: f'viewBox="{m[1]} {m[2]} {m[3]} {float(m[4]) - 40:g}"', svg, count=1)
    return svg.replace("<svg ", '<svg class="snake" ', 1)


def step_keyframes(name, body):
    frames = []
    for sel, x, y in re.findall(r"([\d.,%]+)\{transform:translate\((-?[\d.]+)px,(-?[\d.]+)px\)\}", body + "}"):
        for pct in sel.split(","):
            frames.append((float(pct.rstrip("%")), float(x), float(y)))
    frames.sort()
    out = []
    for (p0, x0, y0), (p1, x1, y1) in zip(frames, frames[1:]):
        n = max(1, round((abs(x1 - x0) + abs(y1 - y0)) / 16))
        for k in range(n):
            t = k / n
            out.append((p0 + (p1 - p0) * t, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append(frames[-1])
    steps = "".join(f"{p:.4g}%{{transform:translate({x:g}px,{y:g}px)}}" for p, x, y in out)
    return f"@keyframes {name}{{{steps}}}"


def e(s):
    return html.escape(s, quote=True)


def build(stats, snake_path):
    teto = data_uri(ROOT / "src/gif/kasane-teto.gif", "image/gif")
    snake = inline_snake(snake_path)

    typed = "".join(
        f'<span class="t" style="--n:{len(t)};animation-delay:{i * 4}s;'
        f'animation-timing-function:steps({len(t)},end)">{e(t)}</span>'
        for i, t in enumerate(TYPED))

    projects = "".join(f"""
      <div class="proj">
        <div class="proj-head"><b>{e(name)}</b><span class="pill {status.replace(' ', '-')}">{e(status)}</span></div>
        <p>{e(desc)}</p>
        <div class="tags">{''.join(f'<span>{e(t)}</span>' for t in tags)}</div>
      </div>""" for name, status, desc, tags in PROJECTS)

    stack = "".join(f"<span>{e(s)}</span>" for s in STACK)
    bar = "".join(f'<i style="width:{p:.2f}%;background:{c}"></i>' for _, p, c in stats["langs"])
    legend = "".join(f'<span><i style="background:{c}"></i>{e(n)} <em>{p:.1f}%</em></span>'
                     for n, p, c in stats["langs"])

    body = f"""
<div class="page">
  <nav>
    <span class="nav-l">projects</span><span class="nav-l">playground</span>
    <span class="sep"></span>
    <b class="brand">LooNuH.dev</b>
    <span class="sep"></span>
    <span class="lang on">EN</span><span class="lang">RU</span>
  </nav>

  <section class="panel hero">
    <div class="hero-text">
      <h1>hi! i'm LooNuH :3</h1>
      <div class="typed">{typed}</div>
      <p>i ship two kinds of things: web platforms (Go and Python backends, React and Next.js
      frontends, Postgres, self-hosted Docker) and firmware for real hardware, like ESP32, nRF52
      and homemade radio protocols.</p>
      <p class="muted">studying Electrical Engineering &amp; IoT at UDG in Podgorica. most things
      get built with my buddy as MetaStack, a two-person team. open to junior roles and internships.</p>
    </div>
    <figure class="teto">
      <img src="{teto}" alt="" />
      <figcaption>teto approves</figcaption>
    </figure>
  </section>

  <h2>what i'm up to rn</h2>
  <section class="grid2">{projects}</section>

  <section class="row">
    <div class="panel">
      <h3>things i use</h3>
      <div class="tags big">{stack}</div>
    </div>
    <div class="panel">
      <h3>numbers go brrr</h3>
      <div class="nums">
        <div><b>3k+</b><span>commits since 2023</span></div>
        <div><b>{stats['repos']}</b><span>repos, mostly private</span></div>
        <div><b>{len(stats['langs']) - 1}+</b><span>languages</span></div>
      </div>
      <div class="bar">{bar}</div>
      <div class="legend">{legend}</div>
    </div>
  </section>

  <section class="panel snake-panel">{snake}</section>

  <footer>
    <span>thanks for stopping by! here, have a baguette 🥖</span>
    <span class="cta">the full thing lives at <b>loonuh.dev</b></span>
  </footer>
</div>"""

    css = """
*{box-sizing:border-box;margin:0}
.page{display:flex;flex-direction:column;width:880px;height:%(h)dpx;padding:22px 26px 24px;border-radius:24px;overflow:hidden;
  background:#0b0b0f radial-gradient(600px 300px at 85%% -40px,rgba(214,51,74,.16),transparent 70%%);
  border:1px solid rgba(255,255,255,.1);color:#e8e8ea;
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
nav{flex:none;display:flex;align-items:center;gap:6px;width:max-content;margin:0 auto 20px;padding:7px 10px;
  border:1px solid rgba(255,255,255,.1);border-radius:14px;background:rgba(0,0,0,.6);font-size:13px}
.nav-l{padding:4px 10px;color:#b4b4bb}
.sep{width:1px;height:18px;background:rgba(255,255,255,.12);margin:0 6px}
.brand{font-weight:800;font-size:16px;letter-spacing:-.02em;padding:0 6px}
.lang{padding:3px 7px;border-radius:7px;color:#8e8e96;font-size:12px}
.lang.on{background:rgba(255,255,255,.1);color:#fff}
.panel{border:1px solid rgba(255,255,255,.1);border-radius:16px;background:rgba(0,0,0,.7);padding:22px}
.hero{display:grid;grid-template-columns:1fr 230px;gap:24px;align-items:center;padding:28px 28px 28px 32px}
h1{font-size:52px;line-height:1.02;font-weight:800;letter-spacing:-.035em;
  background:linear-gradient(#fff 30%%,rgba(255,255,255,.7));-webkit-background-clip:text;background-clip:text;color:transparent}
.typed{position:relative;height:24px;margin:12px 0 16px;font:15px/24px ui-monospace,"SF Mono",Menlo,Consolas,monospace;color:#ff6b80}
.t{position:absolute;left:0;top:0;width:0;overflow:hidden;white-space:nowrap;border-right:2px solid #d6334a;
  animation:type 16s infinite backwards}
@keyframes type{0%%{width:0;opacity:0}.1%%{width:0;opacity:1}12%%{width:calc(var(--n)*1ch + 2px)}22%%{width:calc(var(--n)*1ch + 2px);opacity:1}
  24.9%%{opacity:0}25%%,100%%{width:0;opacity:0}}
.hero p{max-width:60ch;margin-top:10px}
.muted{color:#8e8e96;font-size:14px}
.teto{position:relative;margin:0;text-align:center}
.teto img{width:210px;height:210px;border-radius:18px;background:#f4eef0;
  box-shadow:0 0 0 1px rgba(255,255,255,.12),0 18px 60px -10px rgba(214,51,74,.55)}
.teto figcaption{margin-top:10px;font:12px ui-monospace,"SF Mono",Menlo,monospace;color:#8e8e96}
h2{font-size:24px;font-weight:800;letter-spacing:-.025em;margin:26px 2px 12px}
h3{font-size:15px;font-weight:700;margin-bottom:14px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.proj{border:1px solid rgba(255,255,255,.1);border-radius:16px;background:rgba(0,0,0,.7);padding:16px 18px}
.proj-head{display:flex;justify-content:space-between;align-items:center}
.proj-head b{font-size:17px;letter-spacing:-.01em}
.proj p{color:#b4b4bb;font-size:14px;margin:6px 0 12px;min-height:42px}
.pill{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid}
.pill.live{color:#4ade80;border-color:rgba(74,222,128,.4)}
.pill.cooking{color:#ff6b80;border-color:rgba(214,51,74,.5)}
.pill.open-source{color:#93c5fd;border-color:rgba(147,197,253,.4)}
.tags{display:flex;flex-wrap:wrap;gap:6px}
.tags span{font-size:12px;padding:3px 9px;border-radius:8px;background:rgba(255,255,255,.07);color:#d4d4d8}
.tags.big span{font-size:13px;padding:5px 11px}
.row{display:grid;grid-template-columns:1fr 1.15fr;gap:14px;margin-top:14px}
.nums{display:flex;gap:30px;margin-bottom:16px}
.nums b{display:block;font-size:30px;font-weight:800;letter-spacing:-.03em;line-height:1.1}
.nums span{font-size:12px;color:#8e8e96}
.bar{display:flex;height:9px;border-radius:9px;overflow:hidden;gap:2px;margin-bottom:12px}
.bar i{display:block;height:100%%}
.legend{display:grid;grid-template-columns:repeat(3,1fr);gap:4px 10px;font-size:12px;color:#d4d4d8}
.legend i{display:inline-block;width:8px;height:8px;border-radius:50%%;margin-right:6px}
.legend em{font-style:normal;color:#8e8e96}
.snake-panel{margin-top:14px;padding:6px 12px;text-align:center}
.snake{width:100%%;height:auto;display:block}
footer{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding:18px 4px 0;font-size:14px;color:#8e8e96}
.cta{padding:8px 14px;border-radius:12px;background:#fff;color:#0b0b0f}
@media (prefers-reduced-motion:reduce){.t{animation:none;opacity:0}.t:first-child{opacity:1;width:auto}}
""" % {"h": HEIGHT}

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="LooNuH: fullstack and embedded developer. Full site at loonuh.dev">
<title>LooNuH, loonuh.dev</title>
<foreignObject x="0" y="0" width="{WIDTH}" height="{HEIGHT}">
<div xmlns="http://www.w3.org/1999/xhtml">
<style>{css}</style>{body}
</div>
</foreignObject>
</svg>
"""


def main():
    snake = sys.argv[1] if len(sys.argv) > 1 else None
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "card.svg")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(fetch_stats(), snake), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
