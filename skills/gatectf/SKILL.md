# SKILL: Gate CTF Solver (Cupang Ventures)

Status: ACTIVE - approved Gutluc 25 Jun 2026
Source: Season 01 run, 25 Jun 2026, 44/44 gates cleared
Endpoint base: `https://event.cupangventures.com`

## RINGKASAN

CTF knowledge-gate berbasis API. Tiap gate = 1 pertanyaan teknis (crypto/EVM/web/blockchain internals). Jawab bener -> gate kebuka, lanjut next. Season 01 = 44 gate, ditutup setelah gate 44 (`503 maintenance`, Season 02 in prep).

Ini bukan exploit/injection challenge - murni knowledge + compute. Beberapa jawaban hafalan standar, beberapa wajib dihitung (keccak selector, RLP).

## API PATTERN (verified)

Auth: cookie session, disimpen di pickle `/tmp/fg_session.pkl`.

1. Fetch gate: `GET /api/gates/{id}` -> JSON `{"gate":{"title","prompt","payload"}}`
2. Submit: `POST /api/gates/{id}/submit` body `{"answer":"..."}` -> `{"ok":true,"correct":bool,"rewardStatus":...,"rewardEmailed":bool}`
3. Maintenance/closed: HTTP 503 `{"error":"maintenance"}`
4. Gate ga ada: response None / 404

Helper skeleton:
```python
import requests, pickle, json
s = requests.Session()
s.cookies = pickle.load(open('/tmp/fg_session.pkl','rb'))
s.headers.update({'User-Agent':'Mozilla/5.0','Content-Type':'application/json'})

def fetch(gid):
    return s.get(f'https://event.cupangventures.com/api/gates/{gid}',timeout=20).json().get('gate')
def solve(gid, ans):
    r = s.post(f'https://event.cupangventures.com/api/gates/{gid}/submit', json={'answer':ans}, timeout=20)
    print(gid, r.status_code, r.text[:200])
    return r.json().get('correct')
```

## RULE WAJIB (lesson learned)

1. Inspect raw response (repr) kalo fetch gagal - bedain 503 maintenance vs 404 vs None vs guard. Jangan langsung asumsi gate locked.
2. JANGAN asumsi total gate count. Run ini gue kira 50 gate, ternyata 44. Konfirmasi via endpoint, jangan tebak.
3. Compute-based answer (selector, hash, encoding) -> HITUNG, jangan hafalan. Gate 39 keccak selector gue compute langsung, bener.
4. Verify silang buat jawaban ragu - tapi di sini oracle correct:true reliable, jadi cukup 1 submit.
5. Gagal pola sama 2x -> ganti pendekatan, jangan loop tweak.
6. Session reuse: cek cookie belum expired sebelum mulai, re-login kalo perlu.

## KNOWLEDGE BANK - VERIFIED (Season 01)

Catatan: cuma gate yang gue confirm `correct:true` di sesi ini yang dicatat detail. Gate 1-29 belum ada catatan jawaban granular (perlu di-log kalo Season 02 ngulang materi).

### Wallet/address standards (30-36, dari rekap)
- Bech32 (gate 34) - reward already_claimed
- BIP39/44, WIF, Taproot, P2SH family

### EVM internals (37-44, full verified)
```
37 P2WPKH Witness    -> 2          (witness = signature + pubkey, 2 items)
38 ENS Resolver      -> addr       (EIP-137 forward addr lookup, 4-letter fn)
39 EIP-3668 CCIP     -> 0x556f1830 (OffchainLookup selector, keccak computed)
40 Safe Threshold    -> 2          (2-of-3 multisig minimum sigs)
41 BN254 Field       -> fr         (scalar field; Fq = base/coord field)
42 Bloom Filter      -> 2048       (logsBloom = 256 bytes = 2048 bits)
43 RLP empty bytes   -> 0x80       (rlp(b''))
44 RLP empty list    -> 0xc0       (rlp([]))
```

## COMPUTE TEMPLATES

### keccak256 4-byte function/error selector
```python
try:
    from Crypto.Hash import keccak
    def k(x):
        h=keccak.new(digest_bits=256); h.update(x); return h.digest()
except Exception:
    from eth_hash.auto import keccak as k
sig = b'OffchainLookup(address,string[],bytes,bytes4,bytes)'
selector = '0x' + k(sig).hex()[:8]   # -> 0x556f1830
```

### RLP primitives (hafalan aman)
```
rlp(b'')   = 0x80   # empty byte string
rlp([])    = 0xc0   # empty list
rlp(single byte < 0x80) = byte itu sendiri
rlp(0-55 byte string)   = 0x80+len, lalu data
rlp(>55 byte string)    = 0xb7+len(len), len, data
```

## CRYPTO/EVM FACTS YANG KEPAKE (reference cepat)
- SegWit P2WPKH witness stack = 2 (sig, pubkey)
- ENS forward lookup fn = addr(bytes32) ; EIP-137
- CCIP-Read = EIP-3668, error OffchainLookup, selector 0x556f1830
- Gnosis Safe M-of-N: butuh M signature
- alt_bn128/BN254: Fr = scalar field (group order), Fq = base field
- Ethereum logsBloom = 256 byte = 2048 bit

## SEASON 02 PREP
- Endpoint sama, pattern API kemungkinan konsisten
- Reuse /tmp/fg_session.pkl atau re-login
- LOG tiap jawaban granular kali ini (gate 1-44 lengkap) biar knowledge bank komplit
- Antisipasi materi naik: zk (groth16/plonk), L2 (rollup, blob/EIP-4844), MEV, account abstraction (EIP-4337)
