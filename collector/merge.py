"""KIND(공식) + 38커뮤니케이션(보조)을 한 레코드로 합치고 파생지표를 만든다.

원칙: 일정·확정공모가·공모금액처럼 공식 소스가 가진 값은 KIND를 신뢰하고,
KIND에 비어 있거나 KIND가 아직 반영하지 못한 건(임박 공모)은 38로 채운다.
"""
from __future__ import annotations

from datetime import date, datetime

# KIND를 우선하는 필드 (공식 공시 기반)
KIND_PRIORITY = [
    "market", "filed_date", "bookbuilding_from", "bookbuilding_to",
    "subscription_from", "subscription_to", "payment_date", "listing_date",
    "offer_price", "offer_amount", "underwriters",
]


def _d(s: str | None) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except ValueError:
        return None


def status_of(rec: dict, today: date) -> str:
    listing = _d(rec.get("listing_date"))
    bb_f, bb_t = _d(rec.get("bookbuilding_from")), _d(rec.get("bookbuilding_to"))
    s_f, s_t = _d(rec.get("subscription_from")), _d(rec.get("subscription_to"))

    if listing and today >= listing:
        return "상장완료"
    if s_f and s_t and s_f <= today <= s_t:
        return "청약중"
    if bb_f and bb_t and bb_f <= today <= bb_t:
        return "수요예측중"
    if s_t and today > s_t:
        return "상장대기"
    if s_f and today < s_f:
        return "청약예정"
    if bb_f and today < bb_f:
        return "수요예측예정"
    return "일정미정"


def _band_position(rec: dict) -> dict | None:
    """확정공모가가 희망밴드의 어디에 놓였는지 — 수요예측 흥행의 1차 지표."""
    lo, hi, price = rec.get("band_low"), rec.get("band_high"), rec.get("offer_price")
    if not (lo and hi and price):
        return None
    if price > hi:
        label, pct = "상단 초과", round((price / hi - 1) * 100, 1)
    elif price == hi:
        label, pct = "상단 확정", 0.0
    elif price < lo:
        label, pct = "하단 미달", round((price / lo - 1) * 100, 1)
    elif price == lo:
        label, pct = "하단 확정", 0.0
    else:
        label, pct = "밴드 내", round((price - lo) / (hi - lo) * 100, 1)
    return {"label": label, "pct": pct}


def _dday(rec: dict, today: date) -> int | None:
    """가장 가까운 다음 이벤트까지 남은 일수."""
    for field in ("subscription_from", "subscription_to", "listing_date"):
        d = _d(rec.get(field))
        if d and d >= today:
            return (d - today).days
    return None


def merge(kind: dict[str, dict], ipo38: dict[str, dict],
          today: date | None = None) -> list[dict]:
    today = today or date.today()
    keys = set(kind) | set(ipo38)

    out: list[dict] = []
    for key in keys:
        k, f = kind.get(key, {}), ipo38.get(key, {})
        rec: dict = {}
        rec.update(f)   # 38 전체를 깔고
        for field in KIND_PRIORITY:   # 공식값으로 덮어쓴다 (KIND에 값이 있을 때만)
            if k.get(field) not in (None, "", []):
                rec[field] = k[field]
        rec["name"] = k.get("name") or f.get("name")
        rec["key"] = key
        rec["sources"] = {**f.get("source", {}), **k.get("source", {})}
        rec.pop("source", None)

        if not rec.get("name"):
            continue

        rec["status"] = status_of(rec, today)
        rec["dday"] = _dday(rec, today)
        band = _band_position(rec)
        if band:
            rec["band_position"] = band
        rec["has_official"] = key in kind

        out.append({k2: v for k2, v in rec.items() if v not in (None, "", [], {})})

    # 청약일 임박 순 → 그다음 최신 순
    def sort_key(r: dict):
        s = r.get("subscription_from") or r.get("bookbuilding_from") or r.get("filed_date") or ""
        return s
    out.sort(key=sort_key, reverse=True)
    return out
