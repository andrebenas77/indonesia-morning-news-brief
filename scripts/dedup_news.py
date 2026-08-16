#!/usr/bin/env python3
"""Cluster and classify the morning's headlines: Sectors + raw outlets -> one story list.

Feeds the ranking rubric two signals it could not otherwise compute:

  * cross_outlet_count — how many distinct outlets carried the same story. On the
    Sectors-only path this was always 1, so the rubric's "+3 per additional outlet"
    row had no input at all.
  * repeat_days        — whether this story already ran earlier in the week.

Deliberately mechanical. The model is asked only to group indices and pick a category;
the response schema contains no scores, no ranking and no prose, so this script is
structurally incapable of doing the editorial work that belongs to Claude. If you ever
find yourself adding a `score` or `title` field to the response schema, stop.

Order of work is cheapest-first: exact URL match, then lexical clustering, and only the
surviving representatives go to the model. Lexical clustering doubles as the complete
fallback — if DeepSeek is down, out of balance or slow, the brief still builds.

Usage:
    py scripts/dedup_news.py --date 2026-08-16
    py scripts/dedup_news.py --no-llm                  # lexical only, no API calls
    py scripts/dedup_news.py --commit-store --date ... # after a verified publish
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DATA = ROOT / "data"
STORE = DATA / "headline-store.json"
WIB = timezone(timedelta(hours=7))

# deepseek-chat / deepseek-reasoner were RETIRED 2026-07-24 and now 400. The current
# ids are deepseek-v4-pro and deepseek-v4-flash.
#
# v4-flash is pinned deliberately. v4-pro emits a reasoning block before its text and
# costs more for a job that is pure clustering — a measured call to v4-pro returned an
# empty content[0].text for exactly that reason. Nothing here benefits from a stronger
# model; if clustering quality ever looks wrong, fix the prompt, not the tier.
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"

CATEGORIES = {"corporate", "macro", "bank_indonesia", "market",
              "regulator", "commodity", "global", "noise"}

SYSTEM = (
    "You are a deduplication and classification engine for Indonesian financial news "
    "headlines. You do not summarise, rank, translate, or judge importance. You only "
    "group headlines that report the SAME underlying event, and assign each group one "
    "category. Two headlines about the same company but different events are NOT the "
    "same story. Output JSON only.\n\n"
    'Respond as: {"clusters":[{"members":[0,4],"primary":0,'
    '"category":"corporate","tickers":["BBRI"]}]}\n\n'
    "Every input index must appear in exactly one cluster. `primary` must be one of "
    "`members` — prefer the most specific, most complete headline. `category` is one "
    "of: corporate, macro, bank_indonesia, market, regulator, commodity, global, "
    "noise. Use `noise` for lifestyle, sport, entertainment, crime, human interest, "
    "advertorial, general explainers and generic 'saham rekomendasi hari ini' "
    "clickbait — anything an institutional equity investor would not read. Natural "
    "disasters and accidents are `noise` UNLESS the headline itself names a listed "
    "company, a commodity, or a market impact. `tickers` are 4-letter IDX codes "
    "only, [] if none. Never output headline text."
)

# Sectors returns `source` as a bare URL, so without this map every Sectors item looks
# like a different outlet from the same item scraped directly and cross_outlet_count
# becomes meaningless. Hosts observed live in a single morning's feed.
HOST_OUTLET = {
    "kontan.co.id": "Kontan", "investasi.kontan.co.id": "Kontan",
    "keuangan.kontan.co.id": "Kontan", "insight.kontan.co.id": "Kontan",
    "industri.kontan.co.id": "Kontan", "nasional.kontan.co.id": "Kontan",
    "cnbcindonesia.com": "CNBC Indonesia", "www.cnbcindonesia.com": "CNBC Indonesia",
    "emitennews.com": "Emitennews", "www.emitennews.com": "Emitennews",
    "bloombergtechnoz.com": "Bloomberg Technoz",
    "www.bloombergtechnoz.com": "Bloomberg Technoz",
    "bisnis.com": "Bisnis", "market.bisnis.com": "Bisnis", "www.bisnis.com": "Bisnis",
    "kompas.com": "Kompas", "money.kompas.com": "Kompas",
    "investor.id": "Investor Daily", "www.investor.id": "Investor Daily",
    "idx.co.id": "IDX", "www.idx.co.id": "IDX",
    "cnnindonesia.com": "CNN Indonesia", "www.cnnindonesia.com": "CNN Indonesia",
    "idnfinancials.com": "IDN Financials", "www.idnfinancials.com": "IDN Financials",
    "katadata.co.id": "Katadata", "tempo.co": "Tempo", "antaranews.com": "Antara",
}

STOPWORDS = {
    "di", "ke", "dari", "yang", "dan", "ini", "itu", "untuk", "pada", "dengan", "atau",
    "akan", "ada", "dalam", "para", "oleh", "juga", "saja", "bisa", "tak", "tidak",
    "sudah", "masih", "lebih", "usai", "jadi", "buat", "saat", "kini", "hari", "soal",
    "saham", "persen", "rupiah", "harga", "bursa", "pasar", "emiten", "perusahaan",
    "cek", "simak", "ini2", "begini", "kabar", "berita", "terbaru", "hingga", "capai",
}


# --- normalisation ---------------------------------------------------------

def canon_url(u: str) -> str:
    u = re.sub(r"^https?://", "", (u or "").strip())
    return u.split("?")[0].split("#")[0].rstrip("/").lower()


def outlet_from_url(u: str) -> str:
    host = canon_url(u).split("/")[0]
    if host in HOST_OUTLET:
        return HOST_OUTLET[host]
    bare = host[4:] if host.startswith("www.") else host
    if bare in HOST_OUTLET:
        return HOST_OUTLET[bare]
    # Fall back to the registrable-ish name so unknown outlets still count as distinct.
    parts = [p for p in bare.split(".") if p not in ("co", "id", "com", "net", "org")]
    return parts[-1].title() if parts else (host or "unknown")


def fingerprint(title: str) -> frozenset:
    """Bag of meaningful tokens, for Jaccard comparison."""
    t = unicodedata.normalize("NFKD", title or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    tickers = set(re.findall(r"\b[A-Z]{4}\b", t))
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    toks = {w for w in t.split() if len(w) >= 4 and w not in STOPWORDS}
    return frozenset(toks | {x.lower() for x in tickers})


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def normalize(date: str) -> tuple[list[dict], list[str]]:
    """Merge Sectors + outlet items into one list, collapsing exact-URL duplicates."""
    warnings: list[str] = []
    by_canon: dict[str, dict] = {}
    order: list[str] = []

    sec = load_json(BUILD / f"sectors-news-{date}.json")
    if not sec.get("news"):
        warnings.append("sectors-news missing or empty")
    for n in sec.get("news") or []:
        url = n.get("url") or ""
        cu = canon_url(url)
        if not cu or not (n.get("title") or "").strip():
            continue
        if cu in by_canon:
            continue
        by_canon[cu] = {
            "origin": "sectors", "outlet": outlet_from_url(url),
            "title": (n.get("title") or "").strip(), "url": url, "canon_url": cu,
            "summary": (n.get("summary") or "")[:400],
            "timestamp": n.get("timestamp"),
            "symbols": n.get("symbols") or [], "tags": n.get("tags") or [],
            "rail_rank": None, "dim_score": n.get("dim_score") or 0,
        }
        order.append(cu)

    out = load_json(BUILD / f"outlets-{date}.json")
    if not out.get("items"):
        warnings.append("outlets file missing or empty — cross-outlet signal degraded")
    for o in out.get("items") or []:
        cu = o.get("canon_url") or canon_url(o.get("url") or "")
        if not cu:
            continue
        if cu in by_canon:
            # Same article Sectors already carried. Keep Sectors' English summary and
            # symbols, but take the rail position, which only the scrape can supply.
            prev = by_canon[cu]
            if o.get("rail_rank") is not None and prev.get("rail_rank") is None:
                prev["rail_rank"] = o["rail_rank"]
            if not prev.get("timestamp") and o.get("timestamp"):
                prev["timestamp"] = o["timestamp"]
            continue
        by_canon[cu] = {
            "origin": "outlet", "outlet": o.get("outlet") or outlet_from_url(o.get("url", "")),
            "title": (o.get("title") or "").strip(), "url": o.get("url") or "",
            "canon_url": cu, "summary": o.get("summary") or "",
            "timestamp": o.get("timestamp"),
            "symbols": o.get("symbols") or [], "tags": [],
            "rail_rank": o.get("rail_rank"), "dim_score": 0,
        }
        order.append(cu)

    return [by_canon[c] for c in order], warnings


# --- lexical clustering (also the DeepSeek-down fallback) ------------------

def cluster_lexical(items: list[dict], threshold: float = 0.60) -> list[list[int]]:
    fps = [fingerprint(i["title"]) for i in items]
    parent = list(range(len(items)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # Inverted index on tokens so this stays near-linear instead of O(n^2).
    buckets: dict[str, list[int]] = {}
    for i, fp in enumerate(fps):
        for tok in fp:
            buckets.setdefault(tok, []).append(i)
    for idxs in buckets.values():
        if len(idxs) > 60:       # ultra-common token, not discriminating
            continue
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                x, y = idxs[a], idxs[b]
                if find(x) != find(y) and jaccard(fps[x], fps[y]) >= threshold:
                    union(x, y)

    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    return [sorted(v) for v in groups.values()]


# --- DeepSeek --------------------------------------------------------------

class DeepSeekError(Exception):
    def __init__(self, msg: str, fatal: bool = False):
        super().__init__(msg)
        self.fatal = fatal          # fatal => do not retry (401/402)


def _post_json(payload: dict, key: str, timeout: int = 90) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        # 401 = bad key, 402 = insufficient balance. Retrying either just burns the
        # wall-clock budget and delays the fallback.
        raise DeepSeekError(f"HTTP {e.code}: {detail}", fatal=e.code in (401, 402))
    except Exception as e:
        raise DeepSeekError(f"{type(e).__name__}: {e}")


def _extract_text(resp: dict) -> str:
    """Content can arrive as a plain string or an Anthropic-style block list. Never
    index content[0] blindly — v4-pro puts a reasoning block there and its text is
    empty.

    reasoning_content is only used when it actually contains a JSON object. Returning
    raw reasoning prose as if it were the answer just feeds unparseable narration to
    the salvage path and hides the real failure.
    """
    msg = ((resp.get("choices") or [{}])[0] or {}).get("message") or {}
    c = msg.get("content")
    if isinstance(c, str) and c.strip():
        return c
    if isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text" and (b.get("text") or "").strip():
                return b["text"]
    rc = msg.get("reasoning_content") or ""
    return rc if "{" in rc and "clusters" in rc else ""


def _salvage_json(text: str) -> dict | None:
    """Recover a truncated response by trimming to the last complete cluster object."""
    ends = [m.start() for m in re.finditer(r"\}", text)]
    for i in reversed(ends[-400:]):
        try:
            return json.loads(text[:i + 1] + "]}")
        except Exception:
            continue
    return None


def _reconcile(clusters: list[dict], n: int) -> list[dict]:
    """Force a valid partition of 0..n-1. Never trust the model's bookkeeping.

    Missing indices (the tail of a salvaged response) become singletons; duplicated
    indices stay with the first cluster that claimed them.
    """
    seen: set[int] = set()
    out: list[dict] = []
    for c in clusters or []:
        members = []
        for m in c.get("members") or []:
            if isinstance(m, bool) or not isinstance(m, int):
                continue
            if 0 <= m < n and m not in seen:
                seen.add(m)
                members.append(m)
        if not members:
            continue
        primary = c.get("primary")
        if not isinstance(primary, int) or primary not in members:
            primary = min(members)
        cat = c.get("category")
        tickers = [t for t in (c.get("tickers") or [])
                   if isinstance(t, str) and re.fullmatch(r"[A-Z]{4}", t)]
        out.append({"members": sorted(members), "primary": primary,
                    "category": cat if cat in CATEGORIES else "market",
                    "tickers": sorted(set(tickers))})
    for i in range(n):
        if i not in seen:
            out.append({"members": [i], "primary": i, "category": "market",
                        "tickers": []})
    return out


def _call(lines: list[str], key: str, max_tokens: int, depth: int,
          stats: dict, warnings: list[str]) -> list[dict]:
    """One model call over `lines`; returns clusters indexed 0..len(lines)-1."""
    payload = {
        "model": MODEL, "temperature": 0, "max_tokens": max_tokens,
        # v4-flash is a reasoning model and max_tokens caps reasoning + content
        # together. Left on, a 12-headline batch burned 3.9k reasoning tokens and
        # never emitted its JSON at all — every batch truncated. Clustering needs no
        # chain of thought: reasoning_effort=none took the same batch from 4000
        # completion tokens to 226, and made the call deterministic as a side effect.
        # ("enable_thinking": false is silently ignored by this API — it does not work.)
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "\n".join(lines)}],
    }
    last: DeepSeekError | None = None
    for attempt in range(3):
        try:
            resp = _post_json(payload, key)
            break
        except DeepSeekError as e:
            last = e
            if e.fatal:
                raise
            if attempt < 2:
                time.sleep(2 + 3 * attempt)
    else:
        raise last or DeepSeekError("unknown")

    stats["calls"] += 1
    u = resp.get("usage") or {}
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        stats["usage"][k] = stats["usage"].get(k, 0) + int(u.get(k) or 0)

    finish = ((resp.get("choices") or [{}])[0] or {}).get("finish_reason")
    text = _extract_text(resp)
    parsed = None
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = _salvage_json(text)
        if parsed is not None:
            warnings.append(f"salvaged a truncated response ({len(lines)} items)")

    if parsed is None and finish == "length" and depth < 2 and len(lines) > 4:
        mid = len(lines) // 2
        warnings.append(f"truncated at {len(lines)} items — splitting")
        left = _call(lines[:mid], key, max_tokens, depth + 1, stats, warnings)
        right = _call(lines[mid:], key, max_tokens, depth + 1, stats, warnings)
        for c in right:
            c["members"] = [m + mid for m in c["members"]]
            c["primary"] = c["primary"] + mid
        return left + right

    if parsed is None:
        raise DeepSeekError("unparseable response")
    return _reconcile(parsed.get("clusters") or [], len(lines))


def deepseek_merge(reps: list[dict], key: str, batch: int, max_tokens: int,
                   budget_s: float, stats: dict, warnings: list[str]) -> list[list[int]]:
    """Group representative indices. Returns groups of positions within `reps`."""
    groups: list[list[int]] = []
    started = time.time()
    for off in range(0, len(reps), batch):
        if time.time() - started > budget_s:
            warnings.append(
                f"wall-clock budget {budget_s:.0f}s exceeded — "
                f"{len(reps) - off} representatives kept at lexical clustering")
            stats["partial"] = True
            for j in range(off, len(reps)):
                groups.append([j])
            break
        chunk = reps[off:off + batch]
        lines = [f"[{i}] {r['outlet']} | {r['title']}" for i, r in enumerate(chunk)]
        for c in _call(lines, key, max_tokens, 0, stats, warnings):
            groups.append([m + off for m in c["members"]])
            stats["cat"][off + c["primary"]] = c["category"]
            stats["tick"][off + c["primary"]] = c["tickers"]
    return groups


# --- rolling store ---------------------------------------------------------

def load_store(date: str | None = None, retain_days: int = 7) -> dict:
    """Load the rolling store, applying the retain window at READ time.

    Pruning only on commit is not enough: after a long weekend or a run that never
    published, the file still holds entries older than the window, and every one of
    them would be reported as a repeat. The cutoff has to be enforced wherever the
    store is read, not just wherever it is written.
    """
    s = load_json(STORE)
    if not isinstance(s.get("entries"), dict):
        return {"version": 1, "entries": {}}
    if date:
        cutoff = cutoff_date(date, retain_days)
        s["entries"] = {k: v for k, v in s["entries"].items()
                        if v.get("last_seen", "") >= cutoff}
    return s


def cutoff_date(date: str, retain_days: int) -> str:
    return (datetime.strptime(date, "%Y-%m-%d")
            - timedelta(days=retain_days)).strftime("%Y-%m-%d")


def fp_key(title: str) -> str:
    return "|".join(sorted(fingerprint(title)))[:200]


def commit_store(date: str, retain_days: int) -> int:
    """Merge the pending delta. Called only after the publish is verified — writing it
    at cluster time would suppress tomorrow a story that today never actually shipped
    (which is exactly what happened for twelve days in August 2026)."""
    delta = load_json(BUILD / f"store-delta-{date}.json")
    if not delta.get("entries"):
        print(f"[dedup] no store delta for {date} — nothing to commit")
        return 0
    store = load_store()          # unfiltered: prune below is authoritative on write
    ents = store["entries"]
    for k, v in delta["entries"].items():
        if k in ents:
            e = ents[k]
            e["last_seen"] = v["last_seen"]
            e["seen_dates"] = sorted(set(e.get("seen_dates", []) + v["seen_dates"]))
            e["outlets"] = sorted(set(e.get("outlets", []) + v.get("outlets", [])))
        else:
            ents[k] = v
    cutoff = cutoff_date(date, retain_days)
    before = len(ents)
    store["entries"] = {k: v for k, v in ents.items() if v.get("last_seen", "") >= cutoff}
    DATA.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[dedup] store committed: {before} -> {len(store['entries'])} entries "
          f"(retain {retain_days}d)")
    return 0


# --- main ------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--no-llm", action="store_true", help="lexical only, no API calls")
    ap.add_argument("--batch-size", type=int, default=40)
    ap.add_argument("--max-tokens", type=int, default=4000)
    ap.add_argument("--budget-s", type=float, default=90.0)
    ap.add_argument("--retain-days", type=int, default=7)
    ap.add_argument("--commit-store", action="store_true",
                    help="merge the pending delta (run only after a verified publish)")
    ap.add_argument("--out")
    args = ap.parse_args()

    date = args.date or datetime.now(WIB).strftime("%Y-%m-%d")
    if args.commit_store:
        return commit_store(date, args.retain_days)

    warnings: list[str] = []
    items, warnings_n = normalize(date)
    warnings.extend(warnings_n)
    if not items:
        print("[dedup] no input items — nothing to do", file=sys.stderr)

    # 1. lexical clustering — cheap, and the complete fallback if the model is down
    lex = cluster_lexical(items) if items else []
    lex.sort(key=lambda g: g[0])
    reps = [items[g[0]] for g in lex]

    stats = {"calls": 0, "usage": {}, "cat": {}, "tick": {}, "partial": False}
    engine = "lexical-fallback"
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()

    # 2. model pass over representatives only
    groups = [[i] for i in range(len(reps))]
    if not args.no_llm and reps:
        if not key:
            warnings.append("DEEPSEEK_API_KEY not set — lexical clustering only")
        else:
            try:
                groups = deepseek_merge(reps, key, args.batch_size, args.max_tokens,
                                        args.budget_s, stats, warnings)
                engine = "deepseek-partial" if stats["partial"] else MODEL
            except DeepSeekError as e:
                warnings.append(f"DeepSeek unavailable ({e}) — lexical clustering only")
                groups = [[i] for i in range(len(reps))]
    elif args.no_llm:
        warnings.append("--no-llm: lexical clustering only")

    # 3. fold model groups back onto the lexical clusters
    store = load_store(date, args.retain_days)
    clusters, delta_entries = [], {}
    for gi, grp in enumerate(sorted(groups, key=lambda g: min(g))):
        member_idx: list[int] = []
        for rpos in grp:
            member_idx.extend(lex[rpos])
        members = [items[i] for i in sorted(set(member_idx))]
        if not members:
            continue

        primary_rep = min(grp)
        primary = items[lex[primary_rep][0]]
        # Prefer a member that actually carries a rail position or a richer summary.
        for m in members:
            if m.get("rail_rank") is not None:
                primary = m
                break

        outlets = sorted({m["outlet"] for m in members if m.get("outlet")})
        ranks = [m["rail_rank"] for m in members if m.get("rail_rank") is not None]
        best_rank = min(ranks) if ranks else None
        rail_outlet = next((m["outlet"] for m in members
                            if m.get("rail_rank") == best_rank), None) if ranks else None

        tickers = sorted({t for m in members for t in (m.get("symbols") or [])}
                         | set(stats["tick"].get(primary_rep, [])))
        category = stats["cat"].get(primary_rep, "market")

        k = fp_key(primary["title"])
        prev = store["entries"].get(k)
        seen_dates = sorted(set((prev or {}).get("seen_dates", []) + [date]))
        # Only sightings inside the retain window count. A date carried forward from
        # an old entry must not resurrect a repeat the window has already forgotten.
        window_start = cutoff_date(date, args.retain_days)
        past = [d for d in seen_dates if window_start <= d < date]
        repeat_days = len(past)
        # Bank Indonesia policy stories legitimately develop across days; penalising a
        # rate decision for being on its third morning is exactly wrong.
        if category == "bank_indonesia":
            repeat_days = 0

        clusters.append({
            "cluster_id": f"c{gi:03d}",
            "primary": primary,
            "members": members,
            "cross_outlet_count": len(outlets),
            "outlets": outlets,
            "category": category,
            "tickers": tickers,
            "best_rail_rank": best_rank,
            "rail_outlet": rail_outlet,
            "is_repeat": repeat_days >= 1,
            "repeat_days": repeat_days,
            "first_seen": (past[0] if past else date),
            "merged_from": sorted({m["url"] for m in members if m.get("url")}),
        })
        delta_entries[k] = {
            "first_seen": (prev or {}).get("first_seen", date),
            "last_seen": date, "seen_dates": seen_dates,
            "title": primary["title"][:200], "url": primary.get("url", ""),
            "outlets": outlets, "tickers": tickers,
        }

    clusters.sort(key=lambda c: (-c["cross_outlet_count"],
                                 c["best_rail_rank"] if c["best_rail_rank"] else 99))

    tick_counts = Counter(t for c in clusters for t in c["tickers"])
    out = {
        "date": date,
        "generated_at": datetime.now(WIB).strftime("%Y-%m-%d %H:%M WIB"),
        "available": bool(clusters),
        "engine": engine,
        "clusters": clusters,
        "tickers": [t for t, _ in tick_counts.most_common()],
        "counts": {
            "input": len(items),
            "lexical_clusters": len(lex),
            "clusters": len(clusters),
            "merged": len(items) - len(clusters),
            "repeats": sum(1 for c in clusters if c["is_repeat"]),
            "noise": sum(1 for c in clusters if c["category"] == "noise"),
            "cross_outlet_max": max((c["cross_outlet_count"] for c in clusters), default=0),
            "deepseek_calls": stats["calls"],
        },
        "usage": stats["usage"],
        "warnings": warnings,
        "errors": [],
    }

    BUILD.mkdir(parents=True, exist_ok=True)
    path = Path(args.out) if args.out else BUILD / f"dedup-{date}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    (BUILD / f"store-delta-{date}.json").write_text(
        json.dumps({"date": date, "entries": delta_entries}, indent=2,
                   ensure_ascii=False), encoding="utf-8")

    print(f"[dedup] wrote {path}")
    print(f"[dedup] engine={engine} {out['counts']}")
    if out["usage"]:
        print(f"[dedup] tokens={out['usage']}")
    if out["tickers"]:
        print(f"[dedup] tickers: {','.join(out['tickers'][:25])}")
    for w in warnings:
        print(f"[dedup] warn: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
