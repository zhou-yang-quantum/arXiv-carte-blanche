"""Import a dated ChatGPT digest of up to twenty ranked papers into the archive."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_PAPERS = 1
MAX_PAPERS = 20
TOPICS = {
    "Quantum field theory": r"field theor|worldline|instantons|matrix.model|topological order|fusion",
    "Non-equilibrium": r"dissipat|dynamics|chaos|Krylov|OTOC|thermal|non.equilibrium",
    "Quantum error correction": r"error correction|QEC|QLDPC|qLDPC|code surgery|stabilizer|GKP",
    "Quantum simulation": r"quantum simulat|matrix.model|digital simulat|analog simulat",
    "Quantum algorithms": r"quantum algorithm|compilation|state preparation|code surgery",
    "Exactly solvable models": r"integrab|exact |exactly|Gaussian|Kitaev|Lanczos",
    "Statistical mechanics": r"partition function|cluster expansion|statistical mechanic|Boltzmann|hydrodynamic",
}


def clean(text):
    text = re.sub(r"\ue200url\ue202([^\ue201]+)\ue202(https?://[^\ue201]+)\ue201", r"[\1](\2)", text)
    text = re.sub(r"\ue200[^\ue201]*\ue201", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_digest(text):
    date_match = re.search(r"^#\s+arXiv-(\d{4}-\d{2}-\d{2})\s*$", text, re.M)
    if not date_match:
        raise ValueError("Digest must start with # arXiv-YYYY-MM-DD")
    date = date_match.group(1)
    import datetime
    datetime.date.fromisoformat(date)
    headers = list(re.finditer(r"^##\s+arXiv-(\d{4}-\d{2}-\d{2})\s+[—–-]\s+Item\s+(\d+)\s*$", text, re.M))
    if not headers:
        raise ValueError("Missing dated item headings")
    if any(h.group(1) != date for h in headers):
        raise ValueError("Every item must use the digest date")
    papers = []
    day_notes = ""
    for index, header in enumerate(headers):
        chunk = text[header.end():headers[index + 1].start() if index + 1 < len(headers) else len(text)].strip()
        if index == len(headers) - 1:
            # Reading advice belongs to the day, not to the final paper.
            parts = re.split(r"\n(?=My reading order|Suggested reading order|## Reading order)", chunk, maxsplit=1)
            chunk = parts[0]
            if len(parts) == 2:
                day_notes = clean(parts[1].split("\n---")[0])
        title = re.search(r"^###\s+(.+)$", chunk, re.M)
        metadata = re.search(r"^\*\*([^\n]*arXiv:[^\n]*?)\*\*[ \t]*$", chunk, re.M | re.I)
        arxiv = re.search(r"arXiv:\s*([a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?\b", metadata.group(1), re.I) if metadata else None
        # Older archived digests may contain a verdict. New ones omit it.
        priority = re.search(r"^\*\*Priority:\s*(.*?)\*\*[ \t]*$", chunk, re.M)
        background = re.search(r"\*\*Background[.:]?\*\*", chunk)
        why = re.search(r"\*\*Why it matters(?: for you)?[.?:]?\*\*", chunk)
        if not all((title, metadata, arxiv, background, why)):
            raise ValueError(f"Item {header.group(2)} is missing a title, arXiv metadata, background, or relevance section")
        if not (title.end() < metadata.start() < metadata.end() < background.start() < why.start()):
            raise ValueError("Summary, background, and relevance must appear in that order")
        if priority and not (metadata.end() <= priority.start() < priority.end() < background.start()):
            raise ValueError("Legacy priority line must precede the summary")
        authors = re.sub(r"\s*[—–-]?\s*arXiv:.*", "", metadata.group(1), flags=re.I).strip()
        summary = clean(chunk[priority.end() if priority else metadata.end():background.start()])
        relevance = clean(chunk[why.end():])
        relevance = re.sub(r"\n*\[arXiv[^\]]*\]\(https://arxiv.org/abs/[^)]+\)\s*$", "", relevance).strip()
        tags = [tag for tag, pattern in TOPICS.items() if re.search(pattern, title.group(1) + " " + summary, re.I)]
        paper = {
            "rank": int(header.group(2)), "id": arxiv.group(1), "title": title.group(1),
            "authors": authors, "topics": tags,
            "summary": summary, "background": clean(chunk[background.end():why.start()]),
            "why": relevance, "url": f"https://arxiv.org/abs/{arxiv.group(1)}",
        }
        if not all(paper[key] for key in ("summary", "background", "why")):
            raise ValueError(f"Item {header.group(2)} has an empty explanatory section")
        if priority:
            paper["priority"] = priority.group(1)
        papers.append(paper)
    count = len(papers)
    expected_ranks = list(range(1, count + 1))
    if not MIN_PAPERS <= count <= MAX_PAPERS or [p["rank"] for p in papers] != expected_ranks:
        raise ValueError(f"Expected {MIN_PAPERS}–{MAX_PAPERS} items with consecutive ranks starting at 1")
    if len({p["id"] for p in papers}) != count:
        raise ValueError("Duplicate paper IDs in digest")
    order_match = re.search(r"reading order.*?\*\*(.*?)\*\*", day_notes, re.I)
    order = [int(n) for n in re.findall(r"\d+", order_match.group(1))] if order_match else expected_ranks
    if sorted(order) != expected_ranks:
        order = expected_ranks
    return {
        "date": date, "title": f"arXiv-{date}",
        "overview": clean(text[date_match.end():headers[0].start()]),
        "source": "ChatGPT selection", "reading_order": order, "notes": day_notes, "papers": papers,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--replace", action="store_true", help="Explicitly replace an existing date")
    args = parser.parse_args()
    digest = parse_digest(args.markdown.read_text(encoding="utf-8-sig"))
    folder = ROOT / "content" / "digests"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{digest['date']}.json"
    if target.exists() and not args.replace:
        raise SystemExit(f"{target.name} already exists; use --replace to update it")
    target.write_text(json.dumps(digest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {digest['title']}: {len(digest['papers'])} papers")


if __name__ == "__main__":
    main()
