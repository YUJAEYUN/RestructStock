# RestructStock

구조조정(구조조정/희망퇴직/인력감축) 뉴스가 나온 회사들이 이후 주가를 얼마나 회복하는지
분석하는 프로젝트. 전체 방법론은 PRD를 참고.

## 데이터

- `NewsResult_*.xlsx`: 빅카인즈(BigKinds) 뉴스 검색 결과 원본 (2010.01.01 ~ 2026.07.06,
  제목에 구조조정/희망퇴직/인력감축 포함).

## 파이프라인 (`scripts/`)

순서대로 실행:

1. `01_load_news.py` — 엑셀 4개를 합치고, 빅카인즈가 표시한 중복/예외 기사를 제거.
   → `data/processed/news_clean.parquet`
2. `02_extract_companies.py` — 기사에서 실제 회사명 후보를 추출. 정부기관/협회/노조/
   외국기업/지역명/업종 통칭/인물명 등 노이즈를 블록리스트로 걸러낸다 (정밀도 우선,
   재현율은 희생하는 방향). 상세 로직은 스크립트 상단 docstring 참고.
   → `data/processed/matched_articles.parquet`, `unmatched_articles.parquet`,
     `company_candidates.csv` (검수용 회사명 후보 요약)
3. `03_cluster_events.py` — 같은 회사에 대해 30일 이내로 근접한 보도를 하나의 "이벤트"로
   묶는다 (같은 사건을 여러 언론사가 보도한 경우 병합, 연도가 다른 재구조조정은 별도 이벤트).
   → `data/processed/events.csv` (최종 이벤트 리스트: 회사명/시작일/기사수/키워드종류/대표제목)

`data/processed/*.parquet`는 용량 문제로 git에 커밋하지 않는다(재생성 가능). CSV 결과물만 커밋.

## 현재 상태 (2026-07-06)

- 3-1(뉴스 데이터 정리) 1차 완료: 31,667건 기사 → 993개 회사 후보, 2,023개 이벤트로 정리.
- 3-2 일부 진행:
  - `FinanceDataReader`로 KRX 현재 상장사/상장폐지 마스터를 수집.
    → `data/reference/listed_companies.csv`, `data/reference/delisted_companies.csv`
  - 뉴스 회사명과 상장/상장폐지 마스터를 보수적으로 정확매칭.
    → `data/processed/company_listing_matches.csv`, `data/processed/events_with_listings.csv`
  - 현재상장 정확매칭 종목 194개와 KOSPI/KOSDAQ 지수 가격을 수집.
    → `data/prices/stocks/`, `data/prices/indices/`
- **남은 제약**:
  - `FinanceDataReader`/`pykrx` 종목 가격 API는 현재 약 3,000거래일만 반환해서,
    수집된 현재상장 종목 가격은 대체로 2014-04-11 이후부터만 존재한다.
    2010~2014년 초 이벤트까지 분석하려면 네이버 차트 XML 기반 장기 가격 보강이 필요하다.
    보강 스크립트 초안은 `scripts/07_fetch_prices_naver_chart.py`에 두었고, 실행은 TODO로 남김.
  - 상장폐지 종목 가격은 별도 provider 검증이 필요하다. 현재는 상장폐지 마스터와 이벤트 매칭만 완료.
  - 회복률 계산(3-3), 사유분류/업종별 집계, DART 교차검증(3-5)은 아직 진행하지 않았다.
- 회사명 후보 추출은 규칙 기반 블록리스트 방식이라 완벽하지 않다. `company_candidates.csv`와
  `events.csv`를 사람이 한 번 훑어보고 제외할 항목을 표시하는 검수 과정이 필요하다
  (PRD 3-1-5 참고).

## TODO

- `company_listing_matches.csv`에서 `unmatched`/`ambiguous` 항목 수동 검수:
  모회사 매핑, 비상장/해외기업 제외, 자회사/브랜드명 정리.
- 2010~2014년 가격 보강:
  `scripts/07_fetch_prices_naver_chart.py` 실행 또는 별도 데이터 파일 확보.
- 상장폐지 종목 가격 수집 provider 확정:
  관찰 기간 내 상장폐지 이벤트를 회복률 0% 처리할 수 있도록 delisting date와 가격 종단일 검증.
- 회복률 계산 스크립트 작성:
  발표 전 60일 평균 대비, 이벤트 후 저점 대비, 시장 초과수익률 기준을 모두 산출.
