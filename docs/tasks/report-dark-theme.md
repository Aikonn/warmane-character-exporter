# Task G: dark and light theme for character reports

Status: open (owner decision 2026-11-17). Applies to the character PvE report (quick and full), `pve_report.CSS`. No class colouring, no layout or content changes: only a dark version that follows the system setting, with the same palette as the roster summary (task F).

## Change

Replace the `CSS` constant in `src/warmane_exporter/pve_report.py` with the block below. It keeps every existing rule and only moves colours into CSS variables, adds a page background, an explicit link colour, and a `prefers-color-scheme: dark` override. Claude tried it on a rendered synthetic report in headless Chrome in both modes.

```css
:root{--bg:#ffffff;--fg:#111;--muted:#555;--off:#888;--border:#bbb;--head:#eee;--link:#0b57d0;--finding:#b00020;--h1-line:#444;--h2-line:#999;--note-bg:#f6f6f0;--note-line:#aa8;--warn-bg:#fde8e8;--warn-border:#c33;--warn-line:#b00;--warn-fg:#600;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#16181d;--fg:#e4e6ea;--muted:#a8adb5;--off:#7d838b;--border:#383d46;--head:#22262d;--link:#8ab4f8;--finding:#ff6b7f;--h1-line:#5a606a;--h2-line:#454b55;--note-bg:#23241e;--note-line:#8a8a5c;--warn-bg:#3a1d22;--warn-border:#a3333f;--warn-line:#e05561;--warn-fg:#ffb3bd;color-scheme:dark}}
.finding{color:var(--finding)}
body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:1.5em auto;padding:0 1em;background:var(--bg);color:var(--fg);line-height:1.4}
a{color:var(--link)}
h1{border-bottom:2px solid var(--h1-line);padding-bottom:.2em} h2{margin-top:1.8em;border-bottom:1px solid var(--h2-line)}
table{border-collapse:collapse;margin:.6em 0;font-size:.92em} th,td{border:1px solid var(--border);padding:.25em .6em;text-align:left;vertical-align:top}
th{background:var(--head)} td.n{text-align:right} .muted{color:var(--muted)} .off{color:var(--off)} .note{background:var(--note-bg);border-left:4px solid var(--note-line);padding:.4em .8em}
.warn{background:var(--warn-bg);border:1px solid var(--warn-border);border-left:6px solid var(--warn-line);color:var(--warn-fg);padding:.5em .9em;margin:.6em 0}
details{margin:.4em 0} details.big{margin-top:1.8em;border-bottom:1px solid var(--h2-line)} details.big>summary{list-style-position:inside} details.big>summary>h2{display:inline;margin:0;border:0} summary{cursor:pointer}
```

Dark mapping of the old fixed colours, for reference: issue/finding red `#b00020` -> `#ff6b7f`; muted `#555` -> `#a8adb5`; off `#888` -> `#7d838b`; note box `#f6f6f0`/`#aa8` -> `#23241e`/`#8a8a5c`; warning box `#fde8e8`/`#c33`/`#b00`/`#600` -> `#3a1d22`/`#a3333f`/`#e05561`/`#ffb3bd`. Light values are the current ones (links become `#0b57d0`, as in the roster summary).

## Done when

1. `pve_report.CSS` is the block above; reports still contain no script and make no network requests.
2. `PYTHONPATH=src python -m unittest discover -s tests` passes (report the count), with a test that the rendered report contains `prefers-color-scheme:dark` and that, outside the two `:root` blocks, the CSS has no hex colour literals.
3. Rendered report HTML is unchanged apart from the `<style>` content (compare a fixture's output before and after with the style element removed; say so in the Progress entry).
4. On the PC: open one quick and one full report with Windows in dark mode and in light mode; both readable (a note in the Progress entry is enough).
