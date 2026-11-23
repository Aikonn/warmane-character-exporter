# Task F: roster summary look (dark/light theme, grouped issues, quick-sum copy)

Status: done (manual Windows/chat check waived by owner). Applies to the roster summary page only (`roster.render_summary` and `build_row`); character reports are unchanged.

Reference mockup: [`roster-summary-mockup.html`](roster-summary-mockup.html), built from a real roster with invented names. Its dashed "Mockup only" theme switch at the top is **not** part of the product; the real page follows the system setting only.

## 1. Theme: follow the system light/dark setting

- All colours come from CSS custom properties; `@media (prefers-color-scheme: dark)` switches them. Set `color-scheme` to match so form controls and scrollbars follow.
- No sticky header, zebra stripes, hover highlight, summary bar, filters or GearScore tiers (owner: no).

| Variable | Light | Dark |
|---|---|---|
| page background | `#ffffff` | `#16181d` |
| text | `#111111` | `#e4e6ea` |
| muted text (status, data age, icons) | `#666666` | `#9aa0a6` |
| table borders | `#c4c4c4` | `#383d46` |
| header cell background | `#eeeeee` | `#22262d` |
| link | `#0b57d0` | `#8ab4f8` |
| issue count | `#b00020` | `#ff6b7f` |
| warning count | `#a65a00` | `#f0a24a` |
| issue-group label | `#555555` | `#a8adb5` |

## 2. Class colours

The Class cell loses its coloured background. Each OK row with a known class gets a class CSS class (for example `<tr class="c-hunter">`); unknown/missing classes and non-OK rows get none.

- **Dark:** the character name and the class text use the WotLK class colour (the table in `raid-roster.md`). No row background.
- **Light:** the whole row (every cell) gets a very light tint of the class colour: `round(255 - (255 - channel) * 0.22)` per RGB channel (Python `round`), computed in Python and written as hex. Priest (white) uses `#EDEDED` instead. Name and class text stay the normal text colour (`#111`), the name bold.

Light tints this produces (for the tests):

| Class | Tint |
|---|---|
| Death Knight | `#F2CED4` |
| Druid | `#FFE2C9` |
| Hunter | `#EDF6E0` |
| Mage | `#DEF4FC` |
| Paladin | `#FDE6F0` |
| Priest | `#EDEDED` |
| Rogue | `#FFFDDE` |
| Shaman | `#C7E0F8` |
| Warlock | `#E7E4F3` |
| Warrior | `#F3E9DF` |

Keep one table of class colours in `roster.py` (replace the foreground value in `CLASS_STYLES`, now unused).

## 3. Columns

New order (9 columns): Name, Class, **Spec1 / Spec2**, GearScore, Avg item level, Issues, Warnings, Issues list, Data age.

- Heading "Main trees" becomes **"Spec1 / Spec2"**. Cell content is unchanged ("Shadow / -", "Feral Combat / Feral Combat" stay as they are; owner).
- Report and Armory columns are removed. The **name** links to the local quick report (as the "Open" link did; no link when there is no report file). Right after it, a small external-link icon (inline SVG, muted colour, `title="Armory"`, `aria-label="Armory for NAME"`) links to the armory URL with `target="_blank" rel="noopener"`. Non-OK rows: name as plain text plus the armory icon.
- The Name cell does not wrap (`white-space:nowrap`); neither do Class and Spec1 / Spec2.
- Sortable columns and their `data-sort` values are unchanged (Data age still sorts on the epoch value). Non-OK rows keep their 9-cell layout: name cell, empty cells, status in the Issues list column.

## 4. Grouped issues list

`build_row` keeps the structured issue findings (slot, text) instead of only `issue_texts`, and the Issues list shows grouped lines, in this order, each only when it applies:

1. `No enchant (N): Head, Shoulder, …` (enchant findings except the Enchanter ring ones, slots in equipment order)
2. `No ring enchant (Enchanter) (N): Finger 1, Finger 2`
3. `Empty sockets (N): Head 2, Shoulder 1, …` (N = total empty sockets; per slot its count)
4. `Meta gem not active: Head` (slots)
5. `Belt buckle missing`
6. `Unspent talent points: Spec1 5, Spec2 3`
7. `Major glyphs empty: Spec1 3, Spec2 2`
8. Any other issue: its own line, today's text with the slot prefix when it has one.

The label part (up to and including the colon) is in a `<span class="lbl">` (semi-bold, label colour). All text stays HTML-escaped. The Issues count column still counts findings exactly as today (Ravenik in the mockup: 18 findings, 3 lines).

Classify findings by a machine-readable field, not by parsing English text: add `"kind"` to every finding in `checks.py` (`enchant`, `ring_enchant`, `sockets` (+ `"count"`), `gem_common` (+ `"count"`), `gem_uncommon` (+ `"count"`), `meta`, `buckle`, `armor`, `talents` (+ `"count"`), `glyphs` (+ `"count"`), `no_talents`) and `"spec_index"` (0-based) to spec findings. The PvE report keeps using `text`; its output must not change.

Suggested pure functions in `roster.py`:

```python
def group_issues(issues: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return (label, detail) lines for the Issues list in the order above. detail may be ""."""

def quick_sum(row: RosterRow) -> str | None:
    """One-line chat message for an OK row with issues, else None. See section 5."""
```

## 5. Per-character "quick-sum" copy button

Use case (owner): paste one character's problems into the game chat, which takes a single line.

- OK rows with at least one issue get a small icon button (inline SVG "copy" icon, no text) at the left of the **Issues count** cell, `type="button"`, `title="Copy quick-sum message"`, `aria-label="Copy quick-sum message for NAME"`. The message is in a `data-quick-sum` attribute on the button (escaped). Rows without issues have no button. The cell's `data-sort` stays the count.
- Click copies the message with `navigator.clipboard.writeText`, falling back to a hidden textarea + `document.execCommand("copy")` (the page is opened from `file://`). The icon turns green with title "Copied" for 1.5 s, then returns.
- No "copy all" button (owner: Discord gets the HTML or the tool).

Message format, plain ASCII apart from the name:

    <Name> <GS> - missing <parts>

- GS: GearScore rounded **down** to 0.1k with a `k` suffix, no "gs" (5766 -> `5.7k`, 4872 -> `4.8k`, 6090 -> `6.0k`).
- Parts, comma-separated, in this order, only those that apply: `N enchant(s)` (incl. Enchanter rings), `N gem(s)` (total empty sockets), `buckle`, `N glyph(s)` (summed over specs).
- After the "missing" parts, other issues follow after `; `: `N unspent talent(s)`, `inactive meta gem`, and `N other` for anything else. If there is no "missing" part, drop ` - missing ` and use ` - ` before them.
- Examples: `Ravenik 4.8k - missing 10 enchants, 11 gems, buckle`, `Aldrenna 5.7k - missing buckle, 3 glyphs`, `Name 5.5k - missing 2 gems; inactive meta gem`.
- At most 255 characters (WoW chat limit); it always is with these parts, but test it.

## 6. Data age

- The cell keeps today's text as the no-JavaScript fallback and its `data-sort` epoch value.
- The script replaces the text with a relative age counted from when the page is viewed: `just now` (< 90 s), `N min ago`, `N h ago` (< 36 h), `N d ago`; append ` (cache)` when the data came from cache. The full original text goes into the cell's `title` (hover).
- Muted text colour, no wrap.

## 7. Script and docs

- Still one inline script at the end of `<body>` (sorting, data age, copy); no network requests, no external files; character reports stay script-free.
- Update the "Summary page" section of `docs/tasks/raid-roster.md` (columns, colours, grouped list, copy button, data age) and the README if it describes the summary. Set this file's Status to done.

## Done when

1. The summary follows the system theme: light = class-tinted rows with the table above, dark = class-coloured name and class text; colours from CSS variables per section 1.
2. 9 columns as in section 3; name links the report, armory icon next to it; heading "Spec1 / Spec2"; sorting works on every sortable column including Data age.
3. Issues list shows the grouped lines of section 4 from the new `kind` field; issue counts and the PvE report output unchanged.
4. Copy button and message as in section 5.
5. Data age as in section 6.
6. `python -m unittest discover -s tests` passes (report counts), with tests for: `group_issues` (all kinds incl. Enchanter rings, sockets per slot and total, glyphs and unspent talents on both specs, unknown issue passthrough, order); `quick_sum` (examples above, rounding down, singular/plural, no-"missing" case, only-other case, None without issues, length <= 255); finding `kind`/`count`/`spec_index` in `checks`; PvE report HTML for a fixture identical before and after; summary HTML: `prefers-color-scheme` present, tint hex per class, Priest `#EDEDED`, no Report/Armory headings, name + armory links, non-OK row has 9 cells, button only on rows with issues and with an escaped `data-quick-sum`.
7. On the PC: open a fresh roster summary in Windows light and dark mode (screenshot or note), click one copy button and paste the line into the game chat (paste the line in the Progress entry).
