"""KIND(한국거래소 기업공시채널) — 공모기업 현황.

공식 소스이자 일정의 기준선. 시장구분·신고서제출일·수요예측일정·청약일정·
납입일·확정공모가·공모금액·상장예정일·주관사를 제공한다.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from .util import display_name, intval, norm_name, parse_date, parse_range, fetch

URL = "https://kind.krx.co.kr/listinvstg/pubofrprogcom.do"
PAGE = "https://kind.krx.co.kr/listinvstg/pubofrprogcom.do?method=searchPubofrProgComMain"

# 다운로드용 뷰가 8~10칸짜리 순수 표를 그대로 내려준다.
COLS = ["시장구분", "회사명", "신고서제출일", "수요예측일정", "청약일정",
        "납입일", "확정공모가", "공모금액", "상장예정일", "주관사"]


def collect(min_year: int = 2024) -> dict[str, dict]:
    html = fetch(
        URL,
        method="POST",
        data={
            "method": "searchPubofrProgComSub",
            "forward": "pubofrprogcom_down",
            "currentPageSize": "3000",
            "pageIndex": "1",
        },
        encoding="euc-kr",
    )
    soup = BeautifulSoup(html, "lxml")

    out: dict[str, dict] = {}
    for tr in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < 10 or cells[0] == "시장구분":
            continue
        row = dict(zip(COLS, cells))

        filed = parse_date(row["신고서제출일"])
        listing = parse_date(row["상장예정일"])
        if not filed or int(filed[:4]) < min_year:
            continue

        name = display_name(row["회사명"])
        key = norm_name(name)
        if not key:
            continue

        book_from, book_to = parse_range(row["수요예측일정"])
        sub_from, sub_to = parse_range(row["청약일정"])

        out[key] = {
            "name": name,
            "market": row["시장구분"].replace("상장추진", "").strip() or None,
            "filed_date": filed,
            "bookbuilding_from": book_from,
            "bookbuilding_to": book_to,
            "subscription_from": sub_from,
            "subscription_to": sub_to,
            "payment_date": parse_date(row["납입일"]),
            "listing_date": listing,
            "offer_price": intval(row["확정공모가"]),
            # KIND는 백만원 단위로 준다 → 원 단위로 환산
            "offer_amount": (lambda v: v * 1_000_000 if v else None)(intval(row["공모금액"])),
            "underwriters": [u.strip() for u in row["주관사"].split(",") if u.strip()],
            "source": {"kind": PAGE},
        }
    return out


if __name__ == "__main__":  # 단독 점검용
    d = collect()
    print(f"KIND {len(d)}건")
    for k in list(d)[:3]:
        print(" ", d[k])
