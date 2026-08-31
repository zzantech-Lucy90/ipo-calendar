"""수집 파이프라인 진입점.

    python3 -m collector.run              # 기본 수집 → data/ipos.json
    python3 -m collector.run --pages 5    # 38 목록을 더 깊게
    python3 -m collector.run --no-dart    # DART 보강 생략
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from . import dart, ipo38, kind
from .merge import merge

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ipos.json"


def main() -> None:
    ap = argparse.ArgumentParser(description="공모주 정보 수집")
    ap.add_argument("--pages", type=int, default=3, help="38커뮤니케이션 목록 페이지 수")
    ap.add_argument("--limit", type=int, default=None, help="상세 수집 상한(테스트용)")
    ap.add_argument("--min-year", type=int, default=2025, help="KIND 최소 신고 연도")
    ap.add_argument("--no-dart", action="store_true", help="DART 보강 생략")
    args = ap.parse_args()

    print("[1/4] KIND 공모기업 현황 …", flush=True)
    k = kind.collect(min_year=args.min_year)
    print(f"      {len(k)}건", flush=True)

    print("[2/4] 38커뮤니케이션 상세 …", flush=True)
    f = ipo38.collect(pages=args.pages, limit=args.limit)
    print(f"      {len(f)}건", flush=True)

    print("[3/4] 병합 …", flush=True)
    records = merge(k, f, today=date.today())
    print(f"      {len(records)}건", flush=True)

    print("[4/4] DART 보강 …", flush=True)
    if args.no_dart:
        print("      건너뜀 (--no-dart)", flush=True)
    elif not dart.enabled():
        print("      DART_API_KEY 없음 — 공모자금 사용목적은 비워둡니다", flush=True)
    else:
        by_key = {r["key"]: r for r in records}
        n = dart.enrich(by_key)
        print(f"      사용목적 {n}건 확보", flush=True)

    payload = {
        "generated_at": date.today().isoformat(),
        "count": len(records),
        "sources": {
            "KIND": "https://kind.krx.co.kr/listinvstg/pubofrprogcom.do?method=searchPubofrProgComMain",
            "38커뮤니케이션": "http://www.38.co.kr/html/fund/",
            "DART": "https://opendart.fss.or.kr/",
        },
        "items": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n저장: {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024}KB)")

    from collections import Counter
    for s, c in Counter(r["status"] for r in records).most_common():
        print(f"  {s:8s} {c}")


if __name__ == "__main__":
    main()
