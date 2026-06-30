"""
parse_act.py

Parses a scanned/text Indian central act PDF into structured per-section JSON.

Usage:
    python scripts/ingest/parse_act.py "data/raw/THE INDIAN CONTRACT ACT, 1872.pdf"

Output:
    data/processed/<act_slug>.json
"""

import sys
import re
import json
from pathlib import Path

import fitz  # pymupdf


# ---------- Step 1: extract raw text ----------

def extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    return "\n".join(pages)


# ---------- Step 2: cut off the table of contents ----------

def find_operative_text_start(full_text: str) -> str:
    match = re.search(r"ACT NO\.\s*\d+\s*OF\s*\d{4}", full_text)
    if not match:
        match = re.search(r"\bPreamble\b", full_text)
    if not match:
        raise ValueError("Could not locate start of operative text. Inspect manually.")
    return full_text[match.start():]


# ---------- Step 3: strip noise ----------

FOOTNOTE_PHRASES = [
    "Subs.", "Ins.", "Rep.", "See", "Cf.", "C.f.", "For the Statement of Objects",
    "For an Exception", "For the Statement", "The words", "The original",
    "As to", "This Act", "Added by", "Vide", "Omitted", "Paragraph",
    "But", "Ss.", "S.",
    # BUG FIX (#7a): additional footnote-annotation openers found in Transfer of
    # Property and Prisons Acts that were slipping through as false section hits.
    "Nothing", "Amended", "The Act", "Now", "Substituted", "Extended",
]
_FOOTNOTE_ALTERNATION = "|".join(re.escape(p) for p in FOOTNOTE_PHRASES)

FOOTNOTE_PARAGRAPH_RE = re.compile(
    r"\n\s*\d{1,2}\.\s*(?:" + _FOOTNOTE_ALTERNATION + r")"
    r".*?(?=\n\s*\n|\n\s*(?:\d+\[\s*)?\d{1,3}[A-Z]?\.\s*[A-Z\u201c\"]|\Z)",
    re.DOTALL,
)

# BUG FIX: Omitted/repealed-section blocks have bracketed titles, e.g.:
#   49. [Composition of Cyber Appellate Tribunal.]—Omitted by the Finance Act, 2017
#   7[130A. [Transfer of policy of marine insurance.] Rep. by the Marine Insurance Act, 1963
# The leading '[' (or footnote-glued prefix like '7[') means SECTION_HEADER_RE
# never matches them, so their text gets silently absorbed into the preceding
# section's body.  Strip them out entirely.
OMITTED_SECTION_RE = re.compile(
    r"\n\s*(?:"
    r"(?:\d+\[)?\s*\d{1,3}[A-Z]?\.\s*\[[^\]\n]*\.\]"
    r"|"
    r"\d+\[\d{1,3}[A-Z]?\.\s*[^\]\n]*\.\]"
    r")"
    r"\s*[\u2014\u2013]?\s*(?:Omitted|Rep\.)\s+by"
    r".*?(?=\n\s*\n|\n\s*(?:\d+\[\s*)?\d{1,3}[A-Z]?\.\s*[A-Z\u201c\"\[]|\Z)",
    re.DOTALL,
)

# BUG FIX (#3/#4): footnote superscript markers sometimes get extracted glued
# directly onto the section number with no separator, e.g. "1151." for
# footnote-1 + section-151, or "1161." for footnote-1 + section-161. Since
# real section numbers in this Act are never more than 3 digits, a 4-digit
# run (footnote digit + 3-digit section number) immediately followed by
# ". <Capital>" is virtually always this glue bug. IMPORTANT: this must
# require EXACTLY 4 digits total -- not "2 or 3" -- otherwise it wrongly
# mangles genuine 3-digit section numbers like "124." into "24.".
GLUED_FOOTNOTE_DIGIT_RE = re.compile(r"(?:^|\n)(\d)(\d{3}\.\s*[A-Z\u201c\"])")


def clean_text(text: str) -> str:
    # Remove standalone page-number lines, e.g. a lone "13" on its own line.
    # IMPORTANT: only consume horizontal whitespace ([ \t]) around the digits,
    # never \s (which includes newlines) -- otherwise this can accidentally
    # eat a real blank-line paragraph break sitting next to a page number,
    # which footnote-paragraph stripping (below) depends on to know where to
    # stop. Losing that boundary let a footnote silently swallow real
    # section content across a page break.
    text = re.sub(r"\n[ \t]*\d{1,4}[ \t]*\n", "\n", text)

    # Fix glued footnote-digit + section-number runs (e.g. "1151." -> "151.")
    text = GLUED_FOOTNOTE_DIGIT_RE.sub(lambda m: "\n" + m.group(2), text)

    # Remove footnote paragraphs entirely, BEFORE section-splitting runs, so a
    # footnote's leading number can never be mistaken for a real section
    # heading.
    text = FOOTNOTE_PARAGRAPH_RE.sub("\n", text)

    # Strip omitted-section blocks (bracketed-title entries absorbed by prior section).
    text = OMITTED_SECTION_RE.sub("\n", text)

    # Normalize whitespace: collapse multiple spaces, but keep newlines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------- Step 4: split into sections ----------

# BUG FIX (#1): title char cap raised from 180 -> 320. Some modern/long
# section titles (e.g. s.25 of the Contract Act, ~189 chars) were being
# silently skipped because the old cap was too tight. The blank-line guard
# still prevents runaway matches if an em-dash is ever missing.
SECTION_HEADER_RE = re.compile(
    r"""
    (?:^|\n)                      # start of line
    \s*
    (?:\d+\[\s*)?                 # optional amendment marker like '1['
    (\d{1,3}[A-Z]?)                # section number, e.g. 19, 19A
    \.\s*                          # period after number
    ([A-Z\u201c"](?:(?!\n\s*\n)[^\u2014\u2013])  # title: starts with capital/quote,
     {2,320}?)                     # then any char except em/en-dash, never
                                    # crossing a blank line (paragraph break)
    \.?\s*[\u2014\u2013]            # closing period (optional) then em- or en-dash
    """,
    re.VERBOSE,
)

FOOTNOTE_LINE_RE = re.compile(
    r"^\s*\d{1,2}\.\s*(Subs\.|Ins\.|Rep\.|See\b|Cf\.|C\.f\.|For the Statement|For an Exception|"
    r"For limitation|The words|As to|S\.\s*\d|Ss\.\s*\d|This Act|But\b)",
)

# BUG FIX (#5): once we hit the trailing repealed-chapter listing (entries
# like "239. ['Partnership' defined.] Rep. by ..." have NO em-dash, so they
# never match as real sections and the genuinely-last real section's body
# was silently swallowing this whole tail as garbage text). Detect that tail
# and cut it off before assigning it to the last section's body.
REPEALED_TAIL_RE = re.compile(
    r"\nCHAPTER\s+[IVXLC]+\.*\s*[\u2014-]*\s*\[.*?Rep\. by",
)

# BUG FIX (#6): the genuinely-last real section in an Act often runs straight
# into "THE FIRST SCHEDULE", "THE SECOND SCHEDULE", etc. with no section
# header in between to bound it (especially when the sections right after it
# are themselves omitted stubs that get stripped away). Truncate at the
# first Schedule heading, same idea as REPEALED_TAIL_RE.
# BUG FIX (#7b): also match the bare 'THE SCHEDULE.' used by some older Acts
# (e.g. Prisons Act 1894) and any Schedule heading regardless of ordinal.
SCHEDULE_TAIL_RE = re.compile(
    r"\n\s*\d*\[?\s*THE\s+(?:(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH)\s+)?SCHEDULE\b",
)

# BUG FIX (#7c): Detect where Schedule content starts in the operative text so
# that false SECTION_HEADER_RE hits inside Schedule bodies (e.g. the NY
# Convention Articles or IBA conflict-list items in the Arbitration Act) can be
# suppressed.  We look for any 'THE [ORDINAL] SCHEDULE' or bare 'THE SCHEDULE'
# heading line.
SCHEDULE_START_RE = re.compile(
    r"\n[ \t]*\d*\[?[ \t]*THE\s+(?:(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH)\s+)?SCHEDULE\b",
)


def is_repealed_title(title: str) -> bool:
    return "repealed" in title.lower()


def split_into_sections(operative_text: str, act_name: str):
    matches = list(SECTION_HEADER_RE.finditer(operative_text))

    # BUG FIX (#7c): find the earliest Schedule heading that appears *after* the
    # first real section match, so we don't accidentally hit a TOC listing of
    # schedule names that precedes all section text (Arbitration Act does this).
    # Any SECTION_HEADER_RE match falling inside a Schedule body is dropped.
    first_sec_pos = matches[0].start() if matches else 0
    sched_start = len(operative_text)  # default: no Schedule found
    sm = SCHEDULE_START_RE.search(operative_text, first_sec_pos)
    if sm:
        sched_start = sm.start()
    matches = [m for m in matches if m.start() < sched_start]
    sections = []

    for i, m in enumerate(matches):
        sec_num = m.group(1)
        title = m.group(2).strip()
        title = re.sub(r"\s*\n\s*", " ", title)
        title = title.replace("\u201c", '"').replace("\u201d", '"').strip()

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(operative_text)
        body = operative_text[body_start:body_end]

        # Cut off a trailing fully-repealed chapter listing or Schedule
        # section if this is the last real section in the Act (see BUG
        # FIXES #5 and #6 above). Use whichever tail marker appears first.
        tail_positions = []
        m1 = REPEALED_TAIL_RE.search(body)
        if m1:
            tail_positions.append(m1.start())
        m2 = SCHEDULE_TAIL_RE.search(body)
        if m2:
            tail_positions.append(m2.start())
        if tail_positions:
            body = body[:min(tail_positions)]

        body_lines = body.split("\n")
        clean_lines = [ln for ln in body_lines if not FOOTNOTE_LINE_RE.match(ln)]
        body = "\n".join(clean_lines).strip()
        body = re.sub(r"\n{2,}", "\n", body)

        if is_repealed_title(title):
            continue
        if len(body) < 5:
            continue

        preceding = operative_text[:m.start()]
        chapter_match = list(re.finditer(r"CHAPTER\s+(?:[IVXLC]+|\d+)\b.*", preceding))
        chapter = chapter_match[-1].group().strip() if chapter_match else None
        has_state_amendment = "STATE AMENDMENT" in body

        sections.append({
            "source": act_name,
            "section": sec_num,
            "title": title,
            "chapter": chapter,
            "text": body,
            "has_state_amendment": has_state_amendment,
            "type": "act_section",
        })

    return sections


# ---------- Step 5: orchestrate ----------

def parse_act(pdf_path: str, output_dir: str = "data/processed"):
    pdf_path = Path(pdf_path)
    act_name = pdf_path.stem.strip().title()

    raw_text = extract_text(str(pdf_path))
    operative_text = find_operative_text_start(raw_text)
    operative_text = clean_text(operative_text)

    sections = split_into_sections(operative_text, act_name)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^a-z0-9]+", "_", act_name.lower()).strip("_")
    out_path = out_dir / f"{slug}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, indent=2, ensure_ascii=False)

    print(f"Parsed {len(sections)} sections from '{act_name}'")
    print(f"Saved to: {out_path}")
    return sections


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_act.py <path_to_pdf>")
        sys.exit(1)

    parse_act(sys.argv[1])