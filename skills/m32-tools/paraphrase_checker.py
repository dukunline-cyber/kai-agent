#!/usr/bin/env python3
"""
paraphrase_checker.py — Cek similarity antara teks asli dan paraphrase.

Mendeteksi:
- Kalimat yang masih terlalu mirip (>3 kata berurutan sama)
- Similarity score per kalimat
- Overall similarity percentage
- Saran perbaikan

Usage CLI:
  python3 paraphrase_checker.py --original "text asli" --paraphrase "text paraphrase"
  python3 paraphrase_checker.py --original-file original.txt --paraphrase-file paraphrase.txt

Usage import:
  from paraphrase_checker import check_paraphrase
  result = check_paraphrase(original, paraphrase)
"""

import argparse
import json
import re
from difflib import SequenceMatcher


def _split_sentences(text: str) -> list:
    """Split text menjadi kalimat."""
    # Simple sentence splitter
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _find_matching_ngrams(orig_words: list, para_words: list, n: int = 3) -> list:
    """Cari n-gram yang sama antara original dan paraphrase."""
    orig_ngrams = set()
    for i in range(len(orig_words) - n + 1):
        orig_ngrams.add(tuple(w.lower() for w in orig_words[i:i+n]))

    matches = []
    for i in range(len(para_words) - n + 1):
        ngram = tuple(w.lower() for w in para_words[i:i+n])
        if ngram in orig_ngrams:
            matches.append({
                "position": i,
                "words": " ".join(para_words[i:i+n]),
                "context": " ".join(para_words[max(0,i-2):i+n+2])
            })
    return matches


def check_paraphrase(original: str, paraphrase: str, threshold: float = 0.6) -> dict:
    """Cek kualitas paraphrase.
    
    Args:
        original: teks asli
        paraphrase: teks paraphrase
        threshold: batas similarity untuk flag (0-1)
    
    Returns:
        {
            "overall_similarity": float,
            "verdict": str,  # "good", "moderate", "poor"
            "sentence_matches": list,
            "ngram_matches": list,
            "word_count_orig": int,
            "word_count_para": int,
            "suggestions": list
        }
    """
    orig_sentences = _split_sentences(original)
    para_sentences = _split_sentences(paraphrase)

    orig_words = original.split()
    para_words = paraphrase.split()

    # Overall similarity
    overall_sim = SequenceMatcher(None, original.lower(), paraphrase.lower()).ratio()

    # Per-sentence comparison
    sentence_matches = []
    for i, p_sent in enumerate(para_sentences):
        best_match = {"orig_idx": -1, "similarity": 0, "para_sentence": p_sent}
        for j, o_sent in enumerate(orig_sentences):
            sim = SequenceMatcher(None, o_sent.lower(), p_sent.lower()).ratio()
            if sim > best_match["similarity"]:
                best_match = {"orig_idx": j, "similarity": round(sim, 3),
                              "para_sentence": p_sent, "orig_sentence": o_sent}
        if best_match["similarity"] >= threshold:
            best_match["flag"] = "TOO SIMILAR"
            sentence_matches.append(best_match)
        elif best_match["similarity"] >= 0.4:
            best_match["flag"] = "MODERATE"
            sentence_matches.append(best_match)

    # N-gram matches (3 consecutive words)
    ngram_matches = _find_matching_ngrams(orig_words, para_words, n=3)

    # Verdict
    if overall_sim < 0.3:
        verdict = "GOOD — paraphrase cukup orisinal"
    elif overall_sim < 0.5:
        verdict = "MODERATE — beberapa bagian masih mirip"
    else:
        verdict = "POOR — terlalu mirip dengan sumber, paraphrase ulang"

    # Suggestions
    suggestions = []
    if overall_sim >= 0.5:
        suggestions.append("Overall similarity terlalu tinggi. Ubah struktur kalimat lebih radikal.")
    if ngram_matches:
        suggestions.append(f"Ditemukan {len(ngram_matches)} frasa 3-kata yang sama. Ubah diksi atau urutan kata.")
        for m in ngram_matches[:5]:
            suggestions.append(f'  → "{m["words"]}" — ubah kata atau struktur')
    if len(para_words) < len(orig_words) * 0.7:
        suggestions.append("Paraphrase terlalu pendek dibanding asli. Mungkin ada konten yang hilang.")
    if len(para_words) > len(orig_words) * 1.5:
        suggestions.append("Paraphrase terlalu panjang. Mungkin ada penambahan tidak perlu.")
    if not suggestions:
        suggestions.append("Paraphrase terlihat baik. Tetap cite sumber asli.")

    return {
        "overall_similarity": round(overall_sim, 3),
        "verdict": verdict,
        "sentence_matches": sentence_matches,
        "ngram_matches_count": len(ngram_matches),
        "ngram_matches": ngram_matches[:10],
        "word_count_orig": len(orig_words),
        "word_count_para": len(para_words),
        "suggestions": suggestions
    }


def cli():
    parser = argparse.ArgumentParser(description="Paraphrase Similarity Checker")
    parser.add_argument("--original", help="Original text")
    parser.add_argument("--paraphrase", help="Paraphrased text")
    parser.add_argument("--original-file", help="File containing original text")
    parser.add_argument("--paraphrase-file", help="File containing paraphrased text")
    parser.add_argument("--threshold", type=float, default=0.6, help="Similarity threshold (0-1)")
    parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    original = args.original or ""
    paraphrase = args.paraphrase or ""

    if args.original_file:
        with open(args.original_file, 'r', encoding='utf-8') as f:
            original = f.read()
    if args.paraphrase_file:
        with open(args.paraphrase_file, 'r', encoding='utf-8') as f:
            paraphrase = f.read()

    if not original or not paraphrase:
        parser.error("Must provide --original and --paraphrase (or file variants)")

    result = check_paraphrase(original, paraphrase, args.threshold)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Overall Similarity: {result['overall_similarity']:.1%}")
        print(f"Verdict: {result['verdict']}")
        print(f"Words: {result['word_count_orig']} → {result['word_count_para']}")
        print(f"3-gram matches: {result['ngram_matches_count']}")
        print()
        if result["sentence_matches"]:
            print("Flagged sentences:")
            for m in result["sentence_matches"]:
                print(f"  [{m['flag']}] sim={m['similarity']:.1%}")
                print(f"    Para: {m['para_sentence'][:80]}...")
                print(f"    Orig: {m.get('orig_sentence', '')[:80]}...")
                print()
        print("Suggestions:")
        for s in result["suggestions"]:
            print(f"  • {s}")


if __name__ == "__main__":
    cli()
