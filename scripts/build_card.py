#!/usr/bin/env python3
"""Build the profile card: a small copy of loonuh.dev, cut into stacked images.

Usage: GITHUB_TOKEN=... python3 scripts/build_card.py [snake.svg] [out-dir] [--measure]

Writes card-top/mid/bottom.svg. The hero row is two GIFs, src/card/hero.gif
and src/card/teto.gif: browsers play GIFs on an even clock, while CSS
animations inside an SVG image tick unevenly in Chrome. `--render DIR` writes
the pages and frame lists that scripts/render_gifs.cjs turns into those GIFs;
run both by hand when the hero text, Teto tile or hero height changes.

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
    # snk steps one cell every 0.24% of 41700 ms (100.08 ms); pin it to the clock.
    svg = svg.replace("41700ms", f"{TICK_MS / 0.0024:.3f}ms")
    # Cells get eaten at offsets like 0.73%; snap them to the same 0.24% grid.
    snap = lambda m: f"{min(round(float(m[1]) / 0.24) * 0.24, 99.84) if float(m[1]) < 100 else 100:.2f}%"
    svg = re.sub(r"@keyframes c\w+\{.*?\}\}",
                 lambda m: re.sub(r"([\d.]+)%", snap, m[0]), svg)
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


# Animations step on a 100 ms tick instead of changing every frame: an SVG
# image repaints whole on each change, so fewer changes mean less work.
TICK_MS = 100
TETO_FRAMES = [2, 1, 1, 1, 1, 1]  # GIF frame lengths in ticks, used by render_teto.cjs
TYPE_HOLD, TYPE_GAP = 20, 3       # ticks a phrase stays up, then stays blank


def typing_animation():
    """One char per tick. Each phrase gets its own keyframes on the same cycle,
    so all of them share one start time instead of staggered delays."""
    total = sum(len(t) + TYPE_HOLD + TYPE_GAP for t in TYPED)
    pct = lambda tick: f"{tick / total * 100:.4f}%"
    spans, css, start = [], [], 0
    for i, text in enumerate(TYPED):
        n = len(text)
        full = f"calc({n}ch + 2px)"
        kf = [f"0%{{width:2px;opacity:0;animation-timing-function:steps(1,end)}}"]
        kf.append(f"{pct(start)}{{width:2px;opacity:1;animation-timing-function:steps({n},end)}}")
        kf.append(f"{pct(start + n)}{{width:{full};opacity:1;animation-timing-function:steps(1,end)}}")
        kf.append(f"{pct(start + n + TYPE_HOLD)}{{width:2px;opacity:0}}")
        kf.append("100%{width:2px;opacity:0}")
        css.append(f"@keyframes t{i}{{{''.join(kf)}}}"
                   f".t{i}{{animation:t{i} {total * TICK_MS}ms infinite}}")
        spans.append(f'<span class="t t{i}">{e(text)}</span>')
        start += n + TYPE_HOLD + TYPE_GAP
    return "".join(spans), "".join(css)


# The card is cut into a few images that GitHub stacks with no gaps (see
# README). Inside one big SVG image, several CSS animations at once render
# unevenly in Chrome, so each piece carries at most one animation, and Teto
# is a real GIF (src/card/teto.gif) that the browser plays natively.
W, PAD, GAP = 880, 26, 14
HERO_W = 610                      # left of the hero row; Teto gets the rest
TETO_W = W - HERO_W
HEIGHTS = {"top": 88, "hero": 320, "mid": 640, "bottom": 250}


def sections(stats, snake_path):
    typed, typed_css = typing_animation()
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
    return {
        "top": ("""
  <nav>
    <span class="nav-l">projects</span><span class="nav-l">playground</span>
    <span class="sep"></span>
    <b class="brand">LooNuH.dev</b>
    <span class="sep"></span>
    <span class="lang on">EN</span><span class="lang">RU</span>
  </nav>""", ""),
        "hero": (f"""
  <section class="panel hero">
    <h1>hi! i'm LooNuH :3</h1>
    <div class="typed">{typed}</div>
    <p>i ship two kinds of things: web platforms (Go and Python backends, React and Next.js
    frontends, Postgres, self-hosted Docker) and firmware for real hardware, like ESP32, nRF52
    and homemade radio protocols.</p>
    <p class="muted">studying Electrical Engineering &amp; IoT at UDG in Podgorica. most things
    get built with my buddy as MetaStack, a two-person team. open to junior roles and internships.</p>
  </section>""", typed_css),
        "mid": (f"""
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
  </section>""", ""),
        "bottom": (f"""
  <section class="panel snake-panel">{inline_snake(snake_path)}</section>
  <footer>
    <span>thanks for stopping by! here, have a baguette 🥖</span>
    <span class="cta">the full thing lives at <b>loonuh.dev</b></span>
  </footer>""", ""),
        "teto": ("""
  <figure class="panel teto">
    <div class="teto-img"></div>
    <figcaption>teto approves</figcaption>
  </figure>""", ""),
    }


CSS = """
*{box-sizing:border-box;margin:0}
.strip{display:flex;flex-direction:column;overflow:hidden;background:#0b0b0f;color:#e8e8ea;
  border:0 solid rgba(255,255,255,.1);border-left-width:1px;border-right-width:1px;padding:0 26px;
  font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.strip.s-top{border-top-width:1px;border-radius:24px 24px 0 0;padding-top:22px}
.strip.s-bottom{border-bottom-width:1px;border-radius:0 0 24px 24px;padding-bottom:24px}
.strip.s-hero{border-right-width:0;padding-right:7px}
.strip.s-teto{border-left-width:0;padding-left:7px}
nav{flex:none;display:flex;align-items:center;gap:6px;width:max-content;margin:0 auto;padding:7px 10px;
  border:1px solid rgba(255,255,255,.1);border-radius:14px;background:rgba(0,0,0,.6);font-size:13px}
.nav-l{padding:4px 10px;color:#b4b4bb}
.sep{width:1px;height:18px;background:rgba(255,255,255,.12);margin:0 6px}
.brand{font-weight:800;font-size:16px;letter-spacing:-.02em;padding:0 6px}
.lang{padding:3px 7px;border-radius:7px;color:#8e8e96;font-size:12px}
.lang.on{background:rgba(255,255,255,.1);color:#fff}
.panel{border:1px solid rgba(255,255,255,.1);border-radius:16px;background:rgba(0,0,0,.7);padding:22px}
.hero{flex:1;display:flex;flex-direction:column;justify-content:center;padding:28px 30px}
h1{font-size:52px;line-height:1.02;font-weight:800;letter-spacing:-.035em;
  background:linear-gradient(#fff 30%,rgba(255,255,255,.7));-webkit-background-clip:text;background-clip:text;color:transparent}
.typed{position:relative;height:24px;margin:12px 0 6px;font:15px/24px ui-monospace,"SF Mono",Menlo,Consolas,monospace;color:#ff6b80}
.t{position:absolute;left:0;top:0;width:2px;opacity:0;overflow:hidden;white-space:nowrap;border-right:2px solid #d6334a}
.hero p{margin-top:10px}
.muted{color:#8e8e96;font-size:14px}
.teto{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;position:relative;overflow:hidden;padding:16px 10px}
.teto::before{content:"";position:absolute;left:-40px;right:-40px;top:0;bottom:20px;
  background:radial-gradient(closest-side,rgba(214,51,74,.38),rgba(214,51,74,0))}
.teto-img{position:relative;width:210px;height:210px;background:0 0/1260px 210px no-repeat}
.teto figcaption{position:relative;margin-top:12px;font:12px ui-monospace,"SF Mono",Menlo,monospace;color:#8e8e96}
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
.bar i{display:block;height:100%}
.legend{display:grid;grid-template-columns:repeat(3,1fr);gap:4px 10px;font-size:12px;color:#d4d4d8}
.legend i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.legend em{font-style:normal;color:#8e8e96}
.snake-panel{margin-top:14px;padding:6px 12px}
.snake{width:100%;height:auto;display:block}
footer{display:flex;justify-content:space-between;align-items:center;margin-top:auto;padding:18px 4px 0;font-size:14px;color:#8e8e96}
.cta{padding:8px 14px;border-radius:12px;background:#fff;color:#0b0b0f}
@media (prefers-reduced-motion:reduce){.t,.snake *{animation:none!important}.t:first-child{opacity:1;width:auto}}
"""


def strip_html(name, inner, extra_css, width, height):
    h = f"height:{height}px" if height else ""
    return f'<style>{CSS}{extra_css}</style><div class="strip s-{name}" style="width:{width}px;{h}">{inner}</div>'


def strip_svg(name, inner, extra_css, width, height):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="LooNuH, loonuh.dev">
<foreignObject x="0" y="0" width="{width}" height="{height}">
<div xmlns="http://www.w3.org/1999/xhtml">{strip_html(name, inner, extra_css, width, height)}</div>
</foreignObject>
</svg>
"""


WIDTHS = {"top": W, "hero": HERO_W, "teto": TETO_W, "mid": W, "bottom": W}


def render_jobs(sec):
    """Pages and per-tick frame states for scripts/render_gifs.cjs. Each frame
    is a bit of JS that puts the page in the state for that 100 ms tick."""
    page = lambda name, css="": ("<!doctype html><meta charset=utf-8><style>body{margin:0;background:#0b0b0f}</style>"
                                 + strip_html(name, sec[name][0], ".t{animation:none!important}" + css,
                                              WIDTHS[name], HEIGHTS["hero"]))
    sprite = data_uri(ROOT / "src/gif/teto-sprite.png", "image/png")
    teto = []
    for i, ticks in enumerate(TETO_FRAMES):
        teto += [f"document.querySelector('.teto-img').style.backgroundPosition='{-210 * i}px 0'"] * ticks
    # Same schedule as typing_animation(): one char per tick, hold, then blank.
    hero = []
    for i, text in enumerate(TYPED):
        n = len(text)
        show = lambda k, on=True: (f"document.querySelectorAll('.t').forEach((s,j)=>{{s.style.opacity=j=={i}&&{int(on)}?1:0;"
                                   f"s.style.width='calc({k}ch + 2px)'}})")
        hero += [show(k) for k in range(n)] + [show(n)] * TYPE_HOLD + [show(0, False)] * TYPE_GAP
    return {
        "teto": (page("teto", f".teto-img{{background-image:url({sprite})}}"), teto),
        "hero": (page("hero"), hero),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("snake", nargs="?", help="snk SVG to inline in the bottom strip")
    ap.add_argument("out", nargs="?", default="dist", help="output directory")
    ap.add_argument("--measure", action="store_true",
                    help="also write measure.html with every strip at its natural height")
    ap.add_argument("--render", metavar="DIR", help="write pages + frame lists for scripts/render_gifs.cjs")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sec = sections(fetch_stats(), args.snake)
    for name in ("top", "mid", "bottom"):
        inner, css = sec[name]
        f = out / f"card-{name}.svg"
        f.write_text(strip_svg(name, inner, css, WIDTHS[name], HEIGHTS[name]), encoding="utf-8")
        print(f"wrote {f} ({f.stat().st_size // 1024} KB)")
    if args.render:
        rd = Path(args.render)
        rd.mkdir(parents=True, exist_ok=True)
        jobs = {}
        for name, (html_page, frames) in render_jobs(sec).items():
            (rd / f"{name}.html").write_text(html_page, encoding="utf-8")
            jobs[name] = {"page": f"{name}.html", "frames": frames}
        (rd / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        print(f"wrote render jobs to {rd}")
    if args.measure:
        page = "".join(f'<div id="{n}" style="width:{WIDTHS[n]}px">' + strip_html(n, *sec[n], WIDTHS[n], None) + "</div>"
                       for n in ("top", "hero", "teto", "mid", "bottom"))
        (out / "measure.html").write_text("<!doctype html><meta charset=utf-8><body style=margin:0>" + page, encoding="utf-8")


if __name__ == "__main__":
    main()
