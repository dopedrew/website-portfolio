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
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
SERIES = Path("/home/dopedrew/ops/repos/research/blogs/cti-platform-build-series")
COVERS = SERIES / "covers"
SITE = "https://www.andrew-hogan.com"
OUT = ROOT / "blog"
DATES = ROOT / "blog" / "dates.json"
IMG_OUT = ROOT / "images" / "blog"

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{desc}" />
  <link rel="canonical" href="{canonical}" />
  <link rel="icon" href="/favicon.ico" sizes="any" />
  <link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png" />
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
  <meta name="theme-color" content="#f6f3ee" />
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
      <button class="nav-toggle" aria-expanded="false" aria-controls="nav-links" aria-label="Open menu">
        <span></span><span></span><span></span>
      </button>
      <div class="nav-links" id="nav-links">
        <a href="/#work">Work</a>
        <a href="/blog/">Writing</a>
        <a href="/#about">About</a>
        <a href="/background.html">Background</a>
        <a href="/#contact">Contact</a>
      </div>
    </div>
  </nav>

  <main id="main">
"""

NAV_JS = """
  <script>
    // Blog pages share the fixed navbar, so they need the same scrolled
    // material the home and background pages use.
    (function () {
      var bar = document.getElementById('navbar'), queued = false;
      function sync() { queued = false; bar.classList.toggle('scrolled', window.scrollY > 40); }
      window.addEventListener('scroll', function () {
        if (!queued) { queued = true; requestAnimationFrame(sync); }
      }, { passive: true });
      sync();
    })();
    (function () {
      var t = document.querySelector('.nav-toggle'),
          n = document.getElementById('nav-links');
      if (!t || !n) return;
      t.addEventListener('click', function () {
        var open = n.classList.toggle('open');
        t.setAttribute('aria-expanded', open);
        t.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      });
      // Escape dismisses the menu and returns focus to the trigger.
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && n.classList.contains('open')) {
          n.classList.remove('open');
          t.setAttribute('aria-expanded', 'false');
          t.setAttribute('aria-label', 'Open menu');
          t.focus();
        }
      });
      n.addEventListener('click', function (e) {
        if (e.target.tagName === 'A') {
          n.classList.remove('open');
          t.setAttribute('aria-expanded', 'false');
          t.setAttribute('aria-label', 'Open menu');
        }
      });
    })();
  </script>
"""

FOOT = """
  </main>

  <footer class="footer">
    <div class="container footer-inner">
      <span class="nav-logo">AH<span class="accent">.</span></span>
      <p>&copy; {year} Andrew Hogan</p>
    </div>
  </footer>
</body>
</html>
"""


def load_dates() -> dict:
    """Publish dates per slug.

    The series source carries no DATE, so the first render of a post stamps
    it and the value is committed. Without this every regeneration would
    re-date the whole archive to today, which is worse than no date at all.
    """
    try:
        return json.loads(DATES.read_text())
    except Exception:
        return {}


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
    # BlogPosting is what lets a post be cited as a dated, attributed source
    # by search and AI answer engines instead of read as anonymous text.
    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post["summary"],
        "datePublished": post.get("date"),
        "dateModified": post.get("date"),
        "author": {"@id": f"{SITE}/#person"},
        "publisher": {"@id": f"{SITE}/#person"},
        "mainEntityOfPage": {"@type": "WebPage", "@id": f"{SITE}/blog/{post['slug']}.html"},
        "inLanguage": "en-US",
    }
    if cover:
        schema["image"] = f"{SITE}{cover}"
    if post.get("series"):
        schema["isPartOf"] = {"@type": "CreativeWorkSeries", "name": post["series"]}
    schema = {k: v for k, v in schema.items() if v is not None}
    schema_tag = ('<script type="application/ld+json">'
                  + json.dumps(schema) + "</script>")
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
        HEAD.format(title=esc(post["title"]) + " | Andrew Hogan",
                    og_title=esc(post["title"]),
                    og_type="article",
                    desc=esc(post["summary"]),
                    canonical=f"{SITE}/blog/{post['slug']}.html",
                    og_image=og_image)
        + schema_tag
        + f"""
  <article class="section post-page">
    <div class="container narrow">
      <a class="post-back" href="/blog/">&larr; All writing</a>
      <div class="post-kicker">{esc(post['series'])}</div>
      {f'<p class="post-date"><time datetime="{post["date"]}">{post["date"]}</time></p>' if post.get("date") else ''}
      <h1 class="post-h1">{esc(post['title'])}</h1>
      {f'<img class="post-cover" src="{cover}" alt="Cover illustration for {esc(post["title"])}" />' if cover else ''}
      <div class="post-body">
{chr(10).join(body)}
      </div>
      <div class="post-nav">{''.join(nav)}</div>
    </div>
  </article>
"""
        + NAV_JS + FOOT.format(year=datetime.now(timezone.utc).year))


def render_index(posts: list[dict], covers: dict) -> str:
    esc = html.escape
    # Blog node ties the individual BlogPosting pages together as one body of
    # work rather than leaving them as unrelated documents.
    blog_schema_tag = '<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org",
        "@type": "Blog",
        "@id": f"{SITE}/blog/#blog",
        "url": f"{SITE}/blog/",
        "name": "Field notes | Andrew Hogan",
        "description": "Build logs from the threat intelligence platform, detection lab, and security tooling I run in production.",
        "inLanguage": "en-US",
        "author": {"@id": f"{SITE}/#person"},
        "publisher": {"@id": f"{SITE}/#person"},
        "blogPost": [
            {"@type": "BlogPosting",
             "headline": p["title"],
             "url": f"{SITE}/blog/{p['slug']}.html",
             "datePublished": p.get("date")}
            for p in posts
        ],
    }) + "</script>"
    cards = []
    for p in posts:
        c = covers.get(p["stem"])
        cards.append(f"""        <a class="post-card" href="/blog/{p['slug']}.html">
          {f'<img src="{c}" alt="Cover illustration for {esc(p["title"])}" />' if c else ''}
          <div class="post-card-body">
            <div class="post-card-kicker">Part {p['part']} of {p['total']}</div>
            <h2>{esc(p['title'])}</h2>
            <p>{esc(p['summary'])}</p>
          </div>
        </a>""")
    return (
        blog_schema_tag
        + HEAD.format(title="Writing: Build Logs on Threat Intelligence and Detection | Andrew Hogan",
                    og_title="Writing | Andrew Hogan",
                    og_type="website",
                    desc="Build logs from the threat intelligence platform, detection lab, and security tooling Andrew Hogan runs in production. Ingestion, scoring, enrichment, and asset matching.",
                    canonical=f"{SITE}/blog/",
                    og_image=f'<meta property="og:image" content="{SITE}/og-image.png" />')
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
        + NAV_JS + FOOT.format(year=datetime.now(timezone.utc).year))


def write_sitemap(posts: list[dict]) -> None:
    """Emit sitemap.xml covering the static pages plus every published post.

    Generated here rather than kept by hand: the post list grows every week
    through the series publisher, and a stale sitemap is worse than none.
    """
    urls = [f"{SITE}/", f"{SITE}/background.html", f"{SITE}/blog/"]
    urls += [f"{SITE}/blog/{p['slug']}.html" for p in posts]
    body = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n")
    print(f"wrote sitemap.xml ({len(urls)} urls)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true",
                    help="render every post, not just those with a cover")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    IMG_OUT.mkdir(parents=True, exist_ok=True)

    dates = load_dates()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dates_changed = False

    sources = sorted(p for p in SERIES.glob("*.md") if p.name.lower() != "readme.md")
    posts, covers = [], {}
    for src in sources:
        cover_src = COVERS / f"{src.stem}.png"
        if not cover_src.exists() and not args.all:
            continue
        post = parse(src)
        if post["slug"] not in dates:
            dates[post["slug"]] = today
            dates_changed = True
        post["date"] = dates[post["slug"]]
        posts.append(post)
        if cover_src.exists():
            shutil.copy(cover_src, IMG_OUT / f"{post['slug']}.png")
            covers[post["stem"]] = f"/images/blog/{post['slug']}.png"

    for i, post in enumerate(posts):
        prev_ = posts[i - 1] if i > 0 else None
        next_ = posts[i + 1] if i + 1 < len(posts) else None
        (OUT / f"{post['slug']}.html").write_text(
            render_post(post, covers.get(post["stem"]), prev_, next_))

    if dates_changed:
        DATES.write_text(json.dumps(dates, indent=2, sort_keys=True) + "\n")
        print(f"stamped publish date for {len(dates)} post(s)")

    (OUT / "index.html").write_text(render_index(posts, covers))
    write_sitemap(posts)
    print(f"rendered {len(posts)} post(s) + index into {OUT}")
    for p in posts:
        print(f"  /blog/{p['slug']}.html")


if __name__ == "__main__":
    main()
