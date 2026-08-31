"""38커뮤니케이션 — 공모주 상세 지표 보조 수집.

KIND가 주지 않는 항목을 채운다: 희망공모가 밴드, 기관 수요예측 경쟁률,
의무보유확약 비율과 기간별 분포, 수요예측 가격 분포, 청약경쟁률, 배정 구조,
종목코드, 회사 기본정보.

robots.txt가 전면 허용(Disallow 없음)이나, util.fetch 의 호스트별 딜레이를
지켜 과도한 요청을 내지 않는다. HTTPS는 서버 측 구형 SSL로 실패하므로 http 사용.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .util import display_name, fetch, intval, norm_name, num, parse_date, parse_range

BASE = "http://www.38.co.kr"
LIST = BASE + "/html/fund/index.htm"
DETAIL = BASE + "/html/fund/?o=v&no={no}"

# 목록 유형: 공모청약일정 / 수요예측일정 / 신규상장
LIST_KINDS = ("k", "r", "nw")

# 공모 상세 링크만 골라내는 패턴 — 목록의 './?o=v&no=' 와 '/html/fund/?o=v&no='
_FUND_LINK = re.compile(r"(?:^\./|/html/fund/)\??[^\"]*o=v")

_FIN_MARKER = "재 무 비 율"

# 값이 비어 있는 항목은 '다음 셀'이 곧 다음 라벨이다. 라벨을 값으로 오인하지 않도록
# 조회에 쓰는 라벨 전체를 모아두고 걸러낸다.
KNOWN_LABELS = {
    "종목명", "진행상황", "시장구분", "종목코드", "업종", "대표자", "기업구분",
    "본점소재지", "홈페이지", "대표전화", "최대주주", "매출액", "순이익", "자본금",
    "액면가", "총공모주식수", "상장공모", "희망공모가액", "청약경쟁률", "확정공모가",
    "공모금액", "주간사", "주요일정", "수요예측일", "공모청약일", "배정공고일(신문)",
    "납입일", "환불일", "상장일", "공모사항", "기관경쟁률", "의무보유확약",
    "우리사주조합", "기관투자자등", "일반청약자", "IR일정", "IR일자", "IR장소/시간",
    "수요예측결과", "신규상장", "신규상장일", "현재가", "구분", "합계",
    "법인세비용차감전 계속사업이익",
}  # 이 지점부터는 재무제표 — 라벨이 중복되므로 스캔 중단


# ------------------------------------------------------------------ 목록 수집
def collect_ids(pages: int = 3) -> dict[str, str]:
    """{종목번호(no): 회사명} — 최근 페이지 위주로 모은다."""
    found: dict[str, str] = {}
    for kind in LIST_KINDS:
        for page in range(1, pages + 1):
            try:
                html = fetch(LIST, data={"o": kind, "page": str(page)}, encoding="euc-kr")
            except RuntimeError:
                break
            soup = BeautifulSoup(html, "lxml")
            hit = False
            for a in soup.select('a[href*="o=v"]'):
                href = a.get("href", "")
                if not _FUND_LINK.search(href):
                    continue  # 뉴스·게시판 링크도 o=v 형태라 제외해야 한다
                m = re.search(r"no=(\d+)", href)
                name = a.get_text(strip=True)
                if m and name and len(name) > 1:
                    found.setdefault(m.group(1), name)
                    hit = True
            if not hit:
                break
    return found


# ------------------------------------------------------------------ 상세 파싱
class _Cells:
    """라벨 셀 다음 칸을 값으로 읽는 헬퍼. 첫 등장만 신뢰한다."""

    def __init__(self, cells: list[str]):
        self.cells = cells
        self.index: dict[str, int] = {}
        for i, c in enumerate(cells):
            self.index.setdefault(c, i)

    def after(self, label: str, offset: int = 1) -> str | None:
        i = self.index.get(label)
        if i is None or i + offset >= len(self.cells):
            return None
        value = self.cells[i + offset]
        # 값이 비어 다음 라벨로 넘어간 경우
        return None if value in KNOWN_LABELS else value

    def find_from(self, label: str) -> int | None:
        return self.index.get(label)


def _shares_and_pct(text: str | None) -> dict | None:
    """'1,500,000 주  (75.0%)' → {'shares':1500000,'pct':75.0}"""
    if not text:
        return None
    shares = intval(text)
    m = re.search(r"\(([\d.]+)\s*%\)", text)
    pct = float(m.group(1)) if m else None
    if shares is None and pct is None:
        return None
    return {"shares": shares, "pct": pct}


def _lockup_breakdown(c: _Cells) -> dict | None:
    out = {}
    for label, key in [("6개월 확약", "m6"), ("3개월 확약", "m3"),
                       ("1개월 확약", "m1"), ("15일 확약", "d15")]:
        v = intval(c.after(label))
        if v is not None:
            out[key] = v
    if not out:
        return None
    total = intval(c.after("합계"))
    if total is not None:
        out["total"] = total
    return out


def _price_distribution(c: _Cells) -> list[dict] | None:
    """수요예측 가격대별 참여 분포 (가격미제시 / 상단초과 / 상단 / … / 하단미만)."""
    start = c.find_from("가격 미제시")
    if start is None:
        return None
    rows, i = [], start
    while i + 3 < len(c.cells) and len(rows) < 10:
        label = c.cells[i]
        if label.startswith("합계"):
            break
        cnt, shares, pct = c.cells[i + 1], c.cells[i + 2], c.cells[i + 3]
        rows.append({
            "band": label,
            "orders": intval(cnt),
            "shares": intval(shares),
            "pct": num(pct) if "%" in pct else None,
        })
        i += 4
    return rows or None


def parse_detail(no: str) -> dict | None:
    html = fetch(DETAIL.format(no=no), encoding="euc-kr")
    soup = BeautifulSoup(html, "lxml")

    cells = [t.get_text(" ", strip=True) for t in soup.find_all(["td", "th"])]
    cells = [t for t in cells if t]
    # 재무제표 구간 이후는 라벨이 중복되므로 잘라낸다.
    for i, t in enumerate(cells):
        # 페이지 전체 텍스트를 품은 래퍼 셀에 걸리지 않도록 짧은 셀만 마커로 인정
        if len(t) < 30 and _FIN_MARKER in t:
            cells = cells[:i]
            break
    c = _Cells(cells)

    name = c.after("종목명")
    if not name:
        return None

    band_low = band_high = None
    band = c.after("희망공모가액")
    if band:
        nums = re.findall(r"[\d,]+", band)
        if len(nums) >= 2:
            band_low, band_high = int(nums[0].replace(",", "")), int(nums[1].replace(",", ""))

    sub_comp = c.after("청약경쟁률")
    proportional = None
    if sub_comp:
        m = re.search(r"비례\s*([\d.,]+)", sub_comp)
        proportional = num(m.group(1)) if m else None

    bb_from, bb_to = parse_range(c.after("수요예측일"))
    sub_from, sub_to = parse_range(c.after("공모청약일"))

    def mil(label: str) -> int | None:
        """'20,000 (백만원)' → 원 단위."""
        v = intval(c.after(label))
        return v * 1_000_000 if v is not None else None

    data = {
        "name": display_name(name),
        "code": c.after("종목코드"),
        "market": c.after("시장구분"),
        "status": c.after("진행상황"),
        "industry": c.after("업종"),
        "ceo": c.after("대표자"),
        "company_class": c.after("기업구분"),
        "address": c.after("본점소재지"),
        "homepage": c.after("홈페이지"),
        "revenue": mil("매출액"),
        "net_income": mil("순이익"),
        "capital": mil("자본금"),
        "par_value": intval(c.after("액면가")),
        "shares_offered": intval(c.after("총공모주식수")),
        "offer_structure": c.after("상장공모"),
        "band_low": band_low,
        "band_high": band_high,
        "offer_price": intval(c.after("확정공모가")),
        "offer_amount": mil("공모금액"),
        "underwriters": [u.strip() for u in (c.after("주간사") or "").split(",") if u.strip()],
        "bookbuilding_from": bb_from,
        "bookbuilding_to": bb_to,
        "subscription_from": sub_from,
        "subscription_to": sub_to,
        "payment_date": parse_date(c.after("납입일")),
        "refund_date": parse_date(c.after("환불일")),
        "listing_date": parse_date(c.after("상장일")),
        "subscription_competition": num(sub_comp),
        "proportional_competition": proportional,
        "institutional_competition": num(c.after("기관경쟁률")),
        "lockup_ratio": num(c.after("의무보유확약")),
        "lockup_breakdown": _lockup_breakdown(c),
        "price_distribution": _price_distribution(c),
        "allocation": {
            k: v for k, v in {
                "employee": _shares_and_pct(c.after("우리사주조합")),
                "institutional": _shares_and_pct(c.after("기관투자자등")),
                "retail": _shares_and_pct(c.after("일반청약자")),
            }.items() if v
        },
        "source": {"ipo38": DETAIL.format(no=no)},
    }

    # 수요예측 전 종목에도 '의무보유확약 0.00%' 자리표시자가 박혀 있다.
    # 기관경쟁률이 나오기 전까지는 수요예측 결과를 없는 값으로 취급한다.
    if data["institutional_competition"] is None:
        for field in ("lockup_ratio", "lockup_breakdown", "price_distribution"):
            data[field] = None

    return {k: v for k, v in data.items() if v not in (None, "", [], {})}


def collect(pages: int = 3, limit: int | None = None) -> dict[str, dict]:
    ids = collect_ids(pages=pages)
    out: dict[str, dict] = {}
    for n, (no, _name) in enumerate(sorted(ids.items(), key=lambda x: -int(x[0]))):
        if limit and n >= limit:
            break
        try:
            d = parse_detail(no)
        except Exception:  # noqa: BLE001 — 한 종목 실패가 전체를 막지 않게
            continue
        if d:
            out[norm_name(d["name"])] = d
    return out


if __name__ == "__main__":
    import json
    d = parse_detail("2306")
    print(json.dumps(d, ensure_ascii=False, indent=2))
