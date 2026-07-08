# RestructStock

구조조정(구조조정/희망퇴직/인력감축) 뉴스가 나온 회사들이 이후 주가를 얼마나 회복하는지
분석하는 프로젝트. 전체 방법론은 PRD를 참고

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
4. `04_fetch_market_reference.py` ~ `09_analyze_results.py` — KRX 상장/상장폐지 마스터 수집,
   뉴스 회사명-종목코드 매칭, 주가/지수 데이터 수집, 회복률(30/90/180/365일, 시장 대비 초과수익률) 계산.
   → `data/reference/*.csv`, `data/prices/`, `data/processed/recovery_results.csv`, `data/analysis/*.csv`
5. `10_generate_html_dashboard.py` — `recovery_results.csv`를 회사 스토리 중심 대시보드로 시각화.
   회사별 카드(주가 vs 시장지수 그래프, ✅회복/🔴미회복/💀상장폐지/⏳관찰중 배지, 평이한 한글 설명 문장)와
   연도·시장·보도유형별 회복 비율 요약 차트로 구성. Chart.js는 CDN 대신 `scripts/vendor/chart.umd.min.js`를
   빌드 시점에 읽어 HTML에 인라인으로 넣어서, 결과물 하나만으로 오프라인에서도 열리게 했다.
   → `data/analysis/dashboard.html`

`data/processed/*.parquet`는 용량 문제로 git에 커밋하지 않는다(재생성 가능). CSV/HTML 결과물만 커밋.

## 현재 상태 (2026-07-08)

- 3-1(뉴스 데이터 정리) 1차 완료: 31,667건 기사 → 993개 회사 후보, 2,023개 이벤트로 정리.
- 3-2/3-3 진행: KRX 상장/상장폐지 마스터 매칭, 주가·지수 데이터 수집(2014-04 이후),
  회복률(30/90/180/365일, 시장 대비 초과수익률) 계산까지 완료. 결과는
  `data/processed/recovery_results.csv` (797건, 228개사).
- 시각화: `data/analysis/dashboard.html`. 통계표/전문용어 대신 회사별 "뉴스 나온 날 이후
  주가 어떻게 됐나" 카드(회사 주가 vs 시장지수 그래프 + 평이한 문장 + 회복 배지) 중심으로 구성.
  전체 회복 비율은 상장폐지 포함/제외 두 버전을 모두 보여준다 (PRD 5번 주의사항 반영).
- **남은 제약**:
  - 종목 가격은 대체로 2014-04-11 이후부터만 존재해서 2010~2014년 초 이벤트는 아직 분석 못함
    (보강 스크립트 초안 `scripts/07_fetch_prices_naver_chart.py`, 실행은 TODO).
  - 사유분류(실적부진형 vs 선제적재편형), 업종별 집계, DART 교차검증(3-5)은 아직 진행하지 않았다.
    (이전에 있던 "업종" 집계는 KRX 소속부/시장구분 데이터가 실제 업종과 뒤섞여 있어 신뢰도가 낮아 제외했다.)
- 회사명 후보 추출은 규칙 기반 블록리스트 방식이라 완벽하지 않다. `company_candidates.csv`와
  `events.csv`를 사람이 한 번 훑어보고 제외할 항목을 표시하는 검수 과정이 필요하다
  (PRD 3-1-5 참고).

## TODO

- `company_listing_matches.csv`에서 `unmatched`/`ambiguous` 항목 수동 검수:
  모회사 매핑, 비상장/해외기업 제외, 자회사/브랜드명 정리.
- 2010~2014년 가격 보강:
  `scripts/07_fetch_prices_naver_chart.py` 실행 또는 별도 데이터 파일 확보.
- 구조조정 사유 분류(실적부진형/선제적재편형/업종전반형) 및 업종별 집계 (정확한 업종 데이터 확보 필요).
- DART 공시 교차검증(뉴스 보도일 vs 공시일 비교).
