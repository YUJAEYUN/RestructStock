"""
주가 회복률 결과를 분석하고 요약 리포트를 생성한다.

입력:
  data/processed/recovery_results.csv
  data/processed/company_listing_matches.csv
출력:
  data/analysis/summary_report.md
  data/analysis/by_keyword.csv
  data/analysis/by_market.csv
  data/analysis/by_year.csv
  data/analysis/by_industry.csv
"""
from pathlib import Path
import pandas as pd
import numpy as np

RESULTS_IN = Path("data/processed/recovery_results.csv")
MATCHES_IN = Path("data/processed/company_listing_matches.csv")
OUT_DIR = Path("data/analysis")

def to_markdown_table(df):
    headers = list(df.columns)
    index_name = df.index.name if df.index.name else ""
    header_line = "| " + index_name + " | " + " | ".join(headers) + " |"
    sep_line = "| " + "--- | " * (len(headers) + 1)
    
    lines = [header_line, sep_line]
    for idx, row in df.iterrows():
        row_str = "| " + str(idx) + " | " + " | ".join(str(val) for val in row) + " |"
        lines.append(row_str)
    return "\n".join(lines)

def df_to_md_formatted(summary_df):
    fmt_df = summary_df.copy()
    for col in fmt_df.columns:
        if col == "이벤트수":
            fmt_df[col] = fmt_df[col].map("{:,}".format)
        elif col == "평균기사수":
            fmt_df[col] = fmt_df[col].map("{:.1f}".format)
        elif "avg" in col or "return" in col or "excess" in col:
            # Handle NaNs gracefully
            fmt_df[col] = fmt_df[col].map(lambda x: f"{x*100:+.2f}%" if not pd.isna(x) else "N/A")
    return to_markdown_table(fmt_df)

def main():
    if not RESULTS_IN.exists():
        print(f"Input file {RESULTS_IN} does not exist.")
        return
        
    df = pd.read_csv(RESULTS_IN)
    matches = pd.read_csv(MATCHES_IN, dtype={"종목코드": str})
    
    # Clean matches code format
    matches["종목코드"] = matches["종목코드"].str.split(".").str[0].str.zfill(6)
    
    # Merge results with industry sector from matches
    df = df.merge(matches[["회사명", "업종"]], on="회사명", how="left")
    
    df["이벤트연도"] = pd.to_datetime(df["이벤트시작일"]).dt.year
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Helper to calculate summary metrics
    def summarize_group(grouped):
        summary = grouped.agg(
            이벤트수=("회사명", "count"),
            평균기사수=("기사수", "mean"),
            return_30d_avg=("return_30d", "mean"),
            excess_30d_avg=("excess_30d", "mean"),
            return_90d_avg=("return_90d", "mean"),
            excess_90d_avg=("excess_90d", "mean"),
            return_180d_avg=("return_180d", "mean"),
            excess_180d_avg=("excess_180d", "mean"),
            return_365d_avg=("return_365d", "mean"),
            excess_365d_avg=("excess_365d", "mean"),
            min_return_1y_avg=("min_return_1y", "mean"),
            max_return_1y_avg=("max_return_1y", "mean"),
            min_excess_1y_avg=("min_excess_1y", "mean"),
            max_excess_1y_avg=("max_excess_1y", "mean"),
        )
        return summary
        
    # 1. By Keyword
    by_keyword = summarize_group(df.groupby("키워드종류")).sort_values("이벤트수", ascending=False)
    by_keyword.to_csv(OUT_DIR / "by_keyword.csv", encoding="utf-8-sig")
    
    # 2. By Market
    by_market = summarize_group(df.groupby("시장")).sort_values("이벤트수", ascending=False)
    by_market.to_csv(OUT_DIR / "by_market.csv", encoding="utf-8-sig")
    
    # 3. By Year
    by_year = summarize_group(df.groupby("이벤트연도")).sort_index()
    by_year.to_csv(OUT_DIR / "by_year.csv", encoding="utf-8-sig")
    
    # 4. By Industry (top 20)
    by_industry = summarize_group(df.groupby("업종"))
    by_industry = by_industry.sort_values("이벤트수", ascending=False).head(20)
    by_industry.to_csv(OUT_DIR / "by_industry.csv", encoding="utf-8-sig")
    
    # Generate Markdown Report
    report_path = OUT_DIR / "summary_report.md"
    
    total_events = len(df)
    unique_companies = df["회사명"].nunique()
    bankrupt_delistings = df["is_bankrupt_delist"].sum()
    
    report_content = f"""# 구조조정 보도 기업 주가 회복률 분석 리포트

구조조정(구조조정/희망퇴직/인력감축) 뉴스가 보도된 기업들의 사후 주가 흐름과 시장 대비 초과수익률(BM 대비)을 분석한 보고서입니다.

## 1. 전체 요약
- **분석 대상 이벤트 수**: {total_events:,}건 (2010년 ~ 2026년)
- **분석 대상 기업 수**: {unique_companies:,}개사
- **이벤트 후 1년 내 부도/잠식에 따른 상장폐지**: {bankrupt_delistings:,}건

## 2. 키워드별 분석
키워드 종류에 따른 주가 회복률 및 시장 지수 대비 초과 수익률 평균입니다.

{df_to_md_formatted(by_keyword)}

## 3. 시장별 분석
코스피(KOSPI)와 코스닥(KOSDAQ) 시장에 따른 회복률 비교입니다.

{df_to_md_formatted(by_market)}

## 4. 연도별 추이
연도별 구조조정 보도 이벤트 건수와 주가 회복률 추이입니다.

{df_to_md_formatted(by_year)}

## 5. 주요 업종별 분석 (이벤트수 상위 20개 업종)
구조조정 보도가 가장 잦았던 상위 20개 업종의 회복률 분석 결과입니다.

{df_to_md_formatted(by_industry)}

---
*주의: 회복률은 이벤트 시작 전 60거래일 평균 종가 대비 해당 시점 종가의 변동률입니다. 초과수익률은 개별 종목 수익률에서 해당 시장 지수(KOSPI/KOSDAQ) 수익률을 차감한 수치입니다.*
"""
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"Analysis complete. Generated report -> {report_path}")

if __name__ == "__main__":
    main()
