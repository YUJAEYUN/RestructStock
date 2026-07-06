"""
이벤트별 주가 회복률 및 지수 대비 초과수익률을 계산한다.

입력:
  data/processed/events_with_listings.csv
  data/prices/stocks/{code}.csv
  data/prices/indices/KS11.csv
  data/prices/indices/KQ11.csv
출력:
  data/processed/recovery_results.csv
"""
from pathlib import Path
import pandas as pd
import numpy as np

EVENTS_IN = Path("data/processed/events_with_listings.csv")
STOCK_DIR = Path("data/prices/stocks")
INDEX_DIR = Path("data/prices/indices")
OUT_CSV = Path("data/processed/recovery_results.csv")

# 지수 파일 매핑
INDEX_FILES = {
    "KOSPI": INDEX_DIR / "KS11.csv",
    "KOSDAQ": INDEX_DIR / "KQ11.csv",
    "KOSDAQ GLOBAL": INDEX_DIR / "KQ11.csv"
}

def is_bankruptcy_delist(reason: str) -> bool:
    if pd.isna(reason):
        return False
    reason = str(reason)
    bankruptcy_keywords = [
        "자본전액잠식", "의견거절", "부도", "해산", "상장폐지기준에 해당", 
        "자본잠식", "공시서류 미제출"
    ]
    return any(kw in reason for kw in bankruptcy_keywords)

def calculate_rates_for_event(row, index_prices_cache):
    code = row["종목코드"]
    if pd.isna(code):
        return None
    code = str(code).split(".")[0].zfill(6) # ensure 6-digit format and string
    event_date_str = row["이벤트시작일"]
    event_date = pd.to_datetime(event_date_str)
    
    stock_file = STOCK_DIR / f"{code}.csv"
    if not stock_file.exists():
        return None
    
    # Load stock prices
    try:
        stock_df = pd.read_csv(stock_file)
        if stock_df.empty:
            return None
        stock_df["Date"] = pd.to_datetime(stock_df["Date"])
        stock_df = stock_df.sort_values("Date").reset_index(drop=True)
    except Exception:
        return None
        
    # Load index prices
    market = row["시장"]
    index_file = INDEX_FILES.get(market)
    if not index_file or not index_file.exists():
        return None
        
    if market not in index_prices_cache:
        try:
            idx_df = pd.read_csv(index_file)
            idx_df["Date"] = pd.to_datetime(idx_df["Date"])
            idx_df = idx_df.sort_values("Date").reset_index(drop=True)
            index_prices_cache[market] = idx_df
        except Exception:
            return None
    idx_df = index_prices_cache[market]
    
    # 1. Baseline Price (60 trading days before event_date)
    stock_before = stock_df[stock_df["Date"] < event_date]
    if len(stock_before) < 5: # Require at least 5 trading days
        return None
    baseline_stock = stock_before.tail(60)["Close"].mean()
    
    idx_before = idx_df[idx_df["Date"] < event_date]
    if len(idx_before) < 5:
        return None
    baseline_index = idx_before.tail(60)["Close"].mean()
    
    # Check if stock is delisted and determine bankruptcy status
    delisting_date = pd.to_datetime(row["상장폐지일"]) if not pd.isna(row["상장폐지일"]) else None
    is_bankrupt = is_bankruptcy_delist(row["상장폐지사유"])
    
    results = {
        "baseline_stock": baseline_stock,
        "baseline_index": baseline_index,
        "상장폐지일": row["상장폐지일"],
        "상장폐지사유": row["상장폐지사유"],
        "is_bankrupt_delist": is_bankrupt
    }
    
    # Horizons in calendar days
    horizons = [30, 60, 90, 180, 365]
    
    for h in horizons:
        target_date = event_date + pd.Timedelta(days=h)
        
        # Check if target date is after delisting date
        if delisting_date and target_date >= delisting_date:
            if is_bankrupt:
                # Bankruptcy: price goes to 0 (recovery rate is -1.0)
                stock_price = 0.0
                idx_row = idx_df[idx_df["Date"] >= target_date].head(1)
                if idx_row.empty:
                    idx_row = idx_df.tail(1)
                index_price = idx_row["Close"].values[0]
                
                stock_ret = -1.0
                index_ret = (index_price / baseline_index) - 1.0
                excess_ret = stock_ret - index_ret
            else:
                # Normal merger/delist: stop tracking (NaN)
                stock_price = np.nan
                stock_ret = np.nan
                index_ret = np.nan
                excess_ret = np.nan
        else:
            # Find closest trading day at or after target_date
            stock_after = stock_df[stock_df["Date"] >= target_date].head(1)
            idx_after = idx_df[idx_df["Date"] >= target_date].head(1)
            
            if stock_after.empty or idx_after.empty:
                stock_price = np.nan
                stock_ret = np.nan
                index_ret = np.nan
                excess_ret = np.nan
            else:
                stock_price = stock_after["Close"].values[0]
                index_price = idx_after["Close"].values[0]
                
                stock_ret = (stock_price / baseline_stock) - 1.0
                index_ret = (index_price / baseline_index) - 1.0
                excess_ret = stock_ret - index_ret
                
        results[f"price_{h}d"] = stock_price
        results[f"return_{h}d"] = stock_ret
        results[f"idx_return_{h}d"] = index_ret
        results[f"excess_{h}d"] = excess_ret
        
    # Calculate post-event min/max within 365 days
    end_date_1y = event_date + pd.Timedelta(days=365)
    stock_1y = stock_df[(stock_df["Date"] >= event_date) & (stock_df["Date"] <= end_date_1y)]
    
    if not stock_1y.empty:
        min_idx = stock_1y["Close"].idxmin()
        max_idx = stock_1y["Close"].idxmax()
        
        min_row = stock_1y.loc[min_idx]
        max_row = stock_1y.loc[max_idx]
        
        min_price = min_row["Close"]
        max_price = max_row["Close"]
        
        min_days = (min_row["Date"] - event_date).days
        max_days = (max_row["Date"] - event_date).days
        
        idx_min = idx_df[idx_df["Date"] >= min_row["Date"]].head(1)
        idx_max = idx_df[idx_df["Date"] >= max_row["Date"]].head(1)
        
        idx_min_close = idx_min["Close"].values[0] if not idx_min.empty else baseline_index
        idx_max_close = idx_max["Close"].values[0] if not idx_max.empty else baseline_index
        
        min_ret = (min_price / baseline_stock) - 1.0
        max_ret = (max_price / baseline_stock) - 1.0
        
        idx_min_ret = (idx_min_close / baseline_index) - 1.0
        idx_max_ret = (idx_max_close / baseline_index) - 1.0
        
        # If bankrupt delisting happened within 365 days, min price is 0
        if delisting_date and delisting_date <= end_date_1y and is_bankrupt:
            min_price = 0.0
            min_ret = -1.0
            idx_min_ret = (idx_df[idx_df["Date"] >= delisting_date].head(1)["Close"].values[0] / baseline_index) - 1.0
            min_days = (delisting_date - event_date).days
            
        results["min_price_1y"] = min_price
        results["min_return_1y"] = min_ret
        results["min_days_1y"] = min_days
        results["min_excess_1y"] = min_ret - idx_min_ret
        
        results["max_price_1y"] = max_price
        results["max_return_1y"] = max_ret
        results["max_days_1y"] = max_days
        results["max_excess_1y"] = max_ret - idx_max_ret
    else:
        if delisting_date and is_bankrupt:
            results["min_price_1y"] = 0.0
            results["min_return_1y"] = -1.0
            results["min_days_1y"] = 0
            results["min_excess_1y"] = -1.0
            
            results["max_price_1y"] = baseline_stock
            results["max_return_1y"] = 0.0
            results["max_days_1y"] = 0
            results["max_excess_1y"] = 0.0
        else:
            results["min_price_1y"] = np.nan
            results["min_return_1y"] = np.nan
            results["min_days_1y"] = np.nan
            results["min_excess_1y"] = np.nan
            
            results["max_price_1y"] = np.nan
            results["max_return_1y"] = np.nan
            results["max_days_1y"] = np.nan
            results["max_excess_1y"] = np.nan
            
    return results

def main():
    events = pd.read_csv(EVENTS_IN)
    eligible = events[events["match_status"].isin({"current_exact", "delisted_exact"})].copy()
    
    print(f"Calculating recovery rates for {len(eligible):,} events...")
    
    index_prices_cache = {}
    rows = []
    
    for idx, row in eligible.iterrows():
        res = calculate_rates_for_event(row, index_prices_cache)
        if res is not None:
            full_row = {
                "회사명": row["회사명"],
                "종목코드": str(row["종목코드"]).split(".")[0].zfill(6),
                "이벤트시작일": row["이벤트시작일"],
                "시장": row["시장"],
                "match_status": row["match_status"],
                "기사수": row["기사수"],
                "키워드종류": row["키워드종류"],
                "대표제목": row["대표제목"],
                **res
            }
            rows.append(full_row)
            
    out_df = pd.DataFrame(rows)
    if out_df.empty:
        print("No results calculated.")
        return
        
    cols = ["회사명", "종목코드", "이벤트시작일", "시장", "match_status", "기사수", "키워드종류", "대표제목",
            "baseline_stock", "baseline_index", 
            "price_30d", "return_30d", "excess_30d",
            "price_60d", "return_60d", "excess_60d",
            "price_90d", "return_90d", "excess_90d",
            "price_180d", "return_180d", "excess_180d",
            "price_365d", "return_365d", "excess_365d",
            "min_price_1y", "min_return_1y", "min_days_1y", "min_excess_1y",
            "max_price_1y", "max_return_1y", "max_days_1y", "max_excess_1y",
            "상장폐지일", "상장폐지사유", "is_bankrupt_delist"]
    
    cols = [c for c in cols if c in out_df.columns]
    out_df = out_df[cols]
    
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"Calculation complete. Saved {len(out_df):,} rows -> {OUT_CSV}")

if __name__ == "__main__":
    main()
