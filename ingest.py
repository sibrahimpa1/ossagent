"""
ingest.py — Ayurveda App PDF Extractor
Run once from project root: python ingest.py

Reads 4 Ayurveda PDFs from data/pdfs/ and writes data/chunks.json
Each chunk is one complete recipe (or theory section) with dosha tags.

Requirements: pip install pdfplumber
"""

import json
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────

PDF_FILES = {
    "Ayurveda Cookbook (Alagna)":       "data/pdfs/alagna.pdf",
    "The Easy Ayurveda Cookbook":        "data/pdfs/easy_ayurveda.pdf",
    "The Flavors of Ayurveda":           "data/pdfs/flavors_ayurveda.pdf",
    "Healing the Thyroid with Ayurveda": "data/pdfs/thyroid_ayurveda.pdf",
}

OUTPUT_PATH = Path("data/chunks.json")

# ── Helpers ────────────────────────────────────────────────────────────────────

TRIDOSHIC_KW = [
    "tridoshic", "tri-doshic", "suitable for all three", "balances all",
    "good for all doshas", "all three doshas", "suitable for all", "all dosha",
]

# Alagna PDF has garbled 2-column OCR: "P B B\nITTA EVERAGES" → PITTA
GARBLED_DOSHA_RE = re.compile(r"\b([VPK])(?:[^\n]*)?\n(ATA|ITTA|APHA)\b")
GARBLED_CHAPTER_RE = re.compile(r"\bC(?:[^\n]*)?\nHAPTER\b")

RECIPE_CONTENT_RE = re.compile(
    r"cup|tablespoon|teaspoon|what you need|ingredients|preparation|step \d|ghee|dal|rice\b",
    re.I,
)


def fix_alagna_garbling(text: str) -> str:
    """Fix garbled 2-column headers in Alagna PDF."""
    dosha_lookup = {"V": "VATA", "P": "PITTA", "K": "KAPHA"}
    text = GARBLED_DOSHA_RE.sub(lambda m: f"[{dosha_lookup[m.group(1)]}]", text)
    text = GARBLED_CHAPTER_RE.sub("CHAPTER", text)
    return text


def is_tridoshic(text: str) -> bool:
    tl = text.lower()
    return any(kw in tl for kw in TRIDOSHIC_KW)


def detect_doshas(text: str) -> list[str]:
    tl = text.lower()
    found = set()
    if "vata" in tl:  found.add("vata")
    if "pitta" in tl: found.add("pitta")
    if "kapha" in tl: found.add("kapha")
    return sorted(found)


def recipe_name_from(text: str, max_len: int = 80) -> str:
    """Extract recipe name = first short, non-ingredient, non-step line."""
    skip = re.compile(
        r"^(step|what you|how to|ingredients|prep|cook|serves|makes|\d+[\.\)]|preparation)",
        re.I,
    )
    for line in text.splitlines():
        s = line.strip()
        if s and 4 < len(s) < max_len and not skip.match(s):
            return s
    return text.strip()[:60] if text.strip() else "Unknown"


def trim_chunk(text: str, max_chars: int = 3500) -> str:
    """Trim text to max_chars at a clean boundary."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    cut = max(truncated.rfind("\n\n"), truncated.rfind(". "))
    if cut > max_chars * 0.7:
        return truncated[:cut + 1].strip()
    return truncated.strip()


def make_chunk(
    source: str,
    text: str,
    doshas: list[str],
    tridoshic: bool,
    page: int,
    is_recipe: bool,
) -> dict:
    return {
        "source": source,
        "recipe_name": recipe_name_from(text) if is_recipe else None,
        "doshas": doshas,
        "tridoshic": tridoshic,
        "pages": page,
        "text": trim_chunk(text),
        "is_recipe": is_recipe,
    }


# ── Per-book extractors ────────────────────────────────────────────────────────

def extract_alagna(pdf) -> list[dict]:
    """
    Alagna Ayurveda Cookbook.
    Structure: VATA / PITTA / KAPHA section headers, then recipe title + 'What you need:'.
    PDF has garbled 2-column OCR that needs normalising first.
    Each recipe is typically 1-2 pages. Dosha comes from section header, not recipe text.
    """
    # Build full text with page markers
    raw_parts = []
    for i, page in enumerate(pdf.pages):
        t = page.extract_text() or ""
        if t.strip():
            raw_parts.append(f"[[P{i+1}]]")
            raw_parts.append(t)
    raw = "\n".join(raw_parts)
    raw = fix_alagna_garbling(raw)

    chunks: list[dict] = []
    current_dosha = "vata"
    buf: list[str] = []
    buf_page = 1

    def flush(buf: list[str], dosha: str, page: int) -> None:
        raw_text = "\n".join(buf)
        # Strip markers
        text = re.sub(r"\[\[P\d+\]\]", "", raw_text).strip()
        text = re.sub(r"\[(VATA|PITTA|KAPHA)\][^\n]*\n?", "", text).strip()
        if len(text) < 80:
            return
        is_recipe = bool(re.search(r"what you need|what to do|how to make", text, re.I))
        chunks.append(make_chunk(
            source="Ayurveda Cookbook (Alagna)",
            text=text, doshas=[dosha], tridoshic=False,
            page=page, is_recipe=is_recipe,
        ))

    for line in raw.split("\n"):
        # Page marker
        pm = re.match(r"\[\[P(\d+)\]\]", line)
        if pm:
            buf_page = int(pm.group(1))
            buf.append(line)
            continue

        # Dosha section change
        dm = re.match(r"\[(VATA|PITTA|KAPHA)\]", line)
        if dm:
            flush(buf, current_dosha, buf_page)
            current_dosha = dm.group(1).lower()
            buf = [line]
            continue

        # Recipe boundary: "What you need:" — look back for title
        if re.match(r"What you need:", line.strip()) and buf:
            prev_content = [
                l.strip() for l in buf
                if l.strip()
                and not l.startswith("[[")
                and not re.match(r"\[", l)
            ]
            if prev_content:
                last_line = prev_content[-1]
                if (
                    len(last_line) < 70
                    and not re.match(
                        r"^(step|what|how|ghee|water|oil|salt|cup|tbsp|tsp|"
                        r"tablespoon|teaspoon|\d+|\.|\[)",
                        last_line, re.I,
                    )
                    and len(prev_content) > 1
                ):
                    # Find that line in buf and split there
                    split_idx = len(buf) - 1
                    while split_idx > 0 and buf[split_idx].strip() != last_line:
                        split_idx -= 1
                    if split_idx > 0:
                        flush(buf[:split_idx], current_dosha, buf_page)
                        buf = buf[split_idx:]

        buf.append(line)

    flush(buf, current_dosha, buf_page)
    return chunks


def extract_easy_ayurveda(pdf) -> list[dict]:
    """
    The Easy Ayurveda Cookbook (Rockridge Press).
    Each recipe has an ALL-CAPS title followed by PREP TIME / COOK TIME.
    Dosha notes are specific: 'Vatas can add X', 'Pittas should omit Y'.
    """
    all_lines: list[tuple[int, str]] = []
    for i, page in enumerate(pdf.pages):
        t = page.extract_text() or ""
        for line in t.split("\n"):
            all_lines.append((i + 1, line))

    chunks: list[dict] = []

    # Find recipe title boundaries (line before PREP TIME)
    boundaries: list[tuple[int, int]] = []  # (title_line_idx, page)
    for i, (pnum, line) in enumerate(all_lines):
        if re.match(r"\s*PREP\s+TIME", line):
            for j in range(i - 1, max(0, i - 8), -1):
                prev = all_lines[j][1].strip()
                if prev and len(prev) > 3 and not re.match(
                    r"^(prep|cook|serves|\d)", prev, re.I
                ):
                    boundaries.append((j, all_lines[j][0]))
                    break

    def flush(line_slice: list[tuple[int, str]], start_page: int) -> None:
        text = "\n".join(l for _, l in line_slice).strip()
        if len(text) < 100:
            return
        # Skip pure preamble blobs (table of contents, intro chapters)
        if len(text) > 8000 and not RECIPE_CONTENT_RE.search(text):
            return

        tridoshic = is_tridoshic(text)
        dosha_notes = re.findall(
            r"\b(Vata|Pitta|Kapha)s?\s+(?:can|should|may|will|add|omit|use|substitute|"
            r"increase|decrease)",
            text, re.I,
        )
        specific = sorted(set(d.lower() for d in dosha_notes))
        doshas = ["kapha", "pitta", "vata"] if tridoshic else (specific or detect_doshas(text))
        is_recipe = bool(re.search(r"cup|tablespoon|teaspoon|\d\.\s", text, re.I))

        chunks.append(make_chunk(
            source="The Easy Ayurveda Cookbook",
            text=text, doshas=doshas, tridoshic=tridoshic,
            page=start_page, is_recipe=is_recipe,
        ))

    prev = 0
    prev_page = all_lines[0][0] if all_lines else 1
    for title_idx, pnum in boundaries:
        if title_idx > prev:
            flush(all_lines[prev:title_idx], prev_page)
        prev = title_idx
        prev_page = pnum
    flush(all_lines[prev:], prev_page)
    return chunks


def extract_flavors(pdf) -> list[dict]:
    """
    The Flavors of Ayurveda (Hemangi Devi Dasi).
    Each recipe starts with its name then 'Preparation: X min' or 'Preparation time: X min'.
    Dosha suitability: 'Suitable for vata and pitta' / 'not recommended to pitta'.
    """
    pages = []
    for i, page in enumerate(pdf.pages):
        t = page.extract_text() or ""
        if t.strip():
            pages.append((i + 1, t))

    chunks: list[dict] = []
    buf: list[str] = []
    buf_page = 1

    def flush() -> None:
        text = "\n".join(buf).strip()
        if len(text) < 80:
            return
        # Skip huge intro blobs
        if len(text) > 8000 and not RECIPE_CONTENT_RE.search(text):
            return

        tridoshic = is_tridoshic(text) or bool(
            re.search(r"suitable for all", text, re.I)
        )
        suitable = re.findall(r"[Ss]uitable for (\w+)", text)
        not_rec = re.findall(r"not recommended (?:to|for) (\w+)", text)

        if tridoshic:
            doshas = ["kapha", "pitta", "vata"]
        elif suitable:
            doshas = sorted(
                set(d.lower() for d in suitable if d.lower() in ("vata", "pitta", "kapha"))
            ) or detect_doshas(text)
        else:
            doshas = detect_doshas(text)

        for nr in not_rec:
            if nr.lower() in doshas:
                doshas.remove(nr.lower())

        is_recipe = bool(
            re.search(r"Preparation|tablespoon|teaspoon|ghee|ml\b", text, re.I)
        )
        chunks.append(make_chunk(
            source="The Flavors of Ayurveda",
            text=text, doshas=doshas, tridoshic=tridoshic,
            page=buf_page, is_recipe=is_recipe,
        ))

    for pnum, text in pages:
        # Split at Preparation: boundaries (may have multiple recipes per page)
        parts = re.split(
            r"(?=^Preparation(?:\s+time)?[:\s])", text, flags=re.MULTILINE
        )
        for part in parts:
            if re.match(r"Preparation", part.strip(), re.I):
                flush()
                buf = [part]
                buf_page = pnum
            else:
                buf.append(part)

    flush()
    return chunks


def extract_thyroid(pdf) -> list[dict]:
    """
    Healing the Thyroid with Ayurveda (Teitelbaum).
    Mostly Ayurvedic theory — valuable for WHY certain foods help imbalances.
    Chunk by chapter. Tag doshas from text.
    """
    chunks: list[dict] = []
    buf: list[str] = []
    buf_page = 1
    cur_doshas: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if len(text) < 200:
            return
        doshas = detect_doshas(text) or cur_doshas
        is_recipe = bool(
            re.search(r"tablespoon|teaspoon|ingredients|recipe", text, re.I)
        )
        chunks.append(make_chunk(
            source="Healing the Thyroid with Ayurveda",
            text=text, doshas=doshas,
            tridoshic=set(doshas) == {"vata", "pitta", "kapha"},
            page=buf_page, is_recipe=is_recipe,
        ))

    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        if not text.strip():
            continue
        is_chapter = bool(
            re.search(r"^(Chapter|CHAPTER)\s+\d+", text, re.MULTILINE)
        )
        too_long = len("\n".join(buf)) > 3000

        if is_chapter or too_long:
            flush()
            buf = [text]
            buf_page = i + 1
            sd = re.findall(r"\b(vata|pitta|kapha)\b", text[:300], re.I)
            if sd:
                cur_doshas = list(set(d.lower() for d in sd))
        else:
            buf.append(text)

    flush()
    return chunks


# ── Main ───────────────────────────────────────────────────────────────────────

EXTRACTORS = {
    "Ayurveda Cookbook (Alagna)":       extract_alagna,
    "The Easy Ayurveda Cookbook":        extract_easy_ayurveda,
    "The Flavors of Ayurveda":           extract_flavors,
    "Healing the Thyroid with Ayurveda": extract_thyroid,
}


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict] = []
    missing: list[str] = []

    for source_name, pdf_path_str in PDF_FILES.items():
        pdf_path = Path(pdf_path_str)
        if not pdf_path.exists():
            print(f"  ⚠️  Not found: {pdf_path} — skipping {source_name}")
            missing.append(pdf_path_str)
            continue

        print(f"📖 Processing: {source_name} ({pdf_path.stat().st_size // 1024}KB)...")
        with pdfplumber.open(pdf_path) as pdf:
            chunks = EXTRACTORS[source_name](pdf)

        recipes = [c for c in chunks if c["is_recipe"]]
        dd: dict[str, int] = {}
        for c in chunks:
            for d in c["doshas"]:
                dd[d] = dd.get(d, 0) + 1
        sizes = [len(c["text"]) for c in chunks]
        print(
            f"   → {len(chunks)} chunks | {len(recipes)} recipes | "
            f"sizes {min(sizes)}–{max(sizes)} avg={sum(sizes)//len(sizes)} | "
            f"doshas: {dd}"
        )
        all_chunks.extend(chunks)

    # Assign sequential IDs
    for i, c in enumerate(all_chunks):
        c["id"] = i

    # Summary
    total_recipes = sum(1 for c in all_chunks if c["is_recipe"])
    dd_all: dict[str, int] = {}
    for c in all_chunks:
        for d in c["doshas"]:
            dd_all[d] = dd_all.get(d, 0) + 1

    print(f"\n{'='*60}")
    print(f"✅ Total chunks:  {len(all_chunks)}")
    print(f"   Recipes:       {total_recipes}")
    print(f"   Dosha dist:    {dd_all}")

    if missing:
        print(f"\n⚠️  Missing PDFs ({len(missing)}):")
        for m in missing:
            print(f"   {m}")
        print("   App will work with the books that were found.")

    OUTPUT_PATH.write_text(
        json.dumps(all_chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n💾 Saved → {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size // 1024}KB)")
    print("\nNext step: run setup.sh to install dependencies and generate embeddings.")


if __name__ == "__main__":
    main()