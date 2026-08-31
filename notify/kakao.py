"""카카오톡 '나에게 보내기' 전송.

카카오는 자기 자신에게 보내는 memo API 만 앱 검수 없이 열어준다. 따라서 이 스크립트는
앱을 만든 본인 계정으로만 메시지를 보낸다.

필요한 환경변수
  KAKAO_REST_API_KEY   카카오 개발자 > 내 애플리케이션 > 앱 키 > REST API 키
  KAKAO_REFRESH_TOKEN  notify/setup_kakao.py 로 최초 1회 발급
  SITE_URL             메시지 버튼이 열 주소 (없으면 버튼 생략)

액세스 토큰은 몇 시간이면 만료되므로 매 실행마다 리프레시 토큰으로 새로 받는다.
"""
from __future__ import annotations

import json
import os
import sys

import requests

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def refresh_access_token(rest_key: str, refresh_token: str) -> tuple[str, str | None]:
    """(액세스 토큰, 새 리프레시 토큰 또는 None) 을 돌려준다."""
    r = requests.post(TOKEN_URL, timeout=20, data={
        "grant_type": "refresh_token",
        "client_id": rest_key,
        "refresh_token": refresh_token,
    })
    body = r.json()
    if r.status_code != 200 or "access_token" not in body:
        raise RuntimeError(
            f"액세스 토큰 갱신 실패 ({r.status_code}): {body}\n"
            "→ 리프레시 토큰이 만료됐을 수 있습니다. "
            "python3 -m notify.setup_kakao 로 다시 발급하세요."
        )
    # 카카오는 리프레시 토큰 잔여기간이 1개월 미만일 때만 새 토큰을 함께 준다.
    return body["access_token"], body.get("refresh_token")


def send_to_me(access_token: str, text: str, link_url: str | None = None) -> None:
    template: dict = {"object_type": "text", "text": text}
    if link_url:
        template["link"] = {"web_url": link_url, "mobile_web_url": link_url}
        template["button_title"] = "전체 보기"
    else:
        template["link"] = {}

    r = requests.post(SEND_URL, timeout=20,
                      headers={"Authorization": f"Bearer {access_token}"},
                      data={"template_object": json.dumps(template, ensure_ascii=False)})
    body = {}
    try:
        body = r.json()
    except ValueError:
        pass
    if r.status_code != 200 or body.get("result_code") != 0:
        raise RuntimeError(
            f"메시지 전송 실패 ({r.status_code}): {body}\n"
            "→ 카카오 개발자 > 카카오 로그인 > 동의항목에서 "
            "'카카오톡 메시지 전송(talk_message)' 이 켜져 있는지 확인하세요."
        )


def main() -> int:
    rest_key = os.environ.get("KAKAO_REST_API_KEY", "").strip()
    refresh = os.environ.get("KAKAO_REFRESH_TOKEN", "").strip()
    site = os.environ.get("SITE_URL", "").strip() or None

    if not rest_key or not refresh:
        print("KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 이 없습니다 — 알림을 건너뜁니다.")
        return 0

    from .message import build
    text, worth = build()

    force = "--always" in sys.argv
    if not worth and not force:
        print("오늘은 청약중·임박 종목이 없습니다 — 알림을 보내지 않습니다.")
        print(text)
        return 0

    access, new_refresh = refresh_access_token(rest_key, refresh)
    send_to_me(access, text, site)
    print("카카오톡 전송 완료:\n" + text)

    if new_refresh:
        print("\n" + "=" * 60)
        print("⚠️  카카오가 새 리프레시 토큰을 발급했습니다.")
        print("   저장소 Secrets 의 KAKAO_REFRESH_TOKEN 을 아래 값으로 바꾸세요.")
        print("   (바꾸지 않으면 한 달 안에 알림이 끊깁니다)")
        print(f"   {new_refresh}")
        print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
