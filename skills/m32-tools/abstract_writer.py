#!/usr/bin/env python3
"""
abstract_writer.py — Generator abstrak akademik (ID + EN).

Generate abstrak 150-250 kata dengan struktur:
- Latar belakang (1-2 kalimat)
- Tujuan (1 kalimat)
- Metode (2-3 kalimat)
- Hasil (2-3 kalimat)
- Kesimpulan (1-2 kalimat)

Usage CLI:
  python3 abstract_writer.py --background "..." --objective "..." --method "..." \\
    --results "..." --conclusion "..." --lang id --keywords "kata1, kata2, kata3"

Usage import:
  from abstract_writer import generate_abstract
  result = generate_abstract(background, objective, method, results, conclusion, lang="id")
"""

import argparse
import json
import re


def _count_words(text: str) -> int:
    return len(text.split())


def _trim_to_word_limit(text: str, max_words: int) -> str:
    """Trim text to max_words, cut at last complete sentence."""
    words = text.split()
    if len(words) <= max_words:
        return text

    trimmed = words[:max_words]
    text = " ".join(trimmed)

    # Try to end at last sentence boundary
    last_period = text.rfind(".")
    if last_period > len(text) * 0.8:  # only if we're not cutting too much
        text = text[:last_period + 1]

    return text


def generate_abstract(background: str, objective: str, method: str,
                      results: str, conclusion: str,
                      lang: str = "id", max_words: int = 250) -> dict:
    """Generate structured abstract.
    
    Args:
        background: latar belakang (1-2 kalimat)
        objective: tujuan penelitian (1 kalimat)
        method: metode penelitian (2-3 kalimat)
        results: hasil utama (2-3 kalimat)
        conclusion: kesimpulan (1-2 kalimat)
        lang: 'id' (Indonesia) or 'en' (English)
        max_words: maksimal kata (default 250)
    
    Returns:
        {
            "abstract": str,
            "word_count": int,
            "within_limit": bool,
            "keywords_suggested": list,
            "structure": dict,
        }
    """
    # Templates per language
    if lang == "id":
        templates = {
            "background": background.strip(),
            "objective": f"Penelitian ini bertujuan untuk {objective.strip().lower().rstrip('.')}.",
            "method": method.strip(),
            "results": results.strip(),
            "conclusion": conclusion.strip(),
        }
        connector = " "
    else:  # en
        templates = {
            "background": background.strip(),
            "objective": f"This study aims to {objective.strip().lower().rstrip('.')}.",
            "method": method.strip(),
            "results": results.strip(),
            "conclusion": conclusion.strip(),
        }
        connector = " "

    # Combine
    parts = [templates["background"], templates["objective"],
             templates["method"], templates["results"], templates["conclusion"]]

    # Filter empty parts
    parts = [p for p in parts if p]

    abstract = connector.join(parts)

    # Word count
    wc = _count_words(abstract)

    # Trim if needed
    if wc > max_words:
        abstract = _trim_to_word_limit(abstract, max_words)
        wc = _count_words(abstract)

    # Suggest keywords
    keywords = _suggest_keywords(abstract, lang)

    # Structure analysis
    structure = {
        "background_words": _count_words(templates["background"]),
        "objective_words": _count_words(templates["objective"]),
        "method_words": _count_words(templates["method"]),
        "results_words": _count_words(templates["results"]),
        "conclusion_words": _count_words(templates["conclusion"]),
    }

    return {
        "abstract": abstract,
        "word_count": wc,
        "within_limit": wc <= max_words,
        "max_words": max_words,
        "keywords_suggested": keywords,
        "structure": structure,
    }


def _suggest_keywords(text: str, lang: str = "id", max_keywords: int = 5) -> list:
    """Suggest keywords dari teks abstrak (simple frequency-based)."""
    # Remove common words
    stop_words_id = {
        "dan", "yang", "di", "ke", "dari", "untuk", "pada", "dengan", "ini",
        "itu", "atau", "dalam", "adalah", "akan", "juga", "oleh", "tidak",
        "penelitian", "hasil", "metode", "data", "the", "a", "an", "is",
        "are", "was", "were", "this", "study", "research", "method", "result",
        "and", "of", "to", "in", "for", "with", "on", "by", "from", "as",
        "that", "it", "be", "are", "has", "have", "was", "were", "been",
    }

    words = re.findall(r'\b[A-Za-z]{4,}\b', text.lower())
    freq = {}
    for word in words:
        if word not in stop_words_id:
            freq[word] = freq.get(word, 0) + 1

    # Sort by frequency
    sorted_words = sorted(freq.items(), key=lambda x: -x[1])

    # Take top keywords (deduplicate similar)
    keywords = []
    seen = set()
    for word, count in sorted_words:
        if word not in seen:
            keywords.append(word)
            seen.add(word)
        if len(keywords) >= max_keywords:
            break

    return keywords


def generate_abstract_from_draft(draft: str, lang: str = "id",
                                  max_words: int = 250) -> dict:
    """Generate abstrak dari draft panjang (auto-extract key sentences).
    
    Heuristic: ambil kalimat pertama (background), kalimat dengan "tujuan/aim",
    kalimat dengan "method/metode", kalimat dengan "hasil/result", kalimat dengan "kesimpulan/conclusion".
    """
    sentences = re.split(r'(?<=[.!?])\s+', draft.strip())

    background = ""
    objective = ""
    method = ""
    results = ""
    conclusion = ""

    keywords_map = {
        "id": {
            "objective": ["tujuan", "bertujuan", "penelitian ini"],
            "method": ["metode", "metodologi", "pendekatan", "teknik", "analisis"],
            "results": ["hasil", "temuan", "menunjukkan", "ditemukan"],
            "conclusion": ["kesimpulan", "simpulan", "dapat disimpulkan"],
        },
        "en": {
            "objective": ["aim", "objective", "purpose", "this study"],
            "method": ["method", "methodology", "approach", "technique", "analysis"],
            "results": ["result", "finding", "showed", "found", "demonstrated"],
            "conclusion": ["conclusion", "conclud", "in summary"],
        }
    }

    kw = keywords_map.get(lang, keywords_map["id"])

    for i, sent in enumerate(sentences):
        sent_lower = sent.lower()
        if i == 0 and not background:
            background = sent
        for key in kw["objective"]:
            if key in sent_lower and not objective:
                objective = sent
                break
        for key in kw["method"]:
            if key in sent_lower and not method:
                method = sent
                break
        for key in kw["results"]:
            if key in sent_lower and not results:
                results = sent
                break
        for key in kw["conclusion"]:
            if key in sent_lower and not conclusion:
                conclusion = sent
                break

    # Fallback: if some sections empty, use last sentences
    if not results and len(sentences) > 2:
        results = sentences[-2] if len(sentences) > 2 else ""
    if not conclusion and sentences:
        conclusion = sentences[-1]

    return generate_abstract(background, objective, method, results, conclusion,
                             lang=lang, max_words=max_words)


def cli():
    parser = argparse.ArgumentParser(description="Academic Abstract Generator")
    parser.add_argument("--background", default="", help="Background (1-2 sentences)")
    parser.add_argument("--objective", default="", help="Research objective")
    parser.add_argument("--method", default="", help="Method description")
    parser.add_argument("--results", default="", help="Key results")
    parser.add_argument("--conclusion", default="", help="Conclusion")
    parser.add_argument("--draft", default="", help="Full draft text (auto-extract)")
    parser.add_argument("--lang", default="id", choices=["id", "en"])
    parser.add_argument("--max-words", type=int, default=250)
    parser.add_argument("--keywords", default="", help="Manual keywords (comma-separated)")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.draft:
        result = generate_abstract_from_draft(args.draft, lang=args.lang,
                                               max_words=args.max_words)
    else:
        result = generate_abstract(
            background=args.background, objective=args.objective,
            method=args.method, results=args.results, conclusion=args.conclusion,
            lang=args.lang, max_words=args.max_words
        )

    # Override keywords if manually provided
    if args.keywords:
        result["keywords_suggested"] = [k.strip() for k in args.keywords.split(",")]

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Abstract ({result['word_count']}/{result['max_words']} words):")
        print(f"Within limit: {'✓' if result['within_limit'] else '✗'}")
        print()
        print(result["abstract"])
        print()
        print(f"Keywords: {', '.join(result['keywords_suggested'])}")
        print()
        print("Structure breakdown:")
        for section, wc in result["structure"].items():
            print(f"  {section}: {wc} words")


if __name__ == "__main__":
    cli()
