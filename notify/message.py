"""data/ipos.json 에서 '오늘 알아야 할 것'만 뽑아 카톡 한 통 분량으로 압축한다.

카카오 텍스트 템플릿의 text 는 200자 제한이라, 중요한 것부터 넣고 넘치면 자른다.
우선순위: 청약중 > 오늘 마감 임박 > 며칠 안에 시작 > 수요예측중
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ipos.json"
LIMIT = 200          # 카카오 텍스트 템플릿 본문 상한
UPCOMING_DAYS = 3    # 며칠 앞까지를 '임박'으로 볼지


def seoul_today() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def _d(s: str | None) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except ValueError:
        return None


def _status(r: dict, today: date) -> str:
    """사이트(app.js)·수집기(merge.py)와 같은 규칙."""
    L, bF, bT = _d(r.get("listing_date")), _d(r.get("bookbuilding_from")), _d(r.get("bookbuilding_to"))
    sF, sT = _d(r.get("subscription_from")), _d(r.get("subscription_to"))
    if L and today >= L:
        return "상장완료"
    if sF and sT and sF <= today <= sT:
        return "청약중"
    if bF and bT and bF <= today <= bT:
        return "수요예측중"
    if sT and today > sT:
        return "상장대기"
    if sF and today < sF:
        return "청약예정"
    return "기타"


def _price(r: dict) -> str:
    if r.get("offer_price"):
        return f"{r['offer_price']:,}원"
    lo, hi = r.get("band_low"), r.get("band_high")
    if lo and hi:
        return f"{lo:,}원" if lo == hi else f"{lo:,}~{hi:,}원"
    return "미정"


def _num(v: float) -> str:
    """1160.7 → '1,161' / 63.41 → '63.4' / 0.0 → '0' — 자릿수에 맞춰 읽기 쉽게."""
    if v >= 100:
        return f"{v:,.0f}"
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _md(d: str | None) -> str:
    return f"{int(d[5:7])}/{int(d[8:10])}" if d else "?"


def build(today: date | None = None, path: Path = DATA) -> tuple[str, bool]:
    """(메시지, 보낼 가치가 있는지) 를 돌려준다."""
    today = today or seoul_today()
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", [])

    # 알림에서는 상태를 배타적으로 나누지 않는다.
    # '수요예측중이면서 청약이 이틀 뒤'인 종목이 오히려 가장 급하기 때문.
    live, soon, booking = [], [], []
    for r in items:
        sF, sT = _d(r.get("subscription_from")), _d(r.get("subscription_to"))
        L = _d(r.get("listing_date"))
        if L and today >= L:
            continue
        if sF and sT and sF <= today <= sT:
            live.append(r)
        elif sF and 0 < (sF - today).days <= UPCOMING_DAYS:
            soon.append(r)
        elif _status(r, today) == "수요예측중":
            booking.append(r)

    live.sort(key=lambda r: r.get("subscription_to") or "")
    soon.sort(key=lambda r: r.get("subscription_from") or "")
    booking.sort(key=lambda r: r.get("bookbuilding_to") or "")

    lines = [f"📌 오늘의 공모주 ({_md(today.isoformat())})"]

    if live:
        lines.append(f"\n🔴 청약중 {len(live)}건")
        for r in live[:3]:
            end = _d(r.get("subscription_to"))
            tail = " (오늘 마감)" if end == today else f" ~{_md(r.get('subscription_to'))}"
            lines.append(f"· {r['name']}{tail} {_price(r)}")
            bits = []
            if r.get("institutional_competition") is not None:
                bits.append(f"기관 {_num(r['institutional_competition'])}:1")
            if r.get("lockup_ratio") is not None:
                bits.append(f"확약 {_num(r['lockup_ratio'])}%")
            if bits:
                lines.append("  " + " · ".join(bits))

    if soon:
        lines.append(f"\n⏰ {UPCOMING_DAYS}일 내 청약")
        for r in soon[:4]:
            days = (_d(r["subscription_from"]) - today).days
            lines.append(f"· {r['name']} D-{days} {_price(r)}")

    if booking and not live and not soon:
        lines.append(f"\n📊 수요예측중 {len(booking)}건")
        for r in booking[:3]:
            lines.append(f"· {r['name']} ~{_md(r.get('bookbuilding_to'))}")

    # 200자를 넘으면 뒷줄부터 통째로 덜어낸다 (줄 중간에서 끊지 않는다)
    while len("\n".join(lines)) > LIMIT and len(lines) > 1:
        lines.pop()
    text = "\n".join(lines).rstrip()

    worth_sending = bool(live or soon)
    return text, worth_sending


if __name__ == "__main__":
    msg, worth = build()
    print(msg)
    print(f"\n--- {len(msg)}자 / 발송대상: {'예' if worth else '아니오(조용한 날)'}")
