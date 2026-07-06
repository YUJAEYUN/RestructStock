"""
구조조정 보도 기업 주가 회복률 분석 결과를 시각화하는 인터랙티브 HTML 대시보드를 생성한다.
용어를 쉽게 풀어쓰고, 각 데이터 포인트의 수학적 계산 근거를 추적할 수 있는 펼치기(Detail) 기능을 제공한다.

입력:
  data/analysis/by_keyword.csv
  data/analysis/by_market.csv
  data/analysis/by_year.csv
  data/analysis/by_industry.csv
  data/processed/recovery_results.csv
출력:
  data/analysis/dashboard.html
"""
from pathlib import Path
import json
import pandas as pd

ANALYSIS_DIR = Path("data/analysis")
RESULTS_CSV = Path("data/processed/recovery_results.csv")
OUT_HTML = ANALYSIS_DIR / "dashboard.html"

def main():
    # 1. Load datasets
    by_keyword = pd.read_csv(ANALYSIS_DIR / "by_keyword.csv")
    by_market = pd.read_csv(ANALYSIS_DIR / "by_market.csv")
    by_year = pd.read_csv(ANALYSIS_DIR / "by_year.csv")
    by_industry = pd.read_csv(ANALYSIS_DIR / "by_industry.csv")
    df = pd.read_csv(RESULTS_CSV)
    
    # 2. Serialize to JSON for HTML injection
    keyword_json = by_keyword.to_dict(orient="records")
    market_json = by_market.to_dict(orient="records")
    year_json = by_year.to_dict(orient="records")
    industry_json = by_industry.to_dict(orient="records")
    
    # Selected columns for interactive table and detailed evidence popup
    table_cols = [
        "회사명", "종목코드", "이벤트시작일", "시장", "기사수", "키워드종류", "대표제목",
        "baseline_stock", "baseline_index", 
        "price_30d", "return_30d", "idx_price_30d", "idx_return_30d", "excess_30d",
        "price_90d", "return_90d", "idx_price_90d", "idx_return_90d", "excess_90d",
        "price_180d", "return_180d", "idx_price_180d", "idx_return_180d", "excess_180d",
        "price_365d", "return_365d", "idx_price_365d", "idx_return_365d", "excess_365d",
        "상장폐지일", "상장폐지사유", "is_bankrupt_delist"
    ]
    df_sorted = df.sort_values("이벤트시작일", ascending=False)
    df_table = df_sorted[table_cols].copy()
    # Fill NaNs with None for JSON compatibility
    df_table = df_table.replace({float("nan"): None})
    events_json = df_table.to_dict(orient="records")
    
    # Calculate key aggregate stats
    total_events = len(df)
    unique_companies = df["회사명"].nunique()
    bankruptcies = int(df["is_bankrupt_delist"].sum())
    avg_365d_ret = float(df["return_365d"].mean())
    avg_365d_exc = float(df["excess_365d"].mean())
    
    # HTML Template
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RestructStock - 구조조정 기업 주가 회복률 분석 대시보드</title>
    <meta name="description" content="구조조정, 희망퇴직, 인력감축 보도 이후 국내 상장사들의 주가 회복률 및 시장 초과수익률 대시보드">
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-dark: #0f172a;
            --bg-card: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --accent-blue: #38bdf8;
            --accent-indigo: #6366f1;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            background-color: var(--bg-dark);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(56, 189, 248, 0.12) 0px, transparent 50%);
            background-attachment: fixed;
            min-height: 100vh;
            padding-bottom: 3rem;
        }}

        header {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2.5rem 2rem 1.5rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
        }}

        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #fff 30%, var(--accent-blue) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}

        h1::before {{
            content: '📊';
            font-size: 2.2rem;
        }}

        .subtitle {{
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }}

        .main-container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }}

        /* Glossary section styling */
        .glossary-card {{
            background: rgba(99, 102, 241, 0.08);
            border: 1px dashed rgba(99, 102, 241, 0.3);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 2.5rem;
            backdrop-filter: blur(8px);
        }}

        .glossary-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.1rem;
            font-weight: 700;
            color: #a5b4fc;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .glossary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.25rem;
        }}

        .glossary-item h5 {{
            font-size: 0.9rem;
            font-weight: 600;
            color: #fff;
            margin-bottom: 0.25rem;
        }}

        .glossary-item p {{
            font-size: 0.8rem;
            color: var(--text-muted);
            line-height: 1.4;
        }}

        /* Metrics grid */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }}

        .metric-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            transition: transform 0.3s ease, border-color 0.3s ease;
        }}

        .metric-card:hover {{
            transform: translateY(-5px);
            border-color: rgba(56, 189, 248, 0.3);
        }}

        .metric-label {{
            color: var(--text-muted);
            font-size: 0.85rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}

        .metric-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.8rem;
            font-weight: 700;
            color: #fff;
        }}

        .metric-value.success {{ color: var(--success); }}
        .metric-value.danger {{ color: var(--danger); }}

        .metric-subtext {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.25rem;
        }}

        /* Layout Grid for Charts */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 2rem;
            margin-bottom: 2.5rem;
        }}

        @media (max-width: 1024px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .chart-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 1.75rem;
            backdrop-filter: blur(12px);
        }}

        .chart-card.full-width {{
            grid-column: 1 / -1;
        }}

        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }}

        .chart-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.25rem;
            font-weight: 600;
            color: #fff;
        }}

        .chart-select {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            outline: none;
            cursor: pointer;
        }}

        .chart-container {{
            position: relative;
            height: 380px;
            width: 100%;
        }}

        /* Interactive Events Table Section */
        .table-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 20px;
            padding: 1.75rem;
            backdrop-filter: blur(12px);
        }}

        .table-header-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
            gap: 1rem;
            flex-wrap: wrap;
        }}

        .search-container {{
            display: flex;
            align-items: center;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 0.5rem 1rem;
            min-width: 300px;
        }}

        .search-input {{
            background: transparent;
            border: none;
            color: var(--text-main);
            outline: none;
            width: 100%;
            font-size: 0.9rem;
        }}

        .search-input::placeholder {{
            color: rgba(255, 255, 255, 0.3);
        }}

        .table-container {{
            overflow-x: auto;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            max-height: 600px;
            overflow-y: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
            text-align: left;
        }}

        th {{
            background-color: rgba(15, 23, 42, 0.8);
            color: var(--text-muted);
            padding: 0.85rem 1rem;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            position: sticky;
            top: 0;
            z-index: 10;
            border-bottom: 1px solid var(--border-color);
        }}

        td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-main);
        }}

        .clickable-row {{
            cursor: pointer;
        }}

        .clickable-row:hover {{
            background-color: rgba(255, 255, 255, 0.04);
        }}

        /* Expanded Details styling */
        .details-row td {{
            background-color: rgba(15, 23, 42, 0.4);
            border-bottom: 1px solid var(--border-color);
            padding: 0;
        }}

        .evidence-box {{
            padding: 1.5rem;
            border-left: 4px solid var(--accent-indigo);
            margin: 0.75rem 1rem;
            background: rgba(30, 41, 59, 0.4);
            border-radius: 8px;
        }}

        .evidence-box h4 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1rem;
            color: #fff;
            margin-bottom: 1rem;
        }}

        .evidence-grid {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 1.5rem;
        }}

        @media (max-width: 768px) {{
            .evidence-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .evidence-step {{
            background: rgba(15, 23, 42, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem;
        }}

        .evidence-step strong {{
            display: block;
            font-size: 0.85rem;
            color: var(--accent-blue);
            margin-bottom: 0.5rem;
        }}

        .evidence-step ul {{
            list-style: none;
            font-size: 0.8rem;
        }}

        .evidence-step li {{
            margin-bottom: 0.5rem;
            color: var(--text-muted);
        }}

        .evidence-step li strong {{
            display: inline;
            color: #fff;
        }}

        .evidence-table {{
            width: 100%;
            font-size: 0.8rem;
        }}

        .evidence-table th {{
            position: relative;
            background-color: rgba(15, 23, 42, 0.6);
            padding: 0.5rem 0.75rem;
        }}

        .evidence-table td {{
            padding: 0.5rem 0.75rem;
            background: transparent;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}

        .delist-alert {{
            margin-top: 1rem;
            padding: 0.75rem 1rem;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            border-radius: 8px;
            font-size: 0.8rem;
            color: #fca5a5;
        }}

        .delist-alert.info {{
            background: rgba(56, 189, 248, 0.1);
            border: 1px solid rgba(56, 189, 248, 0.2);
            color: #bae6fd;
        }}

        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .badge.keyword {{
            background-color: rgba(99, 102, 241, 0.2);
            color: #a5b4fc;
            border: 1px solid rgba(99, 102, 241, 0.3);
        }}

        .badge.market {{
            background-color: rgba(56, 189, 248, 0.2);
            color: #7dd3fc;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }}

        .ret-value {{
            font-family: 'Outfit', sans-serif;
            font-weight: 600;
        }}

        .ret-value.positive {{
            color: var(--success);
        }}

        .ret-value.negative {{
            color: var(--danger);
        }}
        
        .ret-value.neutral {{
            color: var(--text-muted);
        }}

        /* Scrollbar styling */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: rgba(15, 23, 42, 0.3);
            border-radius: 8px;
        }}

        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>

    <header>
        <div>
            <h1>RestructStock</h1>
            <div class="subtitle">구조조정 보도 기업 주가 회복률 & 시장 성과 분석 대시보드</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 0.8rem; color: var(--text-muted);">최종 업데이트</div>
            <div style="font-size: 0.9rem; font-weight: 500;">2026년 7월 7일</div>
        </div>
    </header>

    <div class="main-container">

        <!-- Glossary Section -->
        <div class="glossary-card">
            <div class="glossary-title">💡 대시보드 쉽게 읽는 용어집</div>
            <div class="glossary-grid">
                <div class="glossary-item">
                    <h5>구조조정 보도일</h5>
                    <p>뉴스에 구조조정/희망퇴직/인력감축 보도가 처음으로 등장하여 기록된 날짜(시작일)입니다.</p>
                </div>
                <div class="glossary-item">
                    <h5>보도 전 평균 주가 (기준 주가)</h5>
                    <p>뉴스가 보도되기 전 60거래일 동안의 평균 주가입니다. 뉴스 발표 이후 주가가 얼마나 올랐는지 판단하는 기준점이 됩니다.</p>
                </div>
                <div class="glossary-item">
                    <h5>실제 주가 변화율 (실제 수익률)</h5>
                    <p>보도 전 평균 주가 대비, 보도 이후 특정 시점(30일/90일/180일/1년)의 주가가 얼마나 변했는지 나타내는 비율입니다.</p>
                </div>
                <div class="glossary-item">
                    <h5>시장 대비 성과 (시장 초과수익률)</h5>
                    <p>기업의 주가 변화율에서 주식시장 전체의 상승률(코스피/코스닥 지수 상승률)을 뺀 값입니다. 값이 마이너스(-)라면 주가가 올랐더라도 시장 평균보다는 덜 벌었다는 의미입니다.</p>
                </div>
                <div class="glossary-item">
                    <h5>주식시장 퇴출(부도/상장폐지)</h5>
                    <p>관찰 기간 중 자본잠식이나 부도 등으로 인해 상장폐지된 경우입니다. 투자 금액을 모두 잃은 상황이므로, 분석의 현실성을 위해 상장폐지 이후 시점의 실제 주가는 0원(-100% 손실)으로 계산했습니다.</p>
                </div>
            </div>
        </div>

        <!-- Metrics cards row -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">구조조정 보도 건수</div>
                <div class="metric-value">{total_events:,} 건</div>
                <div class="metric-subtext">2010.01 ~ 2026.07 뉴스 통합</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">분석한 기업 수</div>
                <div class="metric-value">{unique_companies:,} 개사</div>
                <div class="metric-subtext">현재 상장사 및 상장폐지사 통합</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">주식시장 퇴출(부도/상장폐지)</div>
                <div class="metric-value danger">{bankruptcies} 개사</div>
                <div class="metric-subtext">보도 이후 1년 이내 부도로 청산된 기업</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">보도 1년 뒤 실제 주가 변화율</div>
                <div class="metric-value success">+{avg_365d_ret * 100:.2f}%</div>
                <div class="metric-subtext">보도 전 60일 평균 대비 평균 변동</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">보도 1년 뒤 시장 대비 평균 성과</div>
                <div class="metric-value danger">{avg_365d_exc * 100:.2f}%</div>
                <div class="metric-subtext">시장 지수 상승률을 뺀 초과 성과</div>
            </div>
        </div>

        <!-- Charts grid -->
        <div class="charts-grid">
            
            <!-- Chart 1: Trajectory by Keyword -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">구조조정 보도 유형별 실제 주가 추이 (30일 ~ 1년)</div>
                    <select id="keywordSelect" class="chart-select" onchange="updateKeywordChart()">
                        <option value="all">모든 유형 비교</option>
                        <option value="구조조정">구조조정 단독</option>
                        <option value="희망퇴직">희망퇴직 단독</option>
                        <option value="구조조정,희망퇴직">구조조정 + 희망퇴직</option>
                        <option value="구조조정,인력감축,희망퇴직">고강도 복합 구조조정</option>
                    </select>
                </div>
                <div class="chart-container">
                    <canvas id="keywordChart"></canvas>
                </div>
            </div>

            <!-- Chart 2: Sector Comparison -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">주요 업종별 1년 후 주가 흐름 비교 (보도가 잦은 상위 업종)</div>
                </div>
                <div class="chart-container">
                    <canvas id="sectorChart"></canvas>
                </div>
            </div>

            <!-- Chart 3: Yearly Trends -->
            <div class="chart-card full-width">
                <div class="chart-header">
                    <div class="chart-title">연도별 구조조정 보도 빈도 및 1년 평균 성과 추이</div>
                </div>
                <div class="chart-container">
                    <canvas id="yearlyChart"></canvas>
                </div>
            </div>

        </div>

        <!-- Events Table card -->
        <div class="table-card">
            <div class="table-header-row">
                <div class="chart-title" style="margin-bottom: 0;">구조조정 뉴스 이벤트 상세 데이터 내역 <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-muted);">(행을 클릭하면 상세 계산 근거를 볼 수 있습니다)</span></div>
                <div class="search-container">
                    <input type="text" id="tableSearch" class="search-input" onkeyup="filterTable()" placeholder="회사명, 종목코드, 제목 검색...">
                </div>
            </div>
            <div class="table-container">
                <table id="eventsTable">
                    <thead>
                        <tr>
                            <th style="min-width: 120px;">회사명</th>
                            <th>종목코드</th>
                            <th>보도 날짜</th>
                            <th>시장</th>
                            <th>보도 키워드</th>
                            <th>30일 변화율</th>
                            <th>90일 변화율</th>
                            <th>180일 변화율</th>
                            <th>1년(365일) 변화율</th>
                            <th>1년 시장 대비 성과</th>
                            <th style="min-width: 250px;">대표 기사 제목</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">
                        <!-- JS injected -->
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <!-- Data Injection -->
    <script>
        const keywordData = {json.dumps(keyword_json, ensure_ascii=False)};
        const marketData = {json.dumps(market_json, ensure_ascii=False)};
        const yearData = {json.dumps(year_json, ensure_ascii=False)};
        const industryData = {json.dumps(industry_json, ensure_ascii=False)};
        const eventsData = {json.dumps(events_json, ensure_ascii=False)};

        // ----------------------------------------------------
        // Chart 1: Keyword Trajectory Chart
        // ----------------------------------------------------
        let keywordChart;
        function initKeywordChart() {{
            const ctx = document.getElementById('keywordChart').getContext('2d');
            const selectValue = document.getElementById('keywordSelect').value;
            let datasets = [];
            
            if (selectValue === 'all') {{
                const targets = ['구조조정', '희망퇴직', '구조조정,희망퇴직'];
                const colors = [
                    {{ ret: '#38bdf8', exc: '#6366f1' }}, // 구조조정
                    {{ ret: '#34d399', exc: '#10b981' }}, // 희망퇴직
                    {{ ret: '#f43f5e', exc: '#be123c' }}  // 구조조정,희망퇴직
                ];
                
                targets.forEach((t, i) => {{
                    const row = keywordData.find(r => r.키워드종류 === t);
                    if (row) {{
                        datasets.push({{
                            label: `${{t}} 실제주가 변화율`,
                            data: [row.return_30d_avg * 100, row.return_90d_avg * 100, row.return_180d_avg * 100, row.return_365d_avg * 100],
                            borderColor: colors[i].ret,
                            backgroundColor: colors[i].ret + '10',
                            borderWidth: 3,
                            tension: 0.25,
                            fill: false
                        }});
                        datasets.push({{
                            label: `${{t}} 시장 대비 성과`,
                            data: [row.excess_30d_avg * 100, row.excess_90d_avg * 100, row.excess_180d_avg * 100, row.excess_365d_avg * 100],
                            borderColor: colors[i].exc,
                            backgroundColor: colors[i].exc + '10',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            tension: 0.25,
                            fill: false
                        }});
                    }}
                }});
            }} else {{
                const row = keywordData.find(r => r.키워드종류 === selectValue);
                if (row) {{
                    datasets.push({{
                        label: '실제 주가 변화율',
                        data: [row.return_30d_avg * 100, row.return_90d_avg * 100, row.return_180d_avg * 100, row.return_365d_avg * 100],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 4,
                        tension: 0.25,
                        fill: true
                    }});
                    datasets.push({{
                        label: '시장 대비 초과 성과',
                        data: [row.excess_30d_avg * 100, row.excess_90d_avg * 100, row.excess_180d_avg * 100, row.excess_365d_avg * 100],
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56, 189, 248, 0.1)',
                        borderWidth: 4,
                        borderDash: [6, 4],
                        tension: 0.25,
                        fill: true
                    }});
                }}
            }}

            if (keywordChart) keywordChart.destroy();
            
            keywordChart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: ['보도 30일 뒤', '보도 90일 뒤', '보도 180일 뒤', '보도 1년 뒤(365일)'],
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'top',
                            labels: {{ color: '#e2e8f0', font: {{ family: 'Inter' }} }}
                        }},
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return context.dataset.label + ': ' + context.raw.toFixed(2) + '%';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            ticks: {{ color: '#94a3b8', callback: val => val.toFixed(0) + '%' }},
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }}
                        }},
                        x: {{
                            ticks: {{ color: '#94a3b8' }},
                            grid: {{ display: false }}
                        }}
                    }}
                }}
            }});
        }}

        function updateKeywordChart() {{
            initKeywordChart();
        }}

        // ----------------------------------------------------
        // Chart 2: Sector Comparison Chart
        // ----------------------------------------------------
        function initSectorChart() {{
            const ctx = document.getElementById('sectorChart').getContext('2d');
            const topSectors = industryData.slice(0, 8);
            const labels = topSectors.map(r => r.업종);
            const returnData = topSectors.map(r => r.return_365d_avg * 100);
            const excessData = topSectors.map(r => r.excess_365d_avg * 100);
            
            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: '1년 실제 주가 변화율',
                            data: returnData,
                            backgroundColor: 'rgba(56, 189, 248, 0.7)',
                            borderColor: '#38bdf8',
                            borderWidth: 1,
                            borderRadius: 6
                        }},
                        {{
                            label: '1년 시장 대비 성과',
                            data: excessData,
                            backgroundColor: 'rgba(99, 102, 241, 0.7)',
                            borderColor: '#6366f1',
                            borderWidth: 1,
                            borderRadius: 6
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'top',
                            labels: {{ color: '#e2e8f0' }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            ticks: {{ color: '#94a3b8', callback: val => val.toFixed(0) + '%' }},
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }}
                        }},
                        x: {{
                            ticks: {{ color: '#94a3b8', font: {{ size: 10 }} }},
                            grid: {{ display: false }}
                        }}
                    }}
                }}
            }});
        }}

        // ----------------------------------------------------
        // Chart 3: Yearly Trends Chart
        // ----------------------------------------------------
        function initYearlyChart() {{
            const ctx = document.getElementById('yearlyChart').getContext('2d');
            const cleanYearData = yearData.filter(r => !isNaN(r.이벤트연도));
            const labels = cleanYearData.map(r => r.이벤트연도);
            const eventCounts = cleanYearData.map(r => r.이벤트수);
            const returns = cleanYearData.map(r => r.return_365d_avg * 100);
            const excess = cleanYearData.map(r => r.excess_365d_avg * 100);
            
            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            type: 'bar',
                            label: '보도 건수',
                            data: eventCounts,
                            backgroundColor: 'rgba(255, 255, 255, 0.1)',
                            borderColor: 'rgba(255, 255, 255, 0.2)',
                            borderWidth: 1,
                            yAxisID: 'yEvent',
                            borderRadius: 4
                        }},
                        {{
                            type: 'line',
                            label: '평균 1년 실제주가 변화율',
                            data: returns,
                            borderColor: '#34d399',
                            borderWidth: 3,
                            tension: 0.2,
                            yAxisID: 'yRet',
                            fill: false
                        }},
                        {{
                            type: 'line',
                            label: '평균 1년 시장 대비 성과',
                            data: excess,
                            borderColor: '#ef4444',
                            borderWidth: 2,
                            borderDash: [4, 4],
                            tension: 0.2,
                            yAxisID: 'yRet',
                            fill: false
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'top',
                            labels: {{ color: '#e2e8f0' }}
                        }}
                    }},
                    scales: {{
                        yRet: {{
                            type: 'linear',
                            position: 'left',
                            ticks: {{ color: '#94a3b8', callback: val => val.toFixed(0) + '%' }},
                            grid: {{ color: 'rgba(255, 255, 255, 0.05)' }},
                            title: {{ display: true, text: '주가 변화율', color: '#94a3b8' }}
                        }},
                        yEvent: {{
                            type: 'linear',
                            position: 'right',
                            ticks: {{ color: '#94a3b8' }},
                            grid: {{ display: false }},
                            title: {{ display: true, text: '보도 건수', color: '#94a3b8' }}
                        }},
                        x: {{
                            ticks: {{ color: '#94a3b8' }},
                            grid: {{ display: false }}
                        }}
                    }}
                }}
            }});
        }}

        // ----------------------------------------------------
        // Interactive Data Table with Collapsible Evidence Panel
        // ----------------------------------------------------
        function renderTable(data) {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            
            data.forEach((row, index) => {{
                const tr = document.createElement('tr');
                tr.className = 'clickable-row';
                tr.onclick = () => toggleDetails(index);
                
                const fmtPct = val => {{
                    if (val === null || val === undefined) return '<span class="ret-value neutral">N/A</span>';
                    const num = val * 100;
                    const sign = num > 0 ? '+' : '';
                    const cls = num > 0 ? 'positive' : (num < 0 ? 'negative' : 'neutral');
                    return `<span class="ret-value ${{cls}}">${{sign}}${{num.toFixed(2)}}%</span>`;
                }};
                
                tr.innerHTML = `
                    <td style="font-weight: 600; color: #fff;">${{row.회사명}}</td>
                    <td style="color: var(--text-muted); font-family: 'Outfit';">${{row.종목코드}}</td>
                    <td>${{row.이벤트시작일}}</td>
                    <td><span class="badge market">${{row.시장}}</span></td>
                    <td><span class="badge keyword">${{row.키워드종류}}</span></td>
                    <td>${{fmtPct(row.return_30d)}}</td>
                    <td>${{fmtPct(row.return_90d)}}</td>
                    <td>${{fmtPct(row.return_180d)}}</td>
                    <td>${{fmtPct(row.return_365d)}}</td>
                    <td>${{fmtPct(row.excess_365d)}}</td>
                    <td style="color: var(--text-muted); max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${{row.대표제목}}">${{row.대표제목}}</td>
                `;
                tbody.appendChild(tr);
                
                // Add Collapsible Details Row
                const detailsTr = document.createElement('tr');
                detailsTr.className = 'details-row';
                detailsTr.id = `details-row-${{index}}`;
                detailsTr.style.display = 'none';
                
                const formatVal = (val, suffix = '', defaultVal = '자료 없음') => {{
                    return (val !== null && val !== undefined) ? `${{val.toLocaleString(undefined, {{maximumFractionDigits: 2}})}}${{suffix}}` : defaultVal;
                }};
                
                const formatPctWithColor = (val) => {{
                    if (val === null || val === undefined) return '자료 없음';
                    const num = val * 100;
                    const sign = num > 0 ? '+' : '';
                    const cls = num > 0 ? 'var(--success)' : (num < 0 ? 'var(--danger)' : 'var(--text-muted)');
                    return `<span style="color: ${{cls}}; font-weight: 600;">${{sign}}${{num.toFixed(2)}}%</span>`;
                }};
                
                // Calculate index values at target date for display
                const calcIndexPrice = (baseIdx, ret) => {{
                    if (baseIdx === null || ret === null) return null;
                    return baseIdx * (1 + ret);
                }};
                
                detailsTr.innerHTML = `
                    <td colspan="11">
                        <div class="evidence-box">
                            <h4>📊 <strong>${{row.회사명}} (${{row.종목코드}})</strong> 구조조정 주가 계산 근거 상세 내역</h4>
                            <div class="evidence-grid">
                                <div class="evidence-step">
                                    <strong>1단계: 주가 판단 기준점 설정</strong>
                                    <ul>
                                        <li>소속 시장: <strong>${{row.시장}}</strong></li>
                                        <li>보도 전 60일 평균 주가 (기준 가격): <strong>${{formatVal(row.baseline_stock, ' 원')}}</strong></li>
                                        <li>보도 전 60일 평균 시장 지수 (기준 지수): <strong>${{formatVal(row.baseline_index, ' 포인트')}}</strong></li>
                                    </ul>
                                </div>
                                <div class="evidence-step">
                                    <strong>2단계: 시점별 실제 주가와 시장 흐름 계산식</strong>
                                    <table class="evidence-table">
                                        <thead>
                                            <tr>
                                                <th>구분</th>
                                                <th>종가 (A)</th>
                                                <th>실제 주가 변화 (A 대비)</th>
                                                <th>시장 지수 (B)</th>
                                                <th>시장 지수 변화 (B 대비)</th>
                                                <th>시장 대비 성과 (A - B)</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td>보도 30일 뒤</td>
                                                <td>${{formatVal(row.price_30d, ' 원')}}</td>
                                                <td>${{formatPctWithColor(row.return_30d)}}</td>
                                                <td>${{formatVal(calcIndexPrice(row.baseline_index, row.idx_return_30d), ' P')}}</td>
                                                <td>${{formatPctWithColor(row.idx_return_30d)}}</td>
                                                <td>${{formatPctWithColor(row.excess_30d)}}</td>
                                            </tr>
                                            <tr>
                                                <td>보도 90일 뒤</td>
                                                <td>${{formatVal(row.price_90d, ' 원')}}</td>
                                                <td>${{formatPctWithColor(row.return_90d)}}</td>
                                                <td>${{formatVal(calcIndexPrice(row.baseline_index, row.idx_return_90d), ' P')}}</td>
                                                <td>${{formatPctWithColor(row.idx_return_90d)}}</td>
                                                <td>${{formatPctWithColor(row.excess_90d)}}</td>
                                            </tr>
                                            <tr>
                                                <td>보도 180일 뒤</td>
                                                <td>${{formatVal(row.price_180d, ' 원')}}</td>
                                                <td>${{formatPctWithColor(row.return_180d)}}</td>
                                                <td>${{formatVal(calcIndexPrice(row.baseline_index, row.idx_return_180d), ' P')}}</td>
                                                <td>${{formatPctWithColor(row.idx_return_180d)}}</td>
                                                <td>${{formatPctWithColor(row.excess_180d)}}</td>
                                            </tr>
                                            <tr>
                                                <td>보도 1년 뒤 (365일)</td>
                                                <td>${{formatVal(row.price_365d, ' 원')}}</td>
                                                <td>${{formatPctWithColor(row.return_365d)}}</td>
                                                <td>${{formatVal(calcIndexPrice(row.baseline_index, row.idx_return_365d), ' P')}}</td>
                                                <td>${{formatPctWithColor(row.idx_return_365d)}}</td>
                                                <td>${{formatPctWithColor(row.excess_365d)}}</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            
                            ${{row.상장폐지일 ? `
                            <div class="delist-alert ${{row.is_bankrupt_delist ? '' : 'info'}}">
                                ⚠️ 이 회사는 <strong>${{row.상장폐지일}}</strong>에 <strong>'${{row.상장폐지사유 || '사유 미확인'}}'</strong> 사유로 상장폐지되었습니다.<br>
                                ➡️ ${{row.is_bankrupt_delist ? 
                                    '<strong>[부도성 퇴출 처리]</strong> 기업이 청산 또는 부도되어 퇴출되었으므로, 상장폐지일 이후 시점의 실제 주가는 <strong>0원(-100% 자산 손실)</strong>으로 회복률 계산에 엄격하게 반영되었습니다.' : 
                                    '<strong>[경영 목적 퇴출 처리]</strong> 지주사 지분 스왑 또는 합병 등으로 인한 자진 상장폐지이므로, 상장폐지일 이후 시점은 가격 추적을 중단(자료 없음)했습니다.'}}
                            </div>
                            ` : ''}}
                        </div>
                    </td>
                `;
                tbody.appendChild(detailsTr);
            }});
        }}

        function toggleDetails(index) {{
            const detailsRow = document.getElementById(`details-row-${{index}}`);
            if (detailsRow.style.display === 'none') {{
                detailsRow.style.display = 'table-row';
            }} else {{
                detailsRow.style.display = 'none';
            }}
        }}

        function filterTable() {{
            const q = document.getElementById('tableSearch').value.toLowerCase();
            const filtered = eventsData.filter(row => {{
                return (
                    row.회사명.toLowerCase().includes(q) ||
                    row.종목코드.includes(q) ||
                    (row.대표제목 && row.대표제목.toLowerCase().includes(q))
                );
            }});
            renderTable(filtered);
        }}

        // ----------------------------------------------------
        // Initialization
        // ----------------------------------------------------
        window.onload = function() {{
            initKeywordChart();
            initSectorChart();
            initYearlyChart();
            renderTable(eventsData);
        }};
    </script>
</body>
</html>
"""
    # 3. Write HTML file
    OUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"Generated Re-designed HTML Dashboard -> {OUT_HTML}")

if __name__ == "__main__":
    main()
