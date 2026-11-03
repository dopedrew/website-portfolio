#!/usr/bin/env python3
"""
Generate the static blog from the series source in the research repo.

The site has no build step, so posts are rendered to flat HTML here and
committed. Source of truth stays the research repo, so a post is written
once and published to wherever it needs to go.

Only posts that already have a generated cover are published: the cover is
produced when a post goes out through the series publisher, so its presence
is the signal that the post is live rather than still queued. That keeps
this site in step with the weekly cadence instead of dumping all ten at once.

    python3 make_blog.py            # render posts that have covers
    python3 make_blog.py --all      # render every post in the series
"""
from __future__ import annotations

import argparse
import html
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
SERIES = Path("/home/dopedrew/ops/repos/research/blogs/cti-platform-build-series")
COVERS = SERIES / "covers"
OUT = ROOT / "blog"
IMG_OUT = ROOT / "images" / "blog"

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{desc}" />
  <link rel="icon" href="/favicon.ico" sizes="any" />
  <link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png" />
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
  <meta name="theme-color" content="#0b0e13" />
  <meta property="og:title" content="{og_title}" />
  <meta property="og:description" content="{desc}" />
  <meta property="og:type" content="{og_type}" />
  {og_image}
  <meta name="twitter:card" content="summary_large_image" />
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <nav id="navbar">
    <div class="nav-inner">
      <a href="/" class="nav-logo-link"><span class="nav-logo">AH<span class="accent">.</span></span></a>
      <div class="nav-links">
        <a href="/#work">Work</a>
        <a href="/blog/">Writing</a>
        <a href="/#experience">Experience</a>
        <a href="/#about">About</a>
        <a href="/#contact">Contact</a>
      </div>
    </div>
  </nav>
"""

FOOT = """
  <footer class="footer">
    <div class="container footer-inner">
      <span class="nav-logo">AH<span class="accent">.</span></span>
      <p>&copy; {year} Andrew Hogan &middot; Built with intention.</p>
    </div>
  </footer>
</body>
</html>
"""


def parse(path: Path) -> dict:
    lines = path.read_text().rstrip().split("\n")
    meta, body_start = {}, 0
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Z]+):\s*(.*)$", line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
        elif not line.strip() and meta:
            body_start = i + 1
            break
    paras = [p.strip() for p in re.split(r"\n\s*\n", "\n".join(lines[body_start:])) if p.strip()]
    part = re.search(r"\((\d+)\s+of\s+(\d+)\)", meta.get("SERIES", ""))
    return {
        "stem": path.stem,
        "slug": re.sub(r"^\d+-", "", path.stem),
        "title": meta.get("TITLE", path.stem),
        "series": meta.get("SERIES", ""),
        "part": int(part.group(1)) if part else 0,
        "total": int(part.group(2)) if part else 0,
        "paras": paras,
        # The last line is a "Next: ..." tease, which only makes sense when
        # the next post exists; it is dropped on the final post.
        "summary": paras[0][:200].rsplit(" ", 1)[0] + "…" if paras else "",
    }


def render_post(post: dict, cover: str | None, prev_: dict | None, next_: dict | None) -> str:
    esc = html.escape
    og_image = (f'<meta property="og:image" content="https://www.andrew-hogan.com{cover}" />'
                if cover else "")
    body = []
    for i, p in enumerate(post["paras"]):
        if p.lower().startswith("next:") and next_:
            continue  # rendered as a proper next-post link instead
        cls = ' class="post-lede"' if i == 0 else ""
        body.append(f"      <p{cls}>{esc(p)}</p>")

    nav = []
    if prev_:
        nav.append(f'<a class="post-nav-link" href="/blog/{prev_["slug"]}.html">'
                   f'<span>Previous</span>{esc(prev_["title"])}</a>')
    if next_:
        nav.append(f'<a class="post-nav-link next" href="/blog/{next_["slug"]}.html">'
                   f'<span>Next</span>{esc(next_["title"])}</a>')

    return (
        HEAD.format(title=esc(post["title"]) + " — Andrew Hogan",
                    og_title=esc(post["title"]),
                    og_type="article",
                    desc=esc(post["summary"]),
                    og_image=og_image)
        + f"""
  <article class="section post-page">
    <div class="container narrow">
      <a class="post-back" href="/blog/">&larr; All writing</a>
      <div class="post-kicker">{esc(post['series'])}</div>
      <h1 class="post-h1">{esc(post['title'])}</h1>
      {f'<img class="post-cover" src="{cover}" alt="" />' if cover else ''}
      <div class="post-body">
{chr(10).join(body)}
      </div>
      <div class="post-nav">{''.join(nav)}</div>
    </div>
  </article>
"""
        + FOOT.format(year=datetime.now(timezone.utc).year))


def render_index(posts: list[dict], covers: dict) -> str:
    esc = html.escape
    cards = []
    for p in posts:
        c = covers.get(p["stem"])
        cards.append(f"""        <a class="post-card" href="/blog/{p['slug']}.html">
          {f'<img src="{c}" alt="" />' if c else ''}
          <div class="post-card-body">
            <div class="post-card-kicker">Part {p['part']} of {p['total']}</div>
            <h2>{esc(p['title'])}</h2>
            <p>{esc(p['summary'])}</p>
          </div>
        </a>""")
    return (
        HEAD.format(title="Writing — Andrew Hogan",
                    og_title="Writing — Andrew Hogan",
                    og_type="website",
                    desc="Build logs on threat intelligence, detection engineering, and security tooling.",
                    og_image="")
        + f"""
  <section class="section post-index">
    <div class="container">
      <div class="section-label">Writing</div>
      <h1 class="section-title">Field notes</h1>
      <p class="section-lede">Build logs from the systems I actually run. Ingestion, scoring,
         enrichment, asset matching, and what production teaches that a lab cannot.</p>
      <div class="post-list">
{chr(10).join(cards)}
      </div>
    </div>
  </section>
"""
        + FOOT.format(year=datetime.now(timezone.utc).year))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="render every post, not just those with a cover")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    IMG_OUT.mkdir(parents=True, exist_ok=True)

    sources = sorted(p for p in SERIES.glob("*.md") if p.name.lower() != "readme.md")
    posts, covers = [], {}
    for src in sources:
        cover_src = COVERS / f"{src.stem}.png"
        if not cover_src.exists() and not args.all:
            continue
        post = parse(src)
        posts.append(post)
        if cover_src.exists():
            shutil.copy(cover_src, IMG_OUT / f"{post['slug']}.png")
            covers[post["stem"]] = f"/images/blog/{post['slug']}.png"

    for i, post in enumerate(posts):
        prev_ = posts[i - 1] if i > 0 else None
        next_ = posts[i + 1] if i + 1 < len(posts) else None
        (OUT / f"{post['slug']}.html").write_text(
            render_post(post, covers.get(post["stem"]), prev_, next_))

    (OUT / "index.html").write_text(render_index(posts, covers))
    print(f"rendered {len(posts)} post(s) + index into {OUT}")
    for p in posts:
        print(f"  /blog/{p['slug']}.html")


if __name__ == "__main__":
    main()
