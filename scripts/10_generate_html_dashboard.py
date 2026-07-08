"""
구조조정 보도 기업 주가 회복률 분석 결과를 "회사 스토리" 중심으로 보여주는
인터랙티브 HTML 대시보드를 생성한다.

기존 버전은 초과수익률/기준지수 같은 계산 용어와 통계표가 중심이라 읽기 어려웠다.
이 버전은 사건 하나하나를 "이 회사, 이 날 뉴스 나옴 → 그 후 이렇게 됨" 카드로 보여주고,
회복 여부는 ✅/🔴/💀 같은 배지로, 회사 주가와 시장 지수는 파란선-회색선 두 줄 그래프로
표현해서 숫자를 몰라도 그래프 모양만으로 이해할 수 있게 하는 것이 목표다.

"회복"의 정의는 PRD 그대로: 사건 이후 주가가 사건 이전 수준(첫 보도 전 60거래일 평균)으로
돌아왔는가 (return_Nd >= 0). 시장 대비 성과(초과수익률)는 회사선-시장선 그래프 비교로
대체하고, 숫자 자체는 펼쳤을 때만 보이는 부가 정보로 내렸다.

입력: data/processed/recovery_results.csv, data/prices/stocks/*.csv, data/prices/indices/*.csv
출력: data/analysis/dashboard.html
"""
from pathlib import Path
import json
import math
import pandas as pd

RESULTS_CSV = Path("data/processed/recovery_results.csv")
STOCK_DIR = Path("data/prices/stocks")
INDEX_DIR = Path("data/prices/indices")
OUT_HTML = Path("data/analysis/dashboard.html")
CHARTJS_VENDOR = Path("scripts/vendor/chart.umd.min.js")

INDEX_FILES = {
    "KOSPI": INDEX_DIR / "KS11.csv",
    "KOSDAQ": INDEX_DIR / "KQ11.csv",
    "KOSDAQ GLOBAL": INDEX_DIR / "KQ11.csv",
}

TODAY = pd.Timestamp.now().normalize()

HORIZONS = [30, 90, 180, 365]


def latest_available(row):
    """가장 긴 관찰 기간부터 값이 있는 것을 찾는다. (365일 > 180일 > 90일 > 30일)"""
    for d in reversed(HORIZONS):
        val = row.get(f"return_{d}d")
        if val is not None and not (isinstance(val, float) and math.isnan(val)):
            return d, val
    return None, None


def classify_status(row, event_date):
    if row.get("is_bankrupt_delist"):
        return "delisted", None, None
    horizon, ret = latest_available(row)
    if horizon is None:
        if (event_date + pd.Timedelta(days=30)) > TODAY:
            return "pending", None, None
        return "no_data", None, None
    status = "recovered" if ret >= 0 else "not_recovered"
    return status, horizon, ret


def verdict_sentence(company, status, horizon, ret, excess):
    if status == "delisted":
        return f"{company}는 보도 이후 상장폐지되어 투자금을 모두 잃은 것으로 처리했습니다."
    if status == "pending":
        return "보도된 지 얼마 안 돼서, 아직 회복 여부를 판단하기엔 일러요."
    if status == "no_data":
        return "주가 데이터가 부족해 회복 여부를 판단할 수 없습니다."
    pct = f"{abs(ret) * 100:.0f}%"
    dir_word = "올랐어요" if ret >= 0 else "낮아요"
    base = f"보도 {horizon}일 후 주가는 보도 전보다 {pct} {dir_word}"
    if excess is None:
        return base + "."
    exc_pct = f"{abs(excess) * 100:.0f}%p"
    exc_word = "시장 전체보다도 좋았어요" if excess >= 0 else "시장 전체보다는 나빴어요"
    return base + f" ({exc_pct} {exc_word})."


def build_chart_data(code, market, event_date, index_cache, baseline_row):
    stock_file = STOCK_DIR / f"{code}.csv"
    if not stock_file.exists() or market not in index_cache:
        return []
    try:
        stock_df = pd.read_csv(stock_file)
        stock_df["Date"] = pd.to_datetime(stock_df["Date"])
        stock_df = stock_df.sort_values("Date").reset_index(drop=True)
    except Exception:
        return []

    idx_df = index_cache[market]
    start_range = event_date - pd.Timedelta(days=60)
    end_range = event_date + pd.Timedelta(days=365)
    stock_window = stock_df[(stock_df["Date"] >= start_range) & (stock_df["Date"] <= end_range)]
    stock_sampled = stock_window.iloc[::3].copy()

    stock_at_event = stock_df[stock_df["Date"] >= event_date].head(1)
    idx_at_event = idx_df[idx_df["Date"] >= event_date].head(1)
    if stock_at_event.empty or idx_at_event.empty:
        return [], None

    p_stock_ref = stock_at_event["Close"].values[0]
    p_idx_ref = idx_at_event["Close"].values[0]

    # 표본 추출(3일 간격)이 첫 보도일과 정확히 맞아떨어지지 않을 수 있어,
    # 기준(0%)이 되는 실제 거래일 행을 항상 포함시킨다 (그래프에 첫 보도일 표시용).
    anchor_date = stock_at_event["Date"].values[0]
    if anchor_date not in stock_sampled["Date"].values:
        stock_sampled = pd.concat([stock_sampled, stock_at_event]).sort_values("Date")
    stock_sampled = stock_sampled.drop_duplicates(subset="Date").reset_index(drop=True)

    delisting_date = pd.to_datetime(baseline_row["상장폐지일"]) if not pd.isna(baseline_row["상장폐지일"]) else None
    is_bankrupt = baseline_row["is_bankrupt_delist"] == True

    chart_data = []
    zero_idx = None
    for i, s_row in stock_sampled.iterrows():
        s_date = s_row["Date"]
        s_price = s_row["Close"]
        idx_row_match = idx_df[idx_df["Date"] >= s_date].head(1)
        if idx_row_match.empty:
            continue
        i_price = idx_row_match["Close"].values[0]
        if delisting_date and s_date >= delisting_date and is_bankrupt:
            s_price = 0.0
        s_ret = (s_price / p_stock_ref) - 1.0 if p_stock_ref > 0 else 0.0
        i_ret = (i_price / p_idx_ref) - 1.0 if p_idx_ref > 0 else 0.0
        if s_date == anchor_date:
            zero_idx = len(chart_data)
        chart_data.append({
            "d": s_date.strftime("%Y-%m-%d"),
            "s": round(s_ret * 100, 2),
            "i": round(i_ret * 100, 2),
        })
    return chart_data, zero_idx


def safe_float(v):
    return None if pd.isna(v) else float(v)


def main():
    df = pd.read_csv(RESULTS_CSV)
    df["이벤트시작일_dt"] = pd.to_datetime(df["이벤트시작일"])

    index_cache = {}
    for m, path in INDEX_FILES.items():
        if path.exists():
            idx_df = pd.read_csv(path)
            idx_df["Date"] = pd.to_datetime(idx_df["Date"])
            index_cache[m] = idx_df.sort_values("Date").reset_index(drop=True)

    events_json = []
    df_sorted = df.sort_values("이벤트시작일", ascending=False)

    for _, row in df_sorted.iterrows():
        code_raw = row["종목코드"]
        if pd.isna(code_raw):
            continue
        code = str(code_raw).split(".")[0].zfill(6)
        event_date = row["이벤트시작일_dt"]
        market = row["시장"]

        status, horizon, ret = classify_status(row, event_date)
        excess = safe_float(row.get(f"excess_{horizon}d")) if horizon else None
        verdict = verdict_sentence(row["회사명"], status, horizon, ret, excess)
        chart_data, zero_idx = build_chart_data(code, market, event_date, index_cache, row)
        if not chart_data:
            continue

        events_json.append({
            "company": row["회사명"],
            "code": code,
            "event_date": row["이벤트시작일"],
            "market": market,
            "keywords": row["키워드종류"],
            "headline": row["대표제목"],
            "status": status,
            "horizon": horizon,
            "return": ret,
            "excess": excess,
            "verdict": verdict,
            "delist_date": row["상장폐지일"] if not pd.isna(row["상장폐지일"]) else None,
            "delist_reason": row["상장폐지사유"] if not pd.isna(row["상장폐지사유"]) else None,
            "returns": {f"{d}d": safe_float(row.get(f"return_{d}d")) for d in HORIZONS},
            "excesses": {f"{d}d": safe_float(row.get(f"excess_{d}d")) for d in HORIZONS},
            "baseline_stock": safe_float(row.get("baseline_stock")),
            "chart": chart_data,
            "zero_idx": zero_idx,
        })

    print(f"사건 {len(events_json)}건에 대해 그래프 데이터 생성 완료")

    # ---- 집계: 연도별, 시장별, 키워드별 회복 비율 (상장폐지/데이터없음 제외한 판정 가능 사건 기준) ----
    def recovery_rate(rows):
        judged = [r for r in rows if r["status"] in ("recovered", "not_recovered", "delisted")]
        if not judged:
            return None, 0
        recovered = sum(1 for r in judged if r["status"] == "recovered")
        return recovered / len(judged), len(judged)

    years = sorted(set(pd.to_datetime(e["event_date"]).year for e in events_json))
    year_agg = []
    for y in years:
        rows = [e for e in events_json if pd.to_datetime(e["event_date"]).year == y]
        rate, n = recovery_rate(rows)
        year_agg.append({"label": str(y), "count": len(rows), "rate": rate, "n_judged": n})

    market_agg = []
    for m in ["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"]:
        rows = [e for e in events_json if e["market"] == m]
        rate, n = recovery_rate(rows)
        if rows:
            market_agg.append({"label": m, "count": len(rows), "rate": rate, "n_judged": n})

    keyword_agg = []
    for kw in ["구조조정", "희망퇴직", "인력감축"]:
        rows = [e for e in events_json if kw in e["keywords"]]
        rate, n = recovery_rate(rows)
        keyword_agg.append({"label": kw, "count": len(rows), "rate": rate, "n_judged": n})

    # ---- 히어로 지표 ----
    total_events = len(events_json)
    unique_companies = len(set(e["company"] for e in events_json))
    delisted_events = sum(1 for e in events_json if e["status"] == "delisted")
    judged_all = [e for e in events_json if e["status"] in ("recovered", "not_recovered", "delisted")]
    judged_alive = [e for e in events_json if e["status"] in ("recovered", "not_recovered")]
    rate_with_delisted = (sum(1 for e in judged_all if e["status"] == "recovered") / len(judged_all)) if judged_all else 0
    rate_alive_only = (sum(1 for e in judged_alive if e["status"] == "recovered") / len(judged_alive)) if judged_alive else 0

    hero = {
        "total_events": total_events,
        "unique_companies": unique_companies,
        "delisted_events": delisted_events,
        "rate_with_delisted": rate_with_delisted,
        "rate_alive_only": rate_alive_only,
        "n_judged": len(judged_all),
    }

    chartjs_src = CHARTJS_VENDOR.read_text(encoding="utf-8")
    html = render_html(events_json, year_agg, market_agg, keyword_agg, hero, chartjs_src)
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"저장 완료: {OUT_HTML} ({OUT_HTML.stat().st_size / 1024 / 1024:.1f} MB)")


def render_html(events_json, year_agg, market_agg, keyword_agg, hero, chartjs_src):
    events_data = json.dumps(events_json, ensure_ascii=False)
    year_data = json.dumps(year_agg, ensure_ascii=False)
    market_data = json.dumps(market_agg, ensure_ascii=False)
    keyword_data = json.dumps(keyword_agg, ensure_ascii=False)
    hero_data = json.dumps(hero, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RestructStock - 구조조정 뉴스 이후, 주가는 어떻게 됐을까?</title>
<meta name="description" content="구조조정/희망퇴직/인력감축 뉴스가 나온 기업들의 이후 주가 흐름을 회사별로 한눈에 보여주는 대시보드">
<script>{chartjs_src}</script>
<style>
:root {{
  --surface-1: #fcfcfb;
  --surface-2: #f9f9f7;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --text-muted: #898781;
  --gridline: #e1e0d9;
  --border: rgba(11,11,11,0.10);
  --accent: #2a78d6;
  --accent-wash: rgba(42,120,214,0.10);
  --gray-line: #898781;
  --good: #0ca30c;
  --serious: #ec835a;
  --critical: #d03b3b;
  --good-wash: rgba(12,163,12,0.10);
  --serious-wash: rgba(236,131,90,0.12);
  --critical-wash: rgba(208,59,59,0.10);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --surface-1: #1a1a19;
    --surface-2: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted: #898781;
    --gridline: #2c2c2a;
    --border: rgba(255,255,255,0.10);
    --accent: #3987e5;
    --accent-wash: rgba(57,135,229,0.14);
    --gray-line: #898781;
    --good: #0ca30c;
    --serious: #ec835a;
    --critical: #e66767;
    --good-wash: rgba(12,163,12,0.16);
    --serious-wash: rgba(236,131,90,0.16);
    --critical-wash: rgba(230,103,103,0.16);
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--surface-2);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  padding-bottom: 4rem;
}}
a {{ color: var(--accent); }}
.wrap {{ max-width: 1100px; margin: 0 auto; padding: 0 1.25rem; }}
header {{ padding: 2.5rem 0 1.25rem; }}
h1 {{ font-size: 1.7rem; margin: 0 0 0.35rem; }}
.subtitle {{ color: var(--text-secondary); font-size: 1rem; line-height: 1.5; max-width: 640px; }}

.criteria-box {{
  background: var(--accent-wash); border: 1px solid var(--border); border-radius: 12px;
  padding: 1rem 1.25rem; margin-top: 1.25rem; font-size: 0.85rem; color: var(--text-secondary);
}}
.criteria-box .title {{ font-weight: 600; color: var(--text-primary); margin-bottom: 0.5rem; }}
.criteria-box ul {{ margin: 0; padding-left: 1.1rem; line-height: 1.65; }}
.criteria-box li {{ margin-bottom: 0.2rem; }}
.criteria-box strong {{ color: var(--text-primary); }}

.hero-row {{ display: flex; gap: 1.25rem; align-items: stretch; flex-wrap: wrap; margin: 1.5rem 0; }}
.hero-card {{
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 14px;
  padding: 1.5rem 1.75rem; flex: 1 1 320px;
}}
.hero-figure {{ font-size: 3rem; font-weight: 700; line-height: 1; margin: 0.25rem 0 0.35rem; }}
.hero-label {{ font-size: 0.95rem; color: var(--text-secondary); }}
.hero-note {{ font-size: 0.82rem; color: var(--text-muted); margin-top: 0.5rem; line-height: 1.5; }}

.stat-row {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
.stat-tile {{
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 1rem 1.25rem; flex: 1 1 150px; min-width: 140px;
}}
.stat-tile .v {{ font-size: 1.5rem; font-weight: 600; }}
.stat-tile .l {{ font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.15rem; }}

.section-title {{ font-size: 1.15rem; font-weight: 600; margin: 2.25rem 0 0.25rem; }}
.section-desc {{ font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 1rem; }}

.mini-charts {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
.mini-card {{
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 1rem 1.1rem; flex: 1 1 300px;
}}
.mini-card h4 {{ margin: 0 0 0.75rem; font-size: 0.92rem; font-weight: 600; }}
.mini-card .cvs-wrap {{ height: 190px; }}

.filter-row {{
  display: flex; gap: 0.6rem; flex-wrap: wrap; align-items: center;
  margin: 1.5rem 0 1rem; padding: 0.9rem 1rem; background: var(--surface-1);
  border: 1px solid var(--border); border-radius: 12px;
}}
.filter-row input, .filter-row select {{
  font-family: inherit; font-size: 0.88rem; padding: 0.45rem 0.7rem;
  border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface-2); color: var(--text-primary);
}}
.filter-row input[type="text"] {{ flex: 1 1 220px; }}
.result-count {{ font-size: 0.82rem; color: var(--text-muted); margin: 0.25rem 0 1rem; }}

.card-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }}
.card {{
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 14px;
  padding: 1.1rem 1.2rem; cursor: pointer; transition: border-color 0.15s;
}}
.card:hover {{ border-color: var(--accent); }}
.card-top {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; }}
.card-company {{ font-weight: 700; font-size: 1.02rem; }}
.card-meta {{ font-size: 0.78rem; color: var(--text-muted); margin-top: 0.15rem; }}
.badge {{
  display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.78rem; font-weight: 600;
  padding: 0.2rem 0.55rem; border-radius: 999px; white-space: nowrap;
}}
.badge.recovered {{ background: var(--good-wash); color: var(--good); }}
.badge.not_recovered {{ background: var(--serious-wash); color: var(--serious); }}
.badge.delisted {{ background: var(--critical-wash); color: var(--critical); }}
.badge.no_data {{ background: var(--gridline); color: var(--text-muted); }}
.badge.pending {{ background: var(--gridline); color: var(--text-secondary); }}
.badge.pill {{ background: var(--gridline); color: var(--text-secondary); font-weight: 500; }}
.card-verdict {{ font-size: 0.85rem; color: var(--text-secondary); margin: 0.6rem 0 0.5rem; line-height: 1.45; }}
.spark {{ width: 100%; height: 46px; display: block; margin: 0.3rem 0 0.2rem; }}
.spark-caption {{ font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.4rem; }}
.card-headline {{ font-size: 0.78rem; color: var(--text-muted); margin-top: 0.5rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

.detail {{ display: none; margin-top: 0.9rem; padding-top: 0.9rem; border-top: 1px solid var(--border); }}
.detail.open {{ display: block; }}
.detail .cvs-wrap {{ height: 220px; }}
.detail-caption {{ font-size: 0.78rem; color: var(--text-muted); margin-top: 0.4rem; }}
.legend-line {{ display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.78rem; color: var(--text-secondary); margin-right: 0.9rem; }}
.legend-swatch {{ width: 16px; height: 2px; display: inline-block; }}

details.raw-numbers {{ margin-top: 0.7rem; font-size: 0.78rem; color: var(--text-secondary); }}
details.raw-numbers summary {{ cursor: pointer; color: var(--accent); }}
.raw-table {{ width: 100%; border-collapse: collapse; margin-top: 0.5rem; font-variant-numeric: tabular-nums; }}
.raw-table th, .raw-table td {{ text-align: right; padding: 0.25rem 0.4rem; border-bottom: 1px solid var(--gridline); }}
.raw-table th:first-child, .raw-table td:first-child {{ text-align: left; }}

#loadMoreBtn {{
  display: block; margin: 1.5rem auto 0; padding: 0.6rem 1.5rem; font-size: 0.88rem;
  border-radius: 999px; border: 1px solid var(--border); background: var(--surface-1);
  color: var(--text-primary); cursor: pointer;
}}
#loadMoreBtn:hover {{ border-color: var(--accent); }}

footer {{ margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border); font-size: 0.78rem; color: var(--text-muted); line-height: 1.6; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>구조조정 뉴스, 그 회사 주가는 어떻게 됐을까?</h1>
  <div class="subtitle">구조조정·희망퇴직·인력감축 뉴스가 보도된 국내 상장기업들이, 그 이후 주가가 원래 수준으로 돌아왔는지 회사별로 보여줍니다.</div>
  <div class="criteria-box">
    <div class="title">이 대시보드가 쓰는 기준</div>
    <ul>
      <li><strong>사건 구분</strong>: 같은 회사라도 뉴스 보도 간격이 30일을 넘으면 별도 사건으로 나눔 (예: 2015년 구조조정과 2020년 구조조정은 각각 다른 사건). 30일 이내 보도는 같은 사건으로 보고 가장 빠른 보도일(첫 보도일) 하나로 합침.</li>
      <li><strong>관찰 기간</strong>: 첫 보도일 기준 전 60거래일 ~ 첫 보도 후 365일. 그래프의 세로 점선이 첫 보도일임.</li>
      <li><strong>기준 주가</strong>: 첫 보도 전 60거래일 종가의 평균.</li>
      <li><strong>회복 판단</strong>: 관찰 가능한 가장 긴 기간(최대 365일, 최근 보도는 확보된 기간까지)의 주가가 기준 주가보다 높아지면 "회복", 아니면 "아직 못 돌아옴". 상장폐지(부도성)는 무조건 회복 실패(0원)로 처리하고, 첫 보도 후 30일이 안 지났으면 "관찰중"으로 판단을 미룸. 시장 대비 성과는 이 판단에 넣지 않고 그래프·문장으로 별도 표시.</li>
    </ul>
  </div>
</header>

<div class="hero-row">
  <div class="hero-card" style="flex: 1 1 260px;">
    <div class="hero-label">판단 가능한 사건 중, 주가가 <strong>원래 수준을 회복</strong>한 비율</div>
    <div class="hero-figure" id="heroFigure">-</div>
    <div class="hero-note">상장폐지된 기업도 "회복 실패(0원)"로 포함한 수치입니다. 상장폐지 기업을 빼면 수치가 더 좋아 보일 수 있어, 아래에 두 버전을 함께 표시합니다.</div>
  </div>
  <div class="stat-row" style="flex: 2 1 420px;">
    <div class="stat-tile"><div class="v" id="statTotal">-</div><div class="l">전체 사건</div></div>
    <div class="stat-tile"><div class="v" id="statCompanies">-</div><div class="l">분석 기업 수</div></div>
    <div class="stat-tile"><div class="v" id="statDelisted">-</div><div class="l">상장폐지된 기업</div></div>
    <div class="stat-tile"><div class="v" id="statAliveRate">-</div><div class="l">상장폐지 제외 시 회복 비율</div></div>
  </div>
</div>

<div class="section-title">전체적으로 보면</div>
<div class="section-desc">연도·시장·보도 유형별로, 판단 가능한 사건 중 몇 %가 회복했는지 보여줍니다. 막대 안 숫자는 사건 건수입니다.</div>
<div class="mini-charts">
  <div class="mini-card"><h4>연도별 회복 비율</h4><div class="cvs-wrap"><canvas id="yearChart"></canvas></div></div>
  <div class="mini-card"><h4>시장별 회복 비율</h4><div class="cvs-wrap"><canvas id="marketChart"></canvas></div></div>
  <div class="mini-card"><h4>보도 유형별 회복 비율</h4><div class="cvs-wrap"><canvas id="keywordChart"></canvas></div></div>
</div>

<div class="section-title">회사별로 보기</div>
<div class="section-desc">카드를 클릭하면 그 회사의 주가(파란선)와 코스피/코스닥 지수(회색 점선)를 함께 볼 수 있습니다. 그래프는 첫 보도일 기준 <strong>전 60거래일 ~ 후 365일</strong> 구간이며, 세로 점선이 첫 보도일입니다.</div>
<div class="filter-row">
  <input type="text" id="searchInput" placeholder="회사명, 종목코드, 기사 제목 검색">
  <select id="statusFilter">
    <option value="all">전체 상태</option>
    <option value="recovered">✅ 회복함</option>
    <option value="not_recovered">🔴 아직 못 돌아옴</option>
    <option value="delisted">💀 상장폐지</option>
    <option value="pending">⏳ 관찰중(최근 보도)</option>
  </select>
  <select id="keywordFilter">
    <option value="all">전체 보도 유형</option>
    <option value="구조조정">구조조정</option>
    <option value="희망퇴직">희망퇴직</option>
    <option value="인력감축">인력감축</option>
  </select>
  <select id="sortSelect">
    <option value="date_desc">최신 보도순</option>
    <option value="date_asc">오래된 보도순</option>
    <option value="best">많이 회복한 순</option>
    <option value="worst">많이 못 돌아온 순</option>
  </select>
</div>
<div class="result-count" id="resultCount"></div>
<div class="card-grid" id="cardGrid"></div>
<button id="loadMoreBtn">더 보기</button>

<footer>
  판단 기준은 위 "이 대시보드가 쓰는 기준" 박스를 참고하세요.
  구조조정 보도와 주가 회복은 상관관계를 보여주는 것이며, 인과관계를 증명하는 것은 아닙니다.
</footer>

</div>

<script>
const EVENTS = {events_data};
const YEAR_AGG = {year_data};
const MARKET_AGG = {market_data};
const KEYWORD_AGG = {keyword_data};
const HERO = {hero_data};

const STATUS_LABEL = {{ recovered: '✅ 회복함', not_recovered: '🔴 아직 못 돌아옴', delisted: '💀 상장폐지', pending: '⏳ 관찰중', no_data: '자료 부족' }};
const fmtPct = v => (v === null || v === undefined) ? '-' : (v >= 0 ? '+' : '') + (v * 100).toFixed(1) + '%';

function setText(id, text) {{ document.getElementById(id).textContent = text; }}

setText('heroFigure', (HERO.rate_with_delisted * 100).toFixed(0) + '%');
setText('statTotal', HERO.total_events.toLocaleString());
setText('statCompanies', HERO.unique_companies.toLocaleString());
setText('statDelisted', HERO.delisted_events.toLocaleString());
setText('statAliveRate', (HERO.rate_alive_only * 100).toFixed(0) + '%');

// ---------------------------------------------------------
// Sparkline: small inline SVG, no chart library needed
// ---------------------------------------------------------
function sparklineSVG(chart, zeroIdx) {{
  if (!chart || chart.length < 2) return '';
  const w = 300, h = 46;
  const allVals = chart.flatMap(p => [p.s, p.i]);
  const min = Math.min(...allVals, 0), max = Math.max(...allVals, 0);
  const range = (max - min) || 1;
  const scaleX = i => (i / (chart.length - 1)) * w;
  const scaleY = v => h - ((v - min) / range) * h;
  const path = arr => arr.map((p, i) => `${{i === 0 ? 'M' : 'L'}}${{scaleX(i).toFixed(1)}},${{scaleY(p).toFixed(1)}}`).join(' ');
  const sPath = path(chart.map(p => p.s));
  const iPath = path(chart.map(p => p.i));
  const zeroY = scaleY(0).toFixed(1);
  const eventMarker = (zeroIdx === null || zeroIdx === undefined) ? '' :
    `<line x1="${{scaleX(zeroIdx).toFixed(1)}}" y1="0" x2="${{scaleX(zeroIdx).toFixed(1)}}" y2="${{h}}" stroke="var(--text-muted)" stroke-width="1.5" stroke-dasharray="2,2"/>`;
  return `<svg class="spark" viewBox="0 0 ${{w}} ${{h}}" preserveAspectRatio="none">
    <line x1="0" y1="${{zeroY}}" x2="${{w}}" y2="${{zeroY}}" stroke="var(--gridline)" stroke-width="1"/>
    ${{eventMarker}}
    <path d="${{iPath}}" fill="none" stroke="var(--gray-line)" stroke-width="2" stroke-dasharray="4,3" opacity="0.7"/>
    <path d="${{sPath}}" fill="none" stroke="var(--accent)" stroke-width="2"/>
  </svg>`;
}}

// ---------------------------------------------------------
// Card grid: filter, sort, paginate
// ---------------------------------------------------------
const PAGE_SIZE = 24;
let visible = [];
let shown = 0;
let openIndex = null;
let detailChart = null;

function applyFilters() {{
  const q = document.getElementById('searchInput').value.trim().toLowerCase();
  const statusF = document.getElementById('statusFilter').value;
  const kwF = document.getElementById('keywordFilter').value;
  const sortV = document.getElementById('sortSelect').value;

  visible = EVENTS.filter(e => {{
    if (statusF !== 'all' && e.status !== statusF) return false;
    if (kwF !== 'all' && !e.keywords.includes(kwF)) return false;
    if (q) {{
      const hay = (e.company + ' ' + e.code + ' ' + e.headline).toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});

  visible.sort((a, b) => {{
    if (sortV === 'date_desc') return a.event_date < b.event_date ? 1 : -1;
    if (sortV === 'date_asc') return a.event_date > b.event_date ? 1 : -1;
    const ra = a.return === null || a.return === undefined ? -999 : a.return;
    const rb = b.return === null || b.return === undefined ? -999 : b.return;
    if (sortV === 'best') return rb - ra;
    if (sortV === 'worst') return ra - rb;
    return 0;
  }});

  shown = 0;
  openIndex = null;
  document.getElementById('cardGrid').innerHTML = '';
  setText('resultCount', `${{visible.length.toLocaleString()}}건`);
  renderMore();
}}

function cardHTML(e, idx) {{
  const statusCls = e.status;
  const statusLabel = STATUS_LABEL[e.status] || '자료 부족';
  return `
    <div class="card" data-idx="${{idx}}">
      <div class="card-top">
        <div>
          <div class="card-company">${{e.company}} <span style="color:var(--text-muted); font-weight:400; font-size:0.82rem;">${{e.code}}</span></div>
          <div class="card-meta">${{e.event_date}} · <span class="badge pill">${{e.market}}</span></div>
        </div>
        <span class="badge ${{statusCls}}">${{statusLabel}}</span>
      </div>
      ${{sparklineSVG(e.chart, e.zero_idx)}}
      <div class="spark-caption">회색 세로 점선 = 첫 보도일(${{e.event_date}})</div>
      <div class="card-verdict">${{e.verdict}}</div>
      <div class="card-headline" title="${{e.headline.replace(/"/g, '&quot;')}}">${{e.headline}}</div>
      <div class="detail" id="detail-${{idx}}"></div>
    </div>`;
}}

function renderMore() {{
  const grid = document.getElementById('cardGrid');
  const slice = visible.slice(shown, shown + PAGE_SIZE);
  const frag = document.createElement('div');
  frag.innerHTML = slice.map((e, i) => cardHTML(e, shown + i)).join('');
  while (frag.firstChild) grid.appendChild(frag.firstChild);
  shown += slice.length;
  document.getElementById('loadMoreBtn').style.display = shown >= visible.length ? 'none' : 'block';

  grid.querySelectorAll('.card').forEach(card => {{
    card.onclick = (ev) => {{
      if (ev.target.closest('details')) return;
      toggleDetail(parseInt(card.dataset.idx, 10));
    }};
  }});
}}

function toggleDetail(idx) {{
  const e = visible[idx];
  const el = document.getElementById(`detail-${{idx}}`);
  if (openIndex === idx) {{
    el.classList.remove('open');
    el.innerHTML = '';
    if (detailChart) {{ detailChart.destroy(); detailChart = null; }}
    openIndex = null;
    return;
  }}
  if (openIndex !== null) {{
    const prevEl = document.getElementById(`detail-${{openIndex}}`);
    if (prevEl) {{ prevEl.classList.remove('open'); prevEl.innerHTML = ''; }}
    if (detailChart) {{ detailChart.destroy(); detailChart = null; }}
  }}
  openIndex = idx;
  el.classList.add('open');
  el.innerHTML = `
    <div>
      <span class="legend-line"><span class="legend-swatch" style="background:var(--accent);"></span>${{e.company}} 주가</span>
      <span class="legend-line"><span class="legend-swatch" style="background:var(--gray-line); border-top: 2px dashed var(--gray-line); height:0;"></span>${{e.market}} 지수</span>
    </div>
    <div class="cvs-wrap"><canvas id="detailCanvas-${{idx}}"></canvas></div>
    <div class="detail-caption">파란선이 회색 점선보다 위에 있으면, 이 회사가 같은 기간 시장 전체보다 잘 버틴 것입니다. 세로 점선이 첫 보도일(${{e.event_date}})입니다.</div>
    <details class="raw-numbers">
      <summary>자세한 숫자 보기</summary>
      <table class="raw-table">
        <thead><tr><th>기간</th><th>회사 주가 변화</th><th>시장 대비</th></tr></thead>
        <tbody>
          ${{[30, 90, 180, 365].map(d => `<tr><td>${{d}}일 후</td><td>${{fmtPct(e.returns[d + 'd'])}}</td><td>${{fmtPct(e.excesses[d + 'd'])}}</td></tr>`).join('')}}
        </tbody>
      </table>
      ${{e.delist_date ? `<p style="margin-top:0.5rem;">상장폐지일: ${{e.delist_date}} (${{e.delist_reason || '사유 미확인'}})</p>` : ''}}
    </details>
  `;
  const ctx = document.getElementById(`detailCanvas-${{idx}}`).getContext('2d');
  const zeroIdx = e.zero_idx;
  const eventLinePlugin = {{
    id: 'eventLine',
    afterDraw(chart) {{
      if (zeroIdx === null || zeroIdx === undefined) return;
      const {{ ctx: c, chartArea, scales }} = chart;
      const x = scales.x.getPixelForValue(zeroIdx);
      if (x < chartArea.left || x > chartArea.right) return;
      c.save();
      c.beginPath();
      c.setLineDash([3, 3]);
      c.moveTo(x, chartArea.top);
      c.lineTo(x, chartArea.bottom);
      c.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted');
      c.lineWidth = 1.5;
      c.stroke();
      c.setLineDash([]);
      c.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-secondary');
      c.font = '11px system-ui, sans-serif';
      c.textAlign = 'center';
      c.fillText('첫 보도일', x, chartArea.top - 4);
      c.restore();
    }}
  }};
  detailChart = new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: e.chart.map(p => p.d),
      datasets: [
        {{ label: e.company, data: e.chart.map(p => p.s), borderColor: getComputedStyle(document.documentElement).getPropertyValue('--accent'), borderWidth: 2, pointRadius: 0, tension: 0.15 }},
        {{ label: e.market + ' 지수', data: e.chart.map(p => p.i), borderColor: getComputedStyle(document.documentElement).getPropertyValue('--gray-line'), borderWidth: 2, borderDash: [5, 4], pointRadius: 0, tension: 0.15 }}
      ]
    }},
    plugins: [eventLinePlugin],
    options: {{
      responsive: true, maintainAspectRatio: false,
      layout: {{ padding: {{ top: 14 }} }},
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: ctx2 => `${{ctx2.dataset.label}}: ${{ctx2.raw.toFixed(1)}}%` }} }}
      }},
      scales: {{
        y: {{ ticks: {{ callback: v => v + '%' }}, grid: {{ color: 'rgba(128,128,128,0.15)' }} }},
        x: {{ ticks: {{ maxTicksLimit: 8 }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}}

document.getElementById('searchInput').addEventListener('input', applyFilters);
document.getElementById('statusFilter').addEventListener('change', applyFilters);
document.getElementById('keywordFilter').addEventListener('change', applyFilters);
document.getElementById('sortSelect').addEventListener('change', applyFilters);
document.getElementById('loadMoreBtn').addEventListener('click', renderMore);

applyFilters();

// ---------------------------------------------------------
// Aggregate mini bar charts (single axis: recovery rate %)
// ---------------------------------------------------------
function barChart(canvasId, agg) {{
  const ctx = document.getElementById(canvasId).getContext('2d');
  const labels = agg.map(a => a.label);
  const rates = agg.map(a => a.rate === null ? 0 : Math.round(a.rate * 1000) / 10);
  const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels,
      datasets: [{{
        data: rates,
        backgroundColor: accentColor,
        borderRadius: 4,
        maxBarThickness: 28
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: c => `회복 비율 ${{c.raw}}% (사건 ${{agg[c.dataIndex].count}}건)`
          }}
        }}
      }},
      scales: {{
        y: {{ min: 0, max: 100, ticks: {{ callback: v => v + '%' }}, grid: {{ color: 'rgba(128,128,128,0.15)' }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
}}
barChart('yearChart', YEAR_AGG);
barChart('marketChart', MARKET_AGG);
barChart('keywordChart', KEYWORD_AGG);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
