"""OpenDART — 공모자금 사용목적과 정식 회사개요.

38커뮤니케이션에 없는 유일한 항목이 '공모금액의 사용목적'이고, 이건 증권신고서
(지분증권) 원문에만 있다. 여기서는 공식 OpenDART API로 신고서를 찾아 요약표를
파싱한다.

DART_API_KEY 환경변수가 없으면 이 모듈은 조용히 비활성화되고, 나머지 파이프라인
(KIND + 38)은 그대로 동작한다.  키 발급: https://opendart.fss.or.kr/
"""
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .util import norm_name, session

API = "https://opendart.fss.or.kr/api"
CACHE = Path(__file__).resolve().parent.parent / "data" / ".cache"

# 증권신고서(지분증권)
DETAIL_TYPE = "C001"

# 요약표에 등장하는 자금 용도 구분
PURPOSE_LABELS = ["시설자금", "영업양수자금", "운영자금", "채무상환자금",
                  "타법인 증권 취득자금", "타법인증권취득자금", "기타"]


def api_key() -> str | None:
    key = os.environ.get("DART_API_KEY", "").strip()
    return key or None


def enabled() -> bool:
    return api_key() is not None


def _get(path: str, **params):
    params["crtfc_key"] = api_key()
    r = session().get(f"{API}/{path}", params=params, timeout=30)
    r.raise_for_status()
    return r


# --------------------------------------------------------------- 고유번호 사전
def corp_index() -> dict[str, str]:
    """{정규화 회사명: corp_code}. 하루 단위로 캐시한다."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "corp_index.json"
    if cached.exists():
        try:
            return json.loads(cached.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    r = _get("corpCode.xml")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read(z.namelist()[0]).decode("utf-8")
    soup = BeautifulSoup(xml, "lxml-xml")

    idx: dict[str, str] = {}
    for item in soup.find_all("list"):
        name = (item.find("corp_name").text or "").strip()
        code = (item.find("corp_code").text or "").strip()
        if name and code:
            idx.setdefault(norm_name(name), code)
    cached.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    return idx


# ------------------------------------------------------------------ 회사 개요
def company_profile(corp_code: str) -> dict | None:
    try:
        j = _get("company.json", corp_code=corp_code).json()
    except Exception:  # noqa: BLE001
        return None
    if j.get("status") != "000":
        return None
    out = {
        "corp_name": j.get("corp_name"),
        "ceo": j.get("ceo_nm"),
        "established": j.get("est_dt"),
        "address": j.get("adres"),
        "homepage": j.get("hm_url"),
        "industry_code": j.get("induty_code"),
        "fiscal_month": j.get("acc_mt"),
    }
    return {k: v for k, v in out.items() if v}


# --------------------------------------------------------- 증권신고서 → 자금용도
def latest_registration(corp_code: str, bgn_de: str) -> dict | None:
    """가장 최근 증권신고서(지분증권) 접수 건."""
    try:
        j = _get("list.json", corp_code=corp_code, bgn_de=bgn_de.replace("-", ""),
                 pblntf_detail_ty=DETAIL_TYPE, page_count=20).json()
    except Exception:  # noqa: BLE001
        return None
    if j.get("status") != "000" or not j.get("list"):
        return None
    items = sorted(j["list"], key=lambda x: x.get("rcept_dt", ""), reverse=True)
    top = items[0]
    return {
        "rcept_no": top.get("rcept_no"),
        "rcept_dt": top.get("rcept_dt"),
        "report_nm": top.get("report_nm"),
        "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={top.get('rcept_no')}",
    }


def _document_text(rcept_no: str) -> str | None:
    try:
        r = _get("document.xml", rcept_no=rcept_no)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            raw = z.read(z.namelist()[0])
    except Exception:  # noqa: BLE001
        return None
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def use_of_proceeds(rcept_no: str) -> dict | None:
    """증권신고서 요약표에서 '자금의 사용목적' 구분별 금액을 뽑는다."""
    xml = _document_text(rcept_no)
    if not xml:
        return None
    soup = BeautifulSoup(xml, "lxml")

    for table in soup.find_all(["table", "TABLE"]):
        text = table.get_text(" ", strip=True)
        if "시설자금" not in text or "운영자금" not in text:
            continue

        rows = []
        for tr in table.find_all(["tr", "TR"]):
            rows.append([c.get_text(" ", strip=True)
                         for c in tr.find_all(["td", "th", "te", "tu", "TD", "TH", "TE", "TU"])])
        rows = [r for r in rows if any(r)]

        # 라벨 행을 찾고, 그 아래에서 숫자가 들어있는 첫 행을 값으로 본다.
        for i, row in enumerate(rows):
            labels = [c for c in row if any(p in c for p in PURPOSE_LABELS)]
            if len(labels) < 2:
                continue
            for value_row in rows[i + 1:i + 4]:
                if len(value_row) != len(row):
                    continue
                if not any(re.search(r"\d", c) for c in value_row):
                    continue
                items = {}
                for label, val in zip(row, value_row):
                    label = label.strip()
                    amount = re.sub(r"[^\d]", "", val)
                    if label and amount:
                        items[label] = int(amount)
                if items:
                    return {"items": items, "unit": "원" if "원" in text else None}
    return None


# ---------------------------------------------------------------- 진입점
def enrich(records: dict[str, dict], limit: int | None = None) -> int:
    """수집된 공모주 레코드에 DART 정보를 채워 넣는다. 반환값 = 보강 건수."""
    if not enabled():
        return 0
    try:
        idx = corp_index()
    except Exception:  # noqa: BLE001
        return 0

    filled = 0
    for key, rec in records.items():
        if limit is not None and filled >= limit:
            break
        corp_code = idx.get(key)
        if not corp_code:
            continue
        rec.setdefault("dart", {})["corp_code"] = corp_code

        profile = company_profile(corp_code)
        if profile:
            rec["dart"]["profile"] = profile

        bgn = rec.get("filed_date") or rec.get("bookbuilding_from") or "2024-01-01"
        reg = latest_registration(corp_code, bgn_de=bgn)
        if reg:
            rec["dart"]["registration"] = reg
            rec.setdefault("source", {})["dart"] = reg["url"]
            proceeds = use_of_proceeds(reg["rcept_no"])
            if proceeds:
                rec["use_of_proceeds"] = proceeds
                filled += 1
    return filled


if __name__ == "__main__":
    print("DART_API_KEY 설정됨" if enabled() else "DART_API_KEY 없음 — 비활성화 상태")
