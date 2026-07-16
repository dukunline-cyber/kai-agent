#!/usr/bin/env python3
"""
structure_checker.py — Validator kelengkapan struktur dokumen akademik.

Cek:
- Kelengkapan bab (skripsi/tesis/jurnal)
- Word count per section
- Rasio antar section (intro/method/results/discussion)
- Missing elements (abstract, keywords, references, dll)
- Saran perbaikan

Usage CLI:
  python3 structure_checker.py --file draft.txt --type skripsi
  python3 structure_checker.py --file draft.txt --type jurnal --style apa

Usage import:
  from structure_checker import check_structure
  result = check_structure(text, doc_type="skripsi")
"""

import argparse
import json
import re


# Expected sections per document type
EXPECTED_SECTIONS = {
    "skripsi": {
        "required": [
            ("abstrak", "Abstrak (ID)"),
            ("abstract", "Abstract (EN)"),
            ("bab i", "BAB I - Pendahuluan"),
            ("latar belakang", "Latar Belakang"),
            ("rumusan masalah", "Rumusan Masalah"),
            ("tujuan", "Tujuan Penelitian"),
            ("bab ii", "BAB II - Tinjauan Pustaka"),
            ("landasan teori", "Landasan Teori"),
            ("penelitian terdahulu", "Penelitian Terdahulu"),
            ("bab iii", "BAB III - Metodologi"),
            ("jenis penelitian", "Jenis Penelitian"),
            ("populasi", "Populasi & Sampel"),
            ("teknik pengumpulan", "Teknik Pengumpulan Data"),
            ("teknik analisis", "Teknik Analisis Data"),
            ("bab iv", "BAB IV - Hasil & Pembahasan"),
            ("hasil", "Hasil Penelitian"),
            ("pembahasan", "Pembahasan"),
            ("bab v", "BAB V - Penutup"),
            ("kesimpulan", "Kesimpulan"),
            ("saran", "Saran"),
            ("daftar pustaka", "Daftar Pustaka"),
        ],
        "optional": [
            ("kata pengantar", "Kata Pengantar"),
            ("daftar isi", "Daftar Isi"),
            ("daftar tabel", "Daftar Tabel"),
            ("daftar gambar", "Daftar Gambar"),
            ("hipotesis", "Hipotesis"),
            ("keterbatasan", "Keterbatasan Penelitian"),
            ("lampiran", "Lampiran"),
        ]
    },
    "tesis": {
        "required": [
            ("abstrak", "Abstrak (ID)"),
            ("abstract", "Abstract (EN)"),
            ("bab i", "BAB I - Pendahuluan"),
            ("latar belakang", "Latar Belakang"),
            ("rumusan masalah", "Rumusan Masalah"),
            ("tujuan", "Tujuan Penelitian"),
            ("bab ii", "BAB II - Tinjauan Pustaka"),
            ("kerangka teori", "Kerangka Teori"),
            ("bab iii", "BAB III - Metodologi"),
            ("jenis penelitian", "Jenis Penelitian"),
            ("populasi", "Populasi & Sampel"),
            ("teknik analisis", "Teknik Analisis Data"),
            ("bab iv", "BAB IV - Hasil & Pembahasan"),
            ("hasil", "Hasil"),
            ("pembahasan", "Pembahasan"),
            ("bab v", "BAB V - Penutup"),
            ("kesimpulan", "Kesimpulan"),
            ("saran", "Saran"),
            ("daftar pustaka", "Daftar Pustaka"),
        ],
        "optional": [
            ("novelty", "Novelty Statement"),
            ("kontribusi", "Kontribusi Orisinalitas"),
            ("keterbatasan", "Keterbatasan"),
            ("lampiran", "Lampiran"),
        ]
    },
    "jurnal": {
        "required": [
            ("abstract", "Abstract"),
            ("keyword", "Keywords"),
            ("introduction", "Introduction"),
            ("method", "Methods"),
            ("result", "Results"),
            ("discussion", "Discussion"),
            ("conclusion", "Conclusion"),
            ("reference", "References"),
        ],
        "optional": [
            ("acknowledgment", "Acknowledgments"),
            ("appendix", "Appendix"),
            ("author contribution", "Author Contributions"),
            ("conflict", "Conflict of Interest"),
            ("funding", "Funding"),
        ]
    }
}

# Recommended word count ratios for journal articles
JOURNAL_RATIO = {
    "introduction": (0.15, 0.25),  # 15-25% of total
    "method": (0.15, 0.25),
    "result": (0.20, 0.35),
    "discussion": (0.20, 0.35),
    "conclusion": (0.03, 0.08),
}


def _find_section(text_lower: str, keyword: str) -> tuple:
    """Cari section berdasarkan keyword. Return (found, position, word_count)."""
    # Try various patterns
    patterns = [
        rf'\b{re.escape(keyword)}\b',
        rf'^{re.escape(keyword)}',
        rf'\n{re.escape(keyword)}',
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.MULTILINE | re.IGNORECASE)
        if match:
            pos = match.start()
            # Count words until next section or end
            rest = text_lower[pos:]
            # Find next section heading (rough heuristic)
            next_section = re.search(r'\n(bab |chapter |abstract|introduction|method|result|discussion|conclusion|reference|daftar pustaka|kata pengantar)', rest[10:])
            if next_section:
                section_text = rest[:next_section.start() + 10]
            else:
                section_text = rest
            word_count = len(section_text.split())
            return True, pos, word_count
    return False, -1, 0


def check_structure(text: str, doc_type: str = "skripsi") -> dict:
    """Cek kelengkapan struktur dokumen.
    
    Args:
        text: isi dokumen
        doc_type: skripsi, tesis, jurnal
    
    Returns:
        {
            "doc_type": str,
            "total_words": int,
            "est_pages": float,
            "found_required": list,
            "missing_required": list,
            "found_optional": list,
            "section_word_counts": dict,
            "ratio_analysis": dict,
            "suggestions": list,
            "completeness_score": float,
        }
    """
    text_lower = text.lower()
    total_words = len(text.split())
    est_pages = total_words / 250  # approx 250 words per page (1.5 spacing, TNR 12)

    expected = EXPECTED_SECTIONS.get(doc_type, EXPECTED_SECTIONS["skripsi"])

    found_required = []
    missing_required = []
    section_word_counts = {}

    for keyword, label in expected["required"]:
        found, pos, wc = _find_section(text_lower, keyword)
        if found:
            found_required.append(label)
            section_word_counts[label] = wc
        else:
            missing_required.append(label)

    found_optional = []
    for keyword, label in expected["optional"]:
        found, pos, wc = _find_section(text_lower, keyword)
        if found:
            found_optional.append(label)
            section_word_counts[label] = wc

    # Ratio analysis (for jurnal)
    ratio_analysis = {}
    if doc_type == "jurnal":
        for section, (min_r, max_r) in JOURNAL_RATIO.items():
            found, pos, wc = _find_section(text_lower, section)
            if found and total_words > 0:
                actual_ratio = wc / total_words
                status = "OK"
                if actual_ratio < min_r:
                    status = f"TOO SHORT (target: {min_r:.0%}-{max_r:.0%})"
                elif actual_ratio > max_r:
                    status = f"TOO LONG (target: {min_r:.0%}-{max_r:.0%})"
                ratio_analysis[section] = {
                    "words": wc,
                    "ratio": round(actual_ratio, 3),
                    "status": status
                }

    # Suggestions
    suggestions = []
    if missing_required:
        suggestions.append(f"Missing {len(missing_required)} required sections:")
        for m in missing_required:
            suggestions.append(f"  ✗ {m}")
    if total_words < 1000:
        suggestions.append(f"Dokumen terlalu pendek ({total_words} kata, ~{est_pages:.0f} halaman).")
    if doc_type == "skripsi" and total_words < 8000:
        suggestions.append("Skripsi biasanya 8000-15000 kata (30-60 halaman).")
    if doc_type == "tesis" and total_words < 15000:
        suggestions.append("Tesis biasanya 15000-30000 kata (60-120 halaman).")
    if doc_type == "jurnal" and total_words > 8000:
        suggestions.append("Jurnal biasanya 4000-8000 kata. Pertimbangkan untuk mempersingkat.")
    if not missing_required:
        suggestions.append("✓ Semua required sections ditemukan!")

    # Completeness score
    total_required = len(expected["required"])
    found_count = len(found_required)
    completeness = round(found_count / total_required, 2) if total_required else 0

    return {
        "doc_type": doc_type,
        "total_words": total_words,
        "est_pages": round(est_pages, 1),
        "found_required": found_required,
        "missing_required": missing_required,
        "found_optional": found_optional,
        "section_word_counts": section_word_counts,
        "ratio_analysis": ratio_analysis,
        "suggestions": suggestions,
        "completeness_score": completeness,
    }


def cli():
    parser = argparse.ArgumentParser(description="Academic Document Structure Checker")
    parser.add_argument("--file", required=True, help="Text file to check")
    parser.add_argument("--type", default="skripsi", choices=["skripsi", "tesis", "jurnal"])
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    with open(args.file, 'r', encoding='utf-8') as f:
        text = f.read()

    result = check_structure(text, args.type)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Document Type: {result['doc_type']}")
        print(f"Total Words: {result['total_words']}")
        print(f"Est. Pages: {result['est_pages']}")
        print(f"Completeness: {result['completeness_score']:.0%}")
        print()
        print("Found Required Sections:")
        for s in result["found_required"]:
            wc = result["section_word_counts"].get(s, 0)
            print(f"  ✓ {s} ({wc} words)")
        print()
        if result["missing_required"]:
            print("Missing Required Sections:")
            for s in result["missing_required"]:
                print(f"  ✗ {s}")
            print()
        if result["found_optional"]:
            print("Found Optional Sections:")
            for s in result["found_optional"]:
                print(f"  + {s}")
            print()
        if result["ratio_analysis"]:
            print("Ratio Analysis (Journal):")
            for section, info in result["ratio_analysis"].items():
                print(f"  {section}: {info['words']} words ({info['ratio']:.1%}) — {info['status']}")
            print()
        print("Suggestions:")
        for s in result["suggestions"]:
            print(f"  • {s}")


if __name__ == "__main__":
    cli()
