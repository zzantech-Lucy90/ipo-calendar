"""카카오톡 알림 최초 1회 설정 — 리프레시 토큰을 발급받는다.

터미널에서 직접 실행하세요:

    python3 -m notify.setup_kakao

미리 해둘 것 (카카오 개발자 https://developers.kakao.com):
  1. 내 애플리케이션 > 애플리케이션 추가하기
  2. 앱 설정 > 플랫폼 > Web 플랫폼 등록 > 사이트 도메인에  https://localhost
  3. 제품 설정 > 카카오 로그인 > 활성화 ON
  4. 제품 설정 > 카카오 로그인 > Redirect URI 에  https://localhost  등록
  5. 제품 설정 > 카카오 로그인 > 동의항목 >
     '카카오톡 메시지 전송(talk_message)' 을 '이용 중 동의' 로 설정
  6. 앱 설정 > 앱 키 > REST API 키 복사
"""
from __future__ import annotations

import re
import sys
import urllib.parse

import requests

AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
REDIRECT = "https://localhost"
SCOPE = "talk_message"


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n중단했습니다.")
        raise SystemExit(1)


def main() -> int:
    print(__doc__)
    print("=" * 64)

    rest_key = ask("REST API 키를 붙여넣고 Enter: ")
    if not rest_key:
        print("REST API 키가 필요합니다.")
        return 1

    params = urllib.parse.urlencode({
        "client_id": rest_key,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
    })
    print("\n[1단계] 아래 주소를 브라우저에 붙여넣고 카카오 로그인·동의를 완료하세요.\n")
    print(f"  {AUTH_URL}?{params}\n")
    print("[2단계] 동의하면 '연결할 수 없음' 같은 빈 페이지로 이동합니다. 정상입니다.")
    print("        그 페이지의 주소창 전체를 복사해 오세요.")
    print("        (https://localhost/?code=XXXXX... 형태)\n")

    raw = ask("주소 또는 code 값을 붙여넣고 Enter: ")
    m = re.search(r"code=([^&\s]+)", raw)
    code = m.group(1) if m else raw
    if not code:
        print("code 를 찾지 못했습니다.")
        return 1

    print("\n토큰 요청 중…")
    r = requests.post(TOKEN_URL, timeout=20, data={
        "grant_type": "authorization_code",
        "client_id": rest_key,
        "redirect_uri": REDIRECT,
        "code": code,
    })
    body = r.json()
    if r.status_code != 200 or "refresh_token" not in body:
        print(f"\n❌ 실패 ({r.status_code}): {body}")
        print("\n자주 나오는 원인:")
        print("  · code 는 1회용입니다. 이미 썼다면 [1단계] 주소부터 다시 하세요.")
        print("  · Redirect URI 가 https://localhost 로 등록돼 있는지 확인하세요.")
        print("  · 동의항목에서 talk_message 가 켜져 있는지 확인하세요.")
        return 1

    refresh = body["refresh_token"]
    access = body["access_token"]

    print("\n✅ 발급 성공\n")
    print("=" * 64)
    print("저장소 Secrets 에 아래 두 개를 등록하세요.")
    print("  Settings > Secrets and variables > Actions > New repository secret\n")
    print(f"  이름: KAKAO_REST_API_KEY   값: {rest_key}")
    print(f"  이름: KAKAO_REFRESH_TOKEN  값: {refresh}")
    print("=" * 64)

    if ask("\n지금 테스트 메시지를 보내볼까요? (y/N) ").lower().startswith("y"):
        from .kakao import send_to_me
        from .message import build
        text, _ = build()
        try:
            send_to_me(access, text, "https://zzantech-lucy90.github.io/ipo-calendar/")
            print("\n✅ 카카오톡을 확인해 보세요. '나와의 채팅'에 도착했습니다.")
        except RuntimeError as e:
            print(f"\n❌ {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
