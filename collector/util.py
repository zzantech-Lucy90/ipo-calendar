"""공통 유틸 — HTTP 세션, 회사명 정규화, 숫자/날짜 파싱."""
from __future__ import annotations

import re
import time
import unicodedata
from datetime import date, datetime

import requests

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

_session: requests.Session | None = None
_last_hit: dict[str, float] = {}
POLITE_DELAY = 0.7  # 같은 호스트 연속 요청 간 최소 간격(초)


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9"})
    return _session


def fetch(url: str, *, method: str = "GET", data: dict | None = None,
          encoding: str | None = None, timeout: int = 25, retries: int = 3) -> str:
    """호스트별 딜레이를 지키며 가져오고 본문 텍스트를 돌려준다."""
    host = re.sub(r"^https?://([^/]+).*", r"\1", url)
    wait = POLITE_DELAY - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            s = session()
            r = s.post(url, data=data, timeout=timeout) if method == "POST" \
                else s.get(url, params=data, timeout=timeout)
            _last_hit[host] = time.time()
            r.raise_for_status()
            if encoding:
                r.encoding = encoding
            return r.text
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"fetch 실패: {url} ({last_err})")


# ---------------------------------------------------------------- 회사명 정규화
_SUFFIX = re.compile(r"(주식회사|㈜|\(주\)|\(유\)|주\)|\(재\))")
_PAREN_ALIAS = re.compile(r"\((?:구|前|구\.)[.,]?\s*[^)]*\)")  # "멜콘(구.에스앤에프솔루션)"
_SPACE = re.compile(r"\s+")


def norm_name(name: str) -> str:
    """서로 다른 소스의 회사명을 같은 키로 묶기 위한 정규화."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name)
    s = _PAREN_ALIAS.sub("", s)
    s = _SUFFIX.sub("", s)
    s = _SPACE.sub("", s)
    return s.strip().lower()


def display_name(name: str) -> str:
    """화면에 쓸 이름 — 별칭 괄호만 떼고 원형은 유지."""
    s = unicodedata.normalize("NFKC", name or "")
    s = _PAREN_ALIAS.sub("", s)
    return _SPACE.sub(" ", s).strip()


# ------------------------------------------------------------------- 값 파싱
def num(text: str | None) -> float | None:
    """'12,345원', '63.41:1', '0.17%' 등에서 앞쪽 숫자를 뽑는다."""
    if not text:
        return None
    m = re.search(r"-?[\d,]+(?:\.\d+)?", text.replace(" ", ""))
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def intval(text: str | None) -> int | None:
    v = num(text)
    return int(v) if v is not None else None


_DATE = re.compile(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})")


def parse_date(text: str | None) -> str | None:
    """'2026-09-15', '2026.09.15' → 'YYYY-MM-DD'."""
    if not text:
        return None
    m = _DATE.search(text)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_range(text: str | None) -> tuple[str | None, str | None]:
    """'2026-09-15 ~ 2026-09-16' 또는 '2026.09.16~09.22' → (시작, 끝).

    끝쪽에 연도가 생략된 축약형(38커뮤니케이션 표기)을 함께 처리한다.
    """
    if not text:
        return None, None
    parts = re.split(r"[~〜–—]", text)
    start = parse_date(parts[0]) if parts else None
    end = None
    if len(parts) > 1:
        end = parse_date(parts[1])
        if end is None and start:
            m = re.search(r"(\d{1,2})[.\-/월]\s*(\d{1,2})", parts[1])
            if m:
                mo, d = int(m.group(1)), int(m.group(2))
                y = int(start[:4])
                if mo < int(start[5:7]):  # 연말→연초를 넘어가는 경우
                    y += 1
                try:
                    end = date(y, mo, d).isoformat()
                except ValueError:
                    end = None
    return start, end or start


def today() -> str:
    return datetime.now().date().isoformat()
