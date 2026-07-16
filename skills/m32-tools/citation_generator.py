#!/usr/bin/env python3
"""
citation_generator.py — Generator sitasi akademik 7 style.

Support: APA 7th, IEEE, Harvard, Vancouver, Chicago, MLA 9th, ABNT.

Usage CLI:
  python3 citation_generator.py --style apa --type journal \
    --author "Smith" --year 2023 --title "Effects of AI" \
    --journal "J Edu Tech" --volume 15 --issue 3 --pages "45-67" \
    --doi "10.1234/jet.2023.001"

Usage import:
  from citation_generator import generate_citation
  result = generate_citation(style="apa", ctype="journal", **kwargs)
"""

import argparse
import json
import sys


def _format_authors_apa(authors: list) -> str:
    """Format author names untuk APA: Last, F. F."""
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = ". ".join([p[0].upper() + "." for p in parts[:-1]])
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(a)
    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) == 2:
        return f"{formatted[0]} & {formatted[1]}"
    elif len(formatted) <= 20:
        return ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
    else:
        return ", ".join(formatted[:19]) + f", ... {formatted[-1]}"


def _format_authors_ieee(authors: list) -> str:
    """Format untuk IEEE: F. F. Last"""
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = " ".join([p[0].upper() + "." for p in parts[:-1]])
            formatted.append(f"{initials} {last}")
        else:
            formatted.append(a)
    if len(formatted) <= 6:
        return ", ".join(formatted)
    else:
        return ", ".join(formatted[:6]) + ", et al."


def _format_authors_harvard(authors: list) -> str:
    """Format untuk Harvard: Last, F."""
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = "".join([p[0].upper() + "." for p in parts[:-1]])
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(a)
    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    else:
        return ", ".join(formatted[:-1]) + f" and {formatted[-1]}"


def _format_authors_vancouver(authors: list) -> str:
    """Format untuk Vancouver: Last AA"""
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            initials = "".join([p[0].upper() for p in parts[:-1]])
            formatted.append(f"{last} {initials}")
        else:
            formatted.append(a)
    if len(formatted) <= 6:
        return ", ".join(formatted)
    else:
        return ", ".join(formatted[:6]) + ", et al."


def _format_authors_mla(authors: list) -> str:
    """Format untuk MLA: Last, First."""
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1]
            first = " ".join(parts[:-1])
            formatted.append(f"{last}, {first}")
        else:
            formatted.append(a)
    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) == 2:
        return f"{formatted[0]} and {formatted[1]}"
    else:
        return f"{formatted[0]} et al."


def _format_authors_abnt(authors: list) -> str:
    """Format untuk ABNT: LAST, A."""
    formatted = []
    for a in authors:
        parts = a.strip().split()
        if len(parts) >= 2:
            last = parts[-1].upper()
            initials = " ".join([p[0].upper() + "." for p in parts[:-1]])
            formatted.append(f"{last}, {initials}")
        else:
            formatted.append(a.upper())
    return "; ".join(formatted)


def generate_citation(style: str, ctype: str, **kw) -> dict:
    """Generate citation dalam format yang diminta.
    
    Args:
        style: apa, ieee, harvard, vancouver, chicago, mla, abnt
        ctype: journal, book, conference, website, thesis
        **kw: author (str or list), year, title, journal, volume, issue,
              pages, doi, url, publisher, city, accessed, degree, university
    
    Returns:
        {"in_text": str, "reference": str}
    """
    # Normalize author to list
    author = kw.get("author", "")
    if isinstance(author, str):
        authors = [a.strip() for a in author.split(";") if a.strip()]
        if not authors and author:
            authors = [author]
    else:
        authors = author

    year = kw.get("year", "")
    title = kw.get("title", "")
    journal = kw.get("journal", "")
    volume = kw.get("volume", "")
    issue = kw.get("issue", "")
    pages = kw.get("pages", "")
    doi = kw.get("doi", "")
    url = kw.get("url", "")
    publisher = kw.get("publisher", "")
    city = kw.get("city", "")
    accessed = kw.get("accessed", "")
    edition = kw.get("edition", "")
    degree = kw.get("degree", "")
    university = kw.get("university", "")

    result = {"in_text": "", "reference": ""}

    if style == "apa":
        auth_str = _format_authors_apa(authors)
        if ctype == "journal":
            result["reference"] = f"{auth_str} ({year}). {title}. {journal}, {volume}({issue}), {pages}."
            if doi:
                result["reference"] += f" https://doi.org/{doi}"
            elif url:
                result["reference"] += f" {url}"
        elif ctype == "book":
            ed = f" ({edition} ed.)" if edition else ""
            result["reference"] = f"{auth_str} ({year}). {title}{ed}. {publisher}."
        elif ctype == "conference":
            result["reference"] = f"{auth_str} ({year}). {title}. In Proceedings of {journal} (pp. {pages}). {publisher}."
        elif ctype == "website":
            result["reference"] = f"{auth_str} ({year}). {title}. {journal}. {url}"
        elif ctype == "thesis":
            result["reference"] = f"{auth_str} ({year}). {title} [{degree} thesis, {university}]. {url}"

        # In-text
        if len(authors) == 1:
            last = authors[0].split()[-1]
            result["in_text"] = f"({last}, {year})"
        elif len(authors) == 2:
            lasts = [a.split()[-1] for a in authors]
            result["in_text"] = f"({lasts[0]} & {lasts[1]}, {year})"
        else:
            last = authors[0].split()[-1]
            result["in_text"] = f"({last} et al., {year})"

    elif style == "ieee":
        auth_str = _format_authors_ieee(authors)
        if ctype == "journal":
            # Abbreviate journal name (simple: just use as-is)
            result["reference"] = f'{auth_str}, "{title}," {journal}, vol. {volume}, no. {issue}, pp. {pages}, {year}.'
            if doi:
                result["reference"] += f" doi: {doi}."
        elif ctype == "book":
            ed = f", {edition} ed." if edition else ""
            result["reference"] = f"{auth_str}, {title}{ed}. {city}: {publisher}, {year}."
        elif ctype == "conference":
            result["reference"] = f'{auth_str}, "{title}," in Proc. {journal}, {year}, pp. {pages}.'
        elif ctype == "website":
            acc = f" [Accessed: {accessed}]" if accessed else ""
            result["reference"] = f'"{title}," {journal}. [Online]. Available: {url}.{acc}'
        elif ctype == "thesis":
            result["reference"] = f'{auth_str}, "{title}," {degree} thesis, {university}, {year}.'
        result["in_text"] = f"[{1}]"  # placeholder, user assigns number

    elif style == "harvard":
        auth_str = _format_authors_harvard(authors)
        if ctype == "journal":
            result["reference"] = f"{auth_str} ({year}) '{title}', {journal}, {volume}({issue}), pp. {pages}."
            if doi:
                result["reference"] += f" doi: {doi}"
        elif ctype == "book":
            ed = f" {edition} edn." if edition else ""
            result["reference"] = f"{auth_str} ({year}) {title}.{ed} {city}: {publisher}."
        elif ctype == "conference":
            result["reference"] = f"{auth_str} ({year}) '{title}', in Proceedings of {journal}, pp. {pages}."
        elif ctype == "website":
            result["reference"] = f"{auth_str} ({year}) '{title}', {journal}. Available at: {url}"
        if len(authors) == 1:
            last = authors[0].split()[-1]
            result["in_text"] = f"({last}, {year})"
        elif len(authors) == 2:
            lasts = [a.split()[-1] for a in authors]
            result["in_text"] = f"({lasts[0]} and {lasts[1]}, {year})"
        else:
            last = authors[0].split()[-1]
            result["in_text"] = f"({last} et al., {year})"

    elif style == "vancouver":
        auth_str = _format_authors_vancouver(authors)
        if ctype == "journal":
            # Abbreviate journal (simple)
            result["reference"] = f"{auth_str}. {title}. {journal}. {year};{volume}({issue}):{pages}."
            if doi:
                result["reference"] += f" doi: {doi}"
        elif ctype == "book":
            ed = f" {edition} ed." if edition else ""
            result["reference"] = f"{auth_str}. {title}{ed}. {city}: {publisher}; {year}."
        elif ctype == "conference":
            result["reference"] = f"{auth_str}. {title}. In: Proceedings of {journal}. {year}. p. {pages}."
        elif ctype == "website":
            result["reference"] = f"{auth_str}. {title}. {journal}. {year}. Available from: {url}"
        elif ctype == "thesis":
            result["reference"] = f"{auth_str}. {title} [{degree} thesis]. {university}; {year}."
        result["in_text"] = f"[{1}]"  # placeholder

    elif style == "chicago":
        if ctype == "journal":
            auth_str = _format_authors_apa(authors)  # similar format
            result["reference"] = f'{auth_str}. {year}. "{title}." {journal} {volume}, no. {issue}: {pages}.'
            if doi:
                result["reference"] += f" https://doi.org/{doi}"
        elif ctype == "book":
            auth_str = _format_authors_mla(authors)
            ed = f", {edition} ed." if edition else ""
            result["reference"] = f"{auth_str}. {title}{ed}. {city}: {publisher}, {year}."
        elif ctype == "website":
            auth_str = _format_authors_apa(authors)
            result["reference"] = f'{auth_str}. "{title}." {journal}. {url}.'
        # Chicago footnote format
        if len(authors) == 1:
            parts = authors[0].split()
            first = " ".join(parts[:-1])
            last = parts[-1]
            result["in_text"] = f"{first} {last}, {title}"
        else:
            result["in_text"] = f"{authors[0].split()[-1]} et al., {title}"

    elif style == "mla":
        auth_str = _format_authors_mla(authors)
        if ctype == "journal":
            result["reference"] = f'{auth_str}. "{title}." {journal}, vol. {volume}, no. {issue}, {year}, pp. {pages}.'
            if doi:
                result["reference"] += f" {doi}"
        elif ctype == "book":
            ed = f" {edition} ed.," if edition else ""
            result["reference"] = f"{auth_str}. {title}.{ed} {publisher}, {year}."
        elif ctype == "website":
            result["reference"] = f'{auth_str}. "{title}." {journal}, {year}, {url}.'
        elif ctype == "thesis":
            result["reference"] = f'{auth_str}. "{title}." {degree} thesis, {university}, {year}.'
        # In-text: (Last page)
        last = authors[0].split()[-1] if authors else "Author"
        result["in_text"] = f"({last} {pages.split('-')[0]})" if pages else f"({last})"

    elif style == "abnt":
        auth_str = _format_authors_abnt(authors)
        if ctype == "journal":
            result["reference"] = f"{auth_str}. {title}. {journal}, {city}, v. {volume}, n. {issue}, p. {pages}, {year}."
        elif ctype == "book":
            ed = f" {edition}. ed." if edition else ""
            result["reference"] = f"{auth_str}. {title}.{ed} {city}: {publisher}, {year}."
        elif ctype == "conference":
            result["reference"] = f"{auth_str}. {title}. In: {journal}, {year}. p. {pages}."
        elif ctype == "website":
            result["reference"] = f"{auth_str}. {title}. {journal}. Disponível em: {url}. Acesso em: {accessed}."
        elif ctype == "thesis":
            result["reference"] = f"{auth_str}. {title} [{degree}]. {university}, {year}."
        # In-text: (AUTHOR, year) uppercase
        last = authors[0].split()[-1].upper() if authors else "AUTHOR"
        result["in_text"] = f"({last}, {year})"

    else:
        result["reference"] = f"Unknown style: {style}"
        result["in_text"] = ""

    return result


def cli():
    parser = argparse.ArgumentParser(description="Academic Citation Generator")
    parser.add_argument("--style", required=True,
                        choices=["apa", "ieee", "harvard", "vancouver", "chicago", "mla", "abnt"])
    parser.add_argument("--type", required=True,
                        choices=["journal", "book", "conference", "website", "thesis"])
    parser.add_argument("--author", required=True, help="Author name(s), semicolon-separated")
    parser.add_argument("--year", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--journal", default="")
    parser.add_argument("--volume", default="")
    parser.add_argument("--issue", default="")
    parser.add_argument("--pages", default="")
    parser.add_argument("--doi", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--publisher", default="")
    parser.add_argument("--city", default="")
    parser.add_argument("--edition", default="")
    parser.add_argument("--accessed", default="")
    parser.add_argument("--degree", default="")
    parser.add_argument("--university", default="")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = generate_citation(
        style=args.style, ctype=args.type,
        author=args.author, year=args.year, title=args.title,
        journal=args.journal, volume=args.volume, issue=args.issue,
        pages=args.pages, doi=args.doi, url=args.url,
        publisher=args.publisher, city=args.city, edition=args.edition,
        accessed=args.accessed, degree=args.degree, university=args.university
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"In-text: {result['in_text']}")
        print(f"Reference: {result['reference']}")


if __name__ == "__main__":
    cli()
