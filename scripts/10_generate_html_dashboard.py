"""
구조조정 보도 기업 주가 회복률 분석 결과를 시각화하는 인터랙티브 HTML 대시보드를 생성한다.

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
    
    # Take a summary subset of the events table to keep HTML file size reasonable
    # Sort by event date descending
    df_sorted = df.sort_values("이벤트시작일", ascending=False)
    # Selected columns for interactive table
    table_cols = ["회사명", "종목코드", "이벤트시작일", "시장", "기사수", "키워드종류", "대표제목",
                  "return_30d", "excess_30d", "return_90d", "excess_90d", 
                  "return_180d", "excess_180d", "return_365d", "excess_365d"]
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
            content: '📉';
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
            max-height: 500px;
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

        tr:last-child td {{
            border-bottom: none;
        }}

        tr {{
            transition: background-color 0.2s ease;
        }}

        tr:hover {{
            background-color: rgba(255, 255, 255, 0.02);
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
            <div class="subtitle">구조조정 보도 기업 주가 회복률 & 시장 초과수익률 분석 대시보드</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 0.8rem; color: var(--text-muted);">최종 업데이트</div>
            <div style="font-size: 0.9rem; font-weight: 500;">2026년 7월 7일</div>
        </div>
    </header>

    <div class="main-container">

        <!-- Metrics cards row -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">총 분석 이벤트</div>
                <div class="metric-value">{total_events:,} 건</div>
                <div class="metric-subtext">2010.01 ~ 2026.07 뉴스 통합</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">분석 대상 상장사</div>
                <div class="metric-value">{unique_companies:,} 개사</div>
                <div class="metric-subtext">현재 상장 및 상장폐지사 통합</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">부도/자본잠식 상장폐지</div>
                <div class="metric-value danger">{bankruptcies} 개사</div>
                <div class="metric-subtext">이벤트 발생 후 1년 내 청산/부도</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">평균 1년 절대 회복률</div>
                <div class="metric-value success">+{avg_365d_ret * 100:.2f}%</div>
                <div class="metric-subtext">보도 전 60일 평균가 대비 절대 변동</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">평균 1년 지수 초과수익률</div>
                <div class="metric-value danger">{avg_365d_exc * 100:.2f}%</div>
                <div class="metric-subtext">개별수익률 - 지수(KOSPI/KOSDAQ)수익률</div>
            </div>
        </div>

        <!-- Charts grid -->
        <div class="charts-grid">
            
            <!-- Chart 1: Trajectory by Keyword -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">구조조정 보도 유형별 주가 추이 (30d ~ 365d)</div>
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
                    <div class="chart-title">주요 업종별 1년 후 수익률 비교 (이벤트 상위 업종)</div>
                </div>
                <div class="chart-container">
                    <canvas id="sectorChart"></canvas>
                </div>
            </div>

            <!-- Chart 3: Yearly Trends -->
            <div class="chart-card full-width">
                <div class="chart-header">
                    <div class="chart-title">연도별 구조조정 보도 건수 및 1년 평균 수익률 추이</div>
                </div>
                <div class="chart-container">
                    <canvas id="yearlyChart"></canvas>
                </div>
            </div>

        </div>

        <!-- Events Table card -->
        <div class="table-card">
            <div class="table-header-row">
                <div class="chart-title" style="margin-bottom: 0;">구조조정 뉴스 이벤트 상세 데이터 내역</div>
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
                            <th>이벤트 날짜</th>
                            <th>시장</th>
                            <th>키워드</th>
                            <th>30일 회복률</th>
                            <th>90일 회복률</th>
                            <th>180일 회복률</th>
                            <th>365일 회복률</th>
                            <th>365일 초과수익률</th>
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
            
            // Prepare default datasets (All comparison)
            const periods = ['30d', '90d', '180d', '365d'];
            const selectValue = document.getElementById('keywordSelect').value;
            
            let datasets = [];
            
            if (selectValue === 'all') {{
                // Plot 3 major groups
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
                            label: `${{t}} 절대수익률`,
                            data: [row.return_30d_avg * 100, row.return_90d_avg * 100, row.return_180d_avg * 100, row.return_365d_avg * 100],
                            borderColor: colors[i].ret,
                            backgroundColor: colors[i].ret + '10',
                            borderWidth: 3,
                            tension: 0.25,
                            fill: false
                        }});
                        datasets.push({{
                            label: `${{t}} 초과수익률`,
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
                // Plot single selected group showing Absolute vs Excess
                const row = keywordData.find(r => r.키워드종류 === selectValue);
                if (row) {{
                    datasets.push({{
                        label: '절대 회복률',
                        data: [row.return_30d_avg * 100, row.return_90d_avg * 100, row.return_180d_avg * 100, row.return_365d_avg * 100],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 4,
                        tension: 0.25,
                        fill: true
                    }});
                    datasets.push({{
                        label: '시장 대비 초과수익률 (BM 대비)',
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
                    labels: ['이벤트 후 30일', '이벤트 후 90일', '이벤트 후 180일', '이벤트 후 1년(365일)'],
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
            
            // Take top 8 industries by event count
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
                            label: '1년 절대 회복률',
                            data: returnData,
                            backgroundColor: 'rgba(56, 189, 248, 0.7)',
                            borderColor: '#38bdf8',
                            borderWidth: 1,
                            borderRadius: 6
                        }},
                        {{
                            label: '1년 초과수익률',
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
            
            // Clean up years (remove any NaN year values if they exist)
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
                            label: '이벤트 건수',
                            data: eventCounts,
                            backgroundColor: 'rgba(255, 255, 255, 0.1)',
                            borderColor: 'rgba(255, 255, 255, 0.2)',
                            borderWidth: 1,
                            yAxisID: 'yEvent',
                            borderRadius: 4
                        }},
                        {{
                            type: 'line',
                            label: '평균 1년 절대수익률',
                            data: returns,
                            borderColor: '#34d399',
                            borderWidth: 3,
                            tension: 0.2,
                            yAxisID: 'yRet',
                            fill: false
                        }},
                        {{
                            type: 'line',
                            label: '평균 1년 초과수익률',
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
                            title: {{ display: true, text: '수익률', color: '#94a3b8' }}
                        }},
                        yEvent: {{
                            type: 'linear',
                            position: 'right',
                            ticks: {{ color: '#94a3b8' }},
                            grid: {{ display: false }},
                            title: {{ display: true, text: '이벤트 건수', color: '#94a3b8' }}
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
        // Interactive Data Table
        // ----------------------------------------------------
        function renderTable(data) {{
            const tbody = document.getElementById('tableBody');
            tbody.innerHTML = '';
            
            data.forEach(row => {{
                const tr = document.createElement('tr');
                
                // Helper to format values
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
            }});
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
    print(f"Generated HTML Dashboard -> {OUT_HTML}")

if __name__ == "__main__":
    main()
