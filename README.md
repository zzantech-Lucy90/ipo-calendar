# 공모주 청약 캘린더

공모주 판단에 필요한 숫자를 한 페이지에 모아 보여주는 정적 사이트입니다.
공시 원문을 매일 자동 수집해 `data/ipos.json` 으로 만들고, GitHub Pages로 배포합니다.

- 청약 일정 (수요예측 · 청약 · 납입 · 환불 · 상장)
- 수요예측 결과 (기관경쟁률, 가격대별 참여 분포)
- 의무보유확약 비율과 기간별(6개월/3개월/1개월/15일) 분포
- 공모 청약 경쟁률 (단순 · 비례)
- 회사 개요 (업종 · 대표자 · 자본금 · 매출 · 손익 · 소재지)
- 공모자금 사용목적 *(DART API 키 등록 시)*

## 데이터 출처

| 항목 | 출처 | 성격 |
|---|---|---|
| 시장구분, 신고서 제출일, 일정, 확정공모가, 공모금액, 주관사 | [KIND](https://kind.krx.co.kr/listinvstg/pubofrprogcom.do?method=searchPubofrProgComMain) (한국거래소) | 공식 |
| 공모자금 사용목적, 정식 회사개요, 증권신고서 링크 | [OpenDART](https://opendart.fss.or.kr/) (금융감독원) | 공식 API |
| 희망공모가 밴드, 기관경쟁률, 의무보유확약, 가격 분포, 청약경쟁률, 배정 물량 | [38커뮤니케이션](http://www.38.co.kr/html/fund/) | 보조 |

일정·공모가·공모금액처럼 공식 소스가 가진 값은 **KIND를 우선**하고, KIND가 아직
반영하지 못한 임박 공모나 KIND에 없는 상세 지표만 보조 소스로 채웁니다.
각 종목 상세의 "원문 확인"에서 출처 페이지로 바로 이동할 수 있습니다.

## 로컬에서 실행

```bash
pip install -r requirements.txt
python3 -m collector.run --pages 3
python3 -m http.server 8765
```

브라우저에서 <http://localhost:8765> 를 엽니다.

| 옵션 | 뜻 |
|---|---|
| `--pages N` | 38커뮤니케이션 목록을 N페이지까지 훑음 (기본 3, 약 90종목) |
| `--min-year Y` | KIND 최소 신고 연도 (기본 2025) |
| `--limit N` | 상세 수집 상한 — 빠른 테스트용 |
| `--no-dart` | DART 보강 생략 |

전체 수집은 약 2분 걸립니다. 서버에 부담을 주지 않도록 호스트별로 요청 간격을 둡니다.

## GitHub Pages 배포

1. 이 폴더를 GitHub 저장소로 push 합니다.
2. **Settings → Pages → Source** 를 `Deploy from a branch`, 브랜치 `main` / 폴더 `/ (root)` 로 지정합니다.
3. 몇 분 뒤 `https://<계정>.github.io/<저장소>/` 에서 열립니다.

## 자동 갱신

`.github/workflows/update.yml` 이 매일 **KST 07:30, 18:30** 두 번 돌면서 `data/ipos.json`
을 갱신하고, 변경이 있을 때만 커밋합니다. 저장소 Actions 탭에서 수동 실행도 됩니다.

## 공모자금 사용목적 켜기

이 항목만 DART 증권신고서 원문에 있어 API 키가 필요합니다.

1. <https://opendart.fss.or.kr/> 에서 무료 인증키를 발급받습니다.
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   에 이름 `DART_API_KEY` 로 등록합니다.
3. 로컬에서는 `export DART_API_KEY=발급받은키` 후 실행합니다.

키가 없으면 이 항목만 비어 있고 나머지는 정상 동작합니다.

## 주의

공시 자료를 자동 수집한 것으로, 정정신고나 원본 입력 오류로 실제와 다를 수 있습니다.
투자 판단과 책임은 투자자 본인에게 있으며, 이 페이지는 투자 권유가 아닙니다.

## 구조

```
index.html            화면
assets/               스타일 · 렌더링 스크립트
collector/
  kind.py             KIND 공모기업 현황
  ipo38.py            38커뮤니케이션 상세 지표
  dart.py             OpenDART 사용목적 · 회사개요
  merge.py            병합 규칙과 파생지표(상태, D-day, 밴드 위치)
  run.py              파이프라인 진입점
data/ipos.json        수집 결과 (사이트가 읽는 파일)
```

브라우저 캐시 때문에 수정이 반영되지 않으면 `index.html` 의 `assets/...?v=1` 숫자를 올려주세요.
