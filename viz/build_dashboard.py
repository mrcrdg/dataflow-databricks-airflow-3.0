"""Build a static dashboard page from the gold tables.

The "generated HTML page" option in ROADMAP.md § Visualisation: one script, no
server, no new service. It reads the gold tables and writes a self-contained
page — charts are hand-authored SVG, so the output has no runtime dependency and
opens from disk in any browser.

    python viz/build_dashboard.py                        # real data -> viz/out/
    python viz/build_dashboard.py ci.duckdb out.html     # anything else

Paths given on the command line are used as-is; the defaults resolve against the
repo root, so this behaves the same from any working directory (ADR 0003).

Why the output is not committed: it is generated, and ADR 0002 says a committed
artifact that nothing regenerates will drift. `viz/out/` is gitignored — rerun
the script instead.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import duckdb

# --- validated palette -----------------------------------------------------
# Every value below was checked with the dataviz validator rather than by eye:
#   categorical pair (light) #0790AC / #B05F14 — CVD dE 18.9, normal 23.9
#   categorical pair (dark)  #25A0B8 / #C87A2E — inside the dark lightness band
#   ordinal teal ramp        light end clears 2:1 against each surface
ORDINAL_LIGHT = ["#63BDD1", "#3EA9C1", "#0790AC", "#06758C", "#05596B"]
ORDINAL_DARK = ["#8FD6E5", "#5CBFD4", "#25A0B8", "#1B7A8D", "#145E6D"]


def esc(v) -> str:
    return html.escape(str(v), quote=True)


def fmt(n: int) -> str:
    return f"{n:,}"


# ---------------------------------------------------------------------------
# Chart builders. Each returns SVG markup; geometry is computed here so the
# page itself carries no layout logic.
# ---------------------------------------------------------------------------


def grouped_columns(rows, width=920, height=340) -> str:
    """Questions vs answers per year. Two series, so a legend is mandatory."""
    left, right, top, bottom = 52, 14, 20, 52
    pw, ph = width - left - right, height - top - bottom
    ymax = 2800
    ticks = [0, 700, 1400, 2100, 2800]

    def y(v):
        return top + ph - (v / ymax) * ph

    group_w = pw / len(rows)
    bar_w = min(20, (group_w - 12) / 2)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Questions and answers posted per year, 2016 to 2024">'
    ]
    # hairline grid, solid — never dashed
    for t in ticks:
        parts.append(
            f'<line class="gridline" x1="{left}" y1="{y(t):.1f}" '
            f'x2="{width - right}" y2="{y(t):.1f}"/>'
        )
        parts.append(
            f'<text class="tick" x="{left - 10}" y="{y(t) + 4:.1f}" '
            f'text-anchor="end">{fmt(t)}</text>'
        )

    for i, (year, q, a, _total) in enumerate(rows):
        gx = left + i * group_w
        partial = year == 2024
        for j, (val, cls, name) in enumerate(
            ((q, "s1", "Questions"), (a, "s2", "Answers"))
        ):
            bx = gx + group_w / 2 - bar_w - 1 + j * (bar_w + 2)
            bh = (val / ymax) * ph
            parts.append(
                f'<rect class="bar {cls}" x="{bx:.1f}" y="{y(val):.1f}" '
                f'width="{bar_w:.1f}" height="{bh:.1f}" rx="3" '
                f'data-label="{year} {name}" data-value="{fmt(val)} posts"'
                f'{" data-partial=\"1\"" if partial else ""}>'
                f"<title>{year} {name}: {fmt(val)}</title></rect>"
            )
        label = f"{year}*" if partial else str(year)
        parts.append(
            f'<text class="tick" x="{gx + group_w / 2:.1f}" '
            f'y="{height - bottom + 20}" text-anchor="middle">{label}</text>'
        )

    # selective direct labels: the peak year only
    peak = max(rows, key=lambda r: r[3])
    pi = rows.index(peak)
    px = left + pi * group_w + group_w / 2
    parts.append(
        f'<text class="callout" x="{px:.1f}" y="{y(peak[1]) - 10:.1f}" '
        f'text-anchor="middle">{fmt(peak[1])}</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def hbars(rows, width=460, row_h=22, label_w=200) -> str:
    """Top tags. One series, so one colour — never a ramp on nominal categories."""
    height = row_h * len(rows) + 8
    vmax = max(r[1] for r in rows)
    track = width - label_w - 56
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="The fifteen most used tags, by number of posts">'
    ]
    for i, (tag, count) in enumerate(rows):
        y = i * row_h + 6
        bw = max(2, (count / vmax) * track)
        parts.append(
            f'<text class="rowlab" x="{label_w - 10}" y="{y + 11}" '
            f'text-anchor="end">{esc(tag)}</text>'
        )
        parts.append(
            f'<rect class="bar s1" x="{label_w}" y="{y + 1}" width="{bw:.1f}" '
            f'height="13" rx="3" data-label="{esc(tag)}" '
            f'data-value="{fmt(count)} posts">'
            f"<title>{esc(tag)}: {fmt(count)}</title></rect>"
        )
        parts.append(
            f'<text class="val" x="{label_w + bw + 8:.1f}" y="{y + 11}">'
            f"{fmt(count)}</text>"
        )
    parts.append("</svg>")
    return "".join(parts)


def ordinal_columns(rows, width=460, height=210) -> str:
    """Score buckets — genuinely ordered, so the ordinal ramp is correct here."""
    left, right, top, bottom = 10, 10, 26, 40
    pw, ph = width - left - right, height - top - bottom
    vmax = max(r[1] for r in rows)
    slot = pw / len(rows)
    bar_w = min(56, slot - 14)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="How many posts fall in each score band">'
    ]
    for i, (bucket, count) in enumerate(rows):
        bh = (count / vmax) * ph
        bx = left + i * slot + (slot - bar_w) / 2
        by = top + ph - bh
        parts.append(
            f'<rect class="bar ord{i}" x="{bx:.1f}" y="{by:.1f}" '
            f'width="{bar_w:.1f}" height="{bh:.1f}" rx="3" '
            f'data-label="score {esc(bucket)}" data-value="{fmt(count)} posts">'
            f"<title>score {esc(bucket)}: {fmt(count)}</title></rect>"
        )
        parts.append(
            f'<text class="val" x="{bx + bar_w / 2:.1f}" y="{by - 7:.1f}" '
            f'text-anchor="middle">{fmt(count)}</text>'
        )
        parts.append(
            f'<text class="tick" x="{bx + bar_w / 2:.1f}" y="{height - 16}" '
            f'text-anchor="middle">{esc(bucket)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def build(db_path: str, out_path: str) -> None:
    con = duckdb.connect(db_path, read_only=True)
    q = lambda s: con.execute(s).fetchall()  # noqa: E731

    posts, questions, answers, authors, first_post, last_post = q(
        """select count(*), count(*) filter (where post_type='Question'),
                  count(*) filter (where post_type='Answer'),
                  count(distinct owner_user_id),
                  min(post_creation_date)::date::varchar,
                  max(post_creation_date)::date::varchar
           from marts_posts_users"""
    )[0]
    by_year = q(
        """select extract(year from post_creation_date)::int,
                  count(*) filter (where post_type='Question'),
                  count(*) filter (where post_type='Answer'), count(*)
           from marts_posts_users group by 1 order by 1"""
    )
    tags_all = q("select tag, post_count from marts_top_tags order by 2 desc")
    tags = tags_all[:15]
    score_order = ["negative", "zero", "1-4", "5-19", "20+"]
    raw_scores = dict(
        q(
            """select case when score < 0 then 'negative' when score = 0 then 'zero'
                           when score between 1 and 4 then '1-4'
                           when score between 5 and 19 then '5-19' else '20+' end,
                      count(*)
               from marts_posts_users group by 1"""
        )
    )
    scores = [(b, raw_scores.get(b, 0)) for b in score_order]
    unanswered = q(
        """select count(*) from marts_posts_users
           where post_type='Question' and coalesce(answer_count, 0) = 0"""
    )[0][0]
    status = q(
        "select author_status, count(*) from marts_posts_users group by 1 order by 2 desc"
    )
    top_authors = q(
        """select display_name, count(*), max(reputation) from marts_posts_users
           where display_name is not null group by 1 order by 2 desc limit 10"""
    )

    # Fail loudly rather than rendering a page of zeroes. An empty gold table
    # means dbt has not run, or has run against the wrong database — the exact
    # failure this project keeps meeting, where the job succeeds and the output
    # merely looks plausible.
    if posts == 0:
        raise ValueError(
            "marts_posts_users is empty — run `dbt build` before building the "
            "dashboard, and check DATAFLOW_DUCKDB_PATH points where you think"
        )
    if questions == 0:
        raise ValueError("no questions in marts_posts_users — refusing to divide by zero")

    answered = questions - unanswered
    answered_pct = answered / questions * 100

    kpis = [
        (fmt(posts), "posts ingested", "bronze.posts, unchanged through gold"),
        (fmt(questions), "questions", f"{answered_pct:.0f}% have an answer"),
        (fmt(answers), "answers", f"{answers / questions:.2f} per question"),
        (fmt(authors), "distinct authors", "by owner_user_id"),
        (f"{first_post[:4]}–{last_post[:4]}", "years covered", f"to {last_post}"),
        (fmt(len(tags_all)), "tags ranked", "marts_top_tags"),
    ]

    kpi_html = "".join(
        f'<div class="kpi"><span class="kpi-num">{esc(n)}</span>'
        f'<span class="kpi-lab">{esc(lab)}</span>'
        f'<span class="kpi-note">{esc(note)}</span></div>'
        for n, lab, note in kpis
    )

    year_rows = "".join(
        f"<tr><td>{y}</td><td class='num'>{fmt(qq)}</td>"
        f"<td class='num'>{fmt(a)}</td><td class='num'>{fmt(t)}</td></tr>"
        for y, qq, a, t in by_year
    )
    tag_rows = "".join(
        f"<tr><td>{esc(t)}</td><td class='num'>{fmt(c)}</td></tr>" for t, c in tags
    )
    author_rows = "".join(
        f"<tr><td>{esc(n)}</td><td class='num'>{fmt(p)}</td>"
        f"<td class='num'>{fmt(r)}</td></tr>"
        for n, p, r in top_authors
    )
    status_rows = "".join(
        f'<div class="split-row"><span>{esc(s)}</span>'
        f'<span class="num">{fmt(c)}</span></div>'
        for s, c in status
    )

    ord_light = " ".join(f"--o{i}: {c};" for i, c in enumerate(ORDINAL_LIGHT))
    # On the dark ground the ramp runs the other way: more is *lighter*, or
    # the largest band would be the one that disappears into the surface.
    ord_dark = " ".join(
        f"--o{i}: {c};" for i, c in enumerate(reversed(ORDINAL_DARK))
    )
    ord_rules = "\n".join(
        f"  .ord{i} {{ fill: var(--o{i}); }}" for i in range(len(ORDINAL_LIGHT))
    )

    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Stack Exchange Gold Tables</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400&display=swap">

<style>
  /* Light is the complete palette; dark redefines tokens only. Surfaces and
     type are inherited from docs/lakehouse-report.html so the two pages read
     as siblings. Series colours are the validated pair. */
  :root {{
    --ground: #F4F6F8; --surface: #FFFFFF; --surface-2: #EDF0F4;
    --ink: #161A22; --ink-soft: #3D4654; --muted: #626D7E;
    --rule: #D6DBE3; --grid: #E4E8EE;
    --s1: #0790AC; --s2: #B05F14; --track: #DDE3EA;
    {ord_light}
    color-scheme: light;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --ground: #0C1015; --surface: #151B23; --surface-2: #1D242E;
      --ink: #E7EBF1; --ink-soft: #C2CAD6; --muted: #8D98A8;
      --rule: #2A323D; --grid: #232B36;
      --s1: #25A0B8; --s2: #C87A2E; --track: #2A323D;
      {ord_dark}
      color-scheme: dark;
    }}
  }}

  :root[data-theme="dark"] {{
    --ground: #0C1015; --surface: #151B23; --surface-2: #1D242E;
    --ink: #E7EBF1; --ink-soft: #C2CAD6; --muted: #8D98A8;
    --rule: #2A323D; --grid: #232B36;
    --s1: #25A0B8; --s2: #C87A2E; --track: #2A323D;
    {ord_dark}
    color-scheme: dark;
  }}

{ord_rules}
  * {{ box-sizing: border-box; }}

  body {{
    margin: 0; background: var(--ground); color: var(--ink);
    font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif;
    font-size: 16px; line-height: 1.55; -webkit-font-smoothing: antialiased;
  }}

  .page {{ max-width: 1060px; margin: 0 auto; padding: 0 22px 80px; }}

  header {{ padding: 56px 0 28px; border-bottom: 1px solid var(--rule); }}
  .eyebrow {{
    font-family: "IBM Plex Mono", monospace; font-size: .72rem;
    letter-spacing: .12em; text-transform: uppercase; color: var(--s1);
    margin: 0 0 .5rem;
  }}
  h1 {{
    font-size: clamp(1.8rem, 4vw, 2.5rem); line-height: 1.12; font-weight: 600;
    letter-spacing: -.02em; text-wrap: balance; margin: 0 0 .6rem;
  }}
  .lede {{
    font-family: "Source Serif 4", Georgia, serif; font-size: 1.08rem;
    color: var(--ink-soft); max-width: 64ch; margin: 0;
  }}

  h2 {{
    font-size: 1.05rem; font-weight: 600; letter-spacing: -.01em; margin: 0;
  }}
  .card-note {{
    font-family: "Source Serif 4", Georgia, serif; font-size: .92rem;
    color: var(--muted); margin: .3rem 0 0; max-width: 62ch;
  }}

  /* --- KPI row --- */
  .kpis {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
    gap: 1px; background: var(--rule); border: 1px solid var(--rule);
    border-radius: 10px; overflow: hidden; margin: 26px 0 30px;
  }}
  .kpi {{ background: var(--surface); padding: 16px 18px; display: grid; gap: 2px; }}
  .kpi-num {{
    font-size: 1.7rem; font-weight: 600; letter-spacing: -.02em;
    font-variant-numeric: tabular-nums; line-height: 1.1;
  }}
  .kpi-lab {{ font-size: .8rem; color: var(--ink-soft); }}
  .kpi-note {{
    font-family: "IBM Plex Mono", monospace; font-size: .68rem; color: var(--muted);
  }}

  /* --- cards --- */
  .grid {{ display: grid; gap: 18px; }}
  .grid.two {{
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    align-items: start;
  }}
  .card {{
    background: var(--surface); border: 1px solid var(--rule); border-radius: 10px;
    padding: 20px 22px; display: grid; gap: 14px; align-content: start;
  }}
  .card > svg {{ width: 100%; height: auto; overflow: visible; }}

  .legend {{ display: flex; flex-wrap: wrap; gap: 6px 18px; align-items: center; }}
  .legend span {{
    display: inline-flex; align-items: center; gap: 7px; font-size: .8rem;
    color: var(--ink-soft);
  }}
  .swatch {{ width: 11px; height: 11px; border-radius: 3px; }}
  .swatch.s1 {{ background: var(--s1); }}
  .swatch.s2 {{ background: var(--s2); }}
  .swatch.faded {{ background: var(--s1); opacity: .55; }}

  /* --- svg marks --- */
  .bar.s1 {{ fill: var(--s1); }}
  .bar.s2 {{ fill: var(--s2); }}
  .bar {{ transition: opacity .12s ease; }}
  .bar:hover {{ opacity: .78; }}
  [data-partial="1"] {{ opacity: .55; }}
  .gridline {{ stroke: var(--grid); stroke-width: 1; }}
  .tick {{
    fill: var(--muted); font-family: "IBM Plex Mono", monospace; font-size: 11px;
  }}
  .val {{
    fill: var(--ink-soft); font-family: "IBM Plex Mono", monospace;
    font-size: 11px; font-variant-numeric: tabular-nums;
  }}
  .rowlab {{ fill: var(--ink-soft); font-size: 12px; }}
  .callout {{
    fill: var(--ink); font-family: "IBM Plex Mono", monospace; font-size: 11px;
    font-weight: 600;
  }}

  /* --- meter --- */
  .meter {{ display: grid; gap: 8px; }}
  .meter-track {{
    height: 14px; border-radius: 7px; background: var(--track); overflow: hidden;
  }}
  .meter-fill {{ height: 100%; background: var(--s1); border-radius: 7px; }}
  .meter-legend {{
    display: flex; justify-content: space-between; font-size: .82rem;
    color: var(--ink-soft); font-variant-numeric: tabular-nums;
  }}

  .split-row {{
    display: flex; justify-content: space-between; padding: 7px 0;
    border-bottom: 1px solid var(--rule); font-size: .88rem;
  }}
  .split-row:last-child {{ border-bottom: 0; }}

  /* --- tables --- */
  .table-wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .86rem; }}
  th, td {{
    text-align: left; padding: 7px 12px; border-bottom: 1px solid var(--rule);
  }}
  th {{
    font-size: .68rem; letter-spacing: .08em; text-transform: uppercase;
    color: var(--muted); font-weight: 600;
  }}
  td.num, th.num {{
    text-align: right; font-family: "IBM Plex Mono", monospace;
    font-variant-numeric: tabular-nums;
  }}
  tbody tr:last-child td {{ border-bottom: 0; }}

  details {{ font-size: .84rem; }}
  summary {{
    cursor: pointer; color: var(--muted); font-size: .78rem;
    list-style-position: outside;
  }}
  summary:focus-visible, a:focus-visible {{
    outline: 2px solid var(--s1); outline-offset: 3px; border-radius: 3px;
  }}
  details[open] summary {{ margin-bottom: 8px; }}

  section {{ margin-top: 30px; display: grid; gap: 18px; }}
  .section-head {{ display: grid; gap: 2px; }}

  footer {{
    margin-top: 44px; padding-top: 20px; border-top: 1px solid var(--rule);
    font-size: .82rem; color: var(--muted);
  }}
  footer p {{ max-width: 74ch; }}
  code {{
    font-family: "IBM Plex Mono", monospace; font-size: .85em;
    background: var(--surface-2); border-radius: 4px; padding: .1em .35em;
  }}

  /* --- tooltip --- */
  #tip {{
    position: fixed; pointer-events: none; opacity: 0; transition: opacity .1s;
    background: var(--ink); color: var(--ground); font-size: .78rem;
    padding: 6px 9px; border-radius: 6px; z-index: 10; white-space: nowrap;
    font-family: "IBM Plex Sans", sans-serif;
  }}
  #tip b {{ font-weight: 600; }}
  #tip .tv {{
    font-family: "IBM Plex Mono", monospace; opacity: .85; margin-left: 6px;
  }}

  @media (prefers-reduced-motion: reduce) {{
    * {{ transition: none !important; }}
  }}
</style>
</head>
<body>

<div class="page">
  <header>
    <p class="eyebrow">gold layer · {esc(first_post)} → {esc(last_post)}</p>
    <h1>What the gold tables actually say</h1>
    <p class="lede">
      Every number on this page is a query against <code>marts_posts_users</code> and
      <code>marts_top_tags</code> — the two finished tables the lakehouse produces.
      Nothing here is computed in the page; the chart geometry is generated from
      the query results.
    </p>
  </header>

  <div class="kpis">{kpi_html}</div>

  <section>
    <div class="section-head">
      <h2>Posts per year</h2>
      <p class="card-note">
        The site grew until 2020, fell back, and recovered. Questions and answers
        track each other closely, which is what a healthy Q&amp;A site looks like —
        the gap between them is the site's answering deficit.
      </p>
    </div>
    <div class="card">
      <div class="legend">
        <span><i class="swatch s1"></i>Questions</span>
        <span><i class="swatch s2"></i>Answers</span>
        <span><i class="swatch faded"></i>faded: 2024 is partial — the dump ends {esc(last_post)}</span>
      </div>
      {grouped_columns(by_year)}
      <details>
        <summary>Table view</summary>
        <div class="table-wrap"><table>
          <thead><tr><th>Year</th><th class="num">Questions</th>
            <th class="num">Answers</th><th class="num">All posts</th></tr></thead>
          <tbody>{year_rows}</tbody>
        </table></div>
      </details>
    </div>
  </section>

  <section>
    <div class="grid two">
      <div class="card">
        <div class="section-head">
          <h2>The fifteen most used tags</h2>
          <p class="card-note">
            One colour, because tags have no order — length is the whole message.
          </p>
        </div>
        {hbars(tags)}
        <details>
          <summary>Table view — all 15</summary>
          <div class="table-wrap"><table>
            <thead><tr><th>Tag</th><th class="num">Posts</th></tr></thead>
            <tbody>{tag_rows}</tbody>
          </table></div>
        </details>
      </div>

      <div class="grid">
        <div class="card">
          <div class="section-head">
            <h2>Score distribution</h2>
            <p class="card-note">
              Ordered bands, so the colour ramp carries the order. Most posts sit
              at 1–4; only {fmt(raw_scores["negative"])} are negative.
            </p>
          </div>
          {ordinal_columns(scores)}
        </div>

        <div class="card">
          <div class="section-head">
            <h2>Answer coverage</h2>
          </div>
          <div class="meter">
            <div class="meter-track">
              <div class="meter-fill" style="width: {answered_pct:.1f}%"></div>
            </div>
            <div class="meter-legend">
              <span>{fmt(answered)} answered ({answered_pct:.1f}%)</span>
              <span>{fmt(unanswered)} unanswered</span>
            </div>
          </div>
          <p class="card-note">
            Of {fmt(questions)} questions. "Unanswered" here means zero answers on
            the post, not an unaccepted one.
          </p>
        </div>

        <div class="card">
          <div class="section-head">
            <h2>Did the author join?</h2>
            <p class="card-note">
              <code>author_status</code> records how each post matched its writer.
              The third value the column can take — <code>unresolved</code>, an
              author id with no user row — never occurs in the real dump. Only the
              CI fixtures produce it, which is why the branch is tested at all.
            </p>
          </div>
          {status_rows}
        </div>
      </div>
    </div>
  </section>

  <section>
    <div class="section-head">
      <h2>Who writes the most</h2>
      <p class="card-note">
        Ten rows, two measures, no natural order to encode — a table beats a chart
        here. <em>Community</em> is the pseudo-user that owns wiki posts.
      </p>
    </div>
    <div class="card">
      <div class="table-wrap"><table>
        <thead><tr><th>Author</th><th class="num">Posts</th>
          <th class="num">Reputation</th></tr></thead>
        <tbody>{author_rows}</tbody>
      </table></div>
    </div>
  </section>

  <footer>
    <p>
      Generated by <code>build_dashboard.py</code> from <code>dataflow.duckdb</code>,
      the local DuckDB database the dbt project writes. Source: the Stack Exchange
      data dump for ai.stackexchange.com, CC&nbsp;BY-SA, posts from
      {esc(first_post)} to {esc(last_post)}.
    </p>
    <p>
      One caveat worth stating: CI builds the lakehouse from five-row fixtures, so
      it can check that this page <em>generates</em>, but it cannot check these
      numbers. They come from a local run against the full 191&nbsp;MB archive.
    </p>
  </footer>
</div>

<div id="tip" role="status" aria-live="polite"></div>

<script>
  // Hover layer: one tooltip element, delegated. Marks carry their own labels
  // as data attributes, so nothing here needs to know about the data.
  (function () {{
    var tip = document.getElementById("tip");
    document.addEventListener("mouseover", function (e) {{
      var m = e.target.closest("[data-label]");
      if (!m) return;
      tip.innerHTML = "<b>" + m.dataset.label + "</b><span class='tv'>" +
        m.dataset.value + "</span>";
      tip.style.opacity = "1";
    }});
    document.addEventListener("mousemove", function (e) {{
      if (tip.style.opacity !== "1") return;
      var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
      tip.style.left = x + "px";
      tip.style.top = (e.clientY + 16) + "px";
    }});
    document.addEventListener("mouseout", function (e) {{
      if (e.target.closest("[data-label]")) tip.style.opacity = "0";
    }});
  }})();
</script>

</body>
</html>
"""
    Path(out_path).write_text(page, encoding="utf-8")
    print(f"wrote {out_path} ({len(page):,} bytes)")


# The repo root is the directory containing this file's parent — same trick as
# dataflow.common.config.resolve_path(), which cannot be imported here because
# this script is deliberately outside the package: it is a tool, not a stage of
# the pipeline.
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "dataflow.duckdb"
DEFAULT_OUT = REPO_ROOT / "viz" / "out" / "gold-dashboard.html"


def main(argv: list[str]) -> None:
    db = Path(argv[1]) if len(argv) > 1 else DEFAULT_DB
    out = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT

    if not db.exists():
        raise SystemExit(
            f"no database at {db} — run the bronze jobs and `dbt build` first"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    build(str(db), str(out))


if __name__ == "__main__":
    main(sys.argv)
