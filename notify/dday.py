"""청약 D-N 종목을 뽑아낸다 — 공모주 소개글 작성 트리거.

    python3 -m notify.dday           # 오늘 기준 D-4
    python3 -m notify.dday --days 2  # D-2
    python3 -m notify.dday --spac    # 스팩도 포함
    python3 -m notify.dday --json    # 기계용 출력

글쓰기 자체는 여기서 하지 않는다. GitHub Actions 러너에는 글을 쓸 모델이 없다.
이 스크립트는 '오늘 어느 종목 글을 써야 하는가'만 확정하고, 실제 집필은
로컬에서 Claude 에게 이 출력을 넘겨 진행한다.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import timedelta
from pathlib import Path

from .message import DATA, _d, _price, seoul_today

# 스팩은 공모가 2,000원 고정에 합병 대상이 미정이라 종목별 개별 소개글로 쓰면
# 내용이 겹친다. 기본적으로 제외하고, 필요하면 묶음 글로 따로 다룬다.
_SPAC = re.compile(r"스팩|기업인수목적")


def is_spac(rec: dict) -> bool:
    return bool(_SPAC.search(rec.get("name", "")))


def find(days: int = 4, include_spac: bool = False, path: Path = DATA,
         today=None) -> list[dict]:
    today = today or seoul_today()
    target = (today + timedelta(days=days)).isoformat()
    payload = json.loads(path.read_text(encoding="utf-8"))

    hits = []
    for r in payload.get("items", []):
        if r.get("subscription_from") != target:
            continue
        if is_spac(r) and not include_spac:
            continue
        hits.append(r)
    hits.sort(key=lambda r: -(r.get("offer_amount") or 0))
    return hits


def brief(r: dict) -> str:
    """집필에 바로 넘길 수 있는 요약 한 덩어리."""
    bb = f"{r.get('bookbuilding_from')}~{r.get('bookbuilding_to')}"
    sub = f"{r.get('subscription_from')}~{r.get('subscription_to')}"
    lines = [
        f"■ {r['name']} ({r.get('market')}, {r.get('industry') or '업종 미상'})",
        f"   대표 {r.get('ceo') or '-'} · 주관사 {', '.join(r.get('underwriters', [])) or '-'}",
        f"   희망공모가 {_price(r)} · 공모금액 {(r.get('offer_amount') or 0)//100_000_000}억원"
        f" · {r.get('shares_offered'):,}주" if r.get("shares_offered") else "",
        f"   수요예측 {bb} · 청약 {sub} · 환불 {r.get('refund_date') or '-'}"
        f" · 상장 {r.get('listing_date') or '미정'}",
        f"   매출 {(r.get('revenue') or 0)//100_000_000}억 · 순손익 {(r.get('net_income') or 0)//100_000_000}억",
    ]
    if r.get("institutional_competition") is not None:
        lines.append(f"   기관경쟁률 {r['institutional_competition']}:1 · 확약 {r.get('lockup_ratio')}%")
    else:
        lines.append(f"   ⚠ 수요예측 결과 미공시 (마감 {r.get('bookbuilding_to')}, 확정공모가는 보통 청약 전날)")
    lines.append(f"   출처 {r.get('sources', {}).get('ipo38', '-')}")
    return "\n".join(l for l in lines if l)


def main() -> int:
    ap = argparse.ArgumentParser(description="청약 D-N 종목 추출")
    ap.add_argument("--days", type=int, default=4)
    ap.add_argument("--spac", action="store_true", help="스팩 포함")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    hits = find(days=args.days, include_spac=args.spac)
    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=1))
        return 0

    today = seoul_today()
    target = today + timedelta(days=args.days)
    print(f"기준 {today} · 청약 시작 {target} (D-{args.days})\n")
    if not hits:
        print("해당 종목 없음 — 오늘은 쓸 글이 없다.")
    else:
        print(f"소개글 작성 대상 {len(hits)}건\n")
        for r in hits:
            print(brief(r), "\n")
    skipped = [r["name"] for r in find(days=args.days, include_spac=True) if is_spac(r)]
    if skipped and not args.spac:
        print(f"(스팩 제외: {', '.join(skipped)} — 묶음 글로 다루려면 --spac)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
