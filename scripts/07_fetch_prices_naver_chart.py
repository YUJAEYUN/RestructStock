"""
네이버 차트 XML 엔드포인트로 장기 일별 종목 가격을 수집한다.

FinanceDataReader/pykrx는 현재 종목별 3,000행 제한 때문에 2014-04-11 이전
가격을 가져오지 못한다. 네이버 차트 엔드포인트는 count 파라미터로 더 긴
일별 시계열을 받을 수 있어, 2010년 이벤트 분석용 보강 provider로 사용한다.

출력:
  data/prices_naver/stocks/{code}.csv
"""
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests

EVENTS_IN = Path("data/processed/events_with_listings.csv")
OUT_DIR = Path("data/prices_naver/stocks")
VALID_STATUSES = {"current_exact"}
VALID_MARKETS = {"KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"}

COUNT = 6000
URL = "https://fchart.stock.naver.com/sise.nhn"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://finance.naver.com/",
}


def fetch_chart(code: str) -> pd.DataFrame:
    params = {
        "symbol": code,
        "timeframe": "day",
        "count": COUNT,
        "requestType": 0,
    }
    resp = requests.get(URL, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    rows = []
    for item in root.findall(".//item"):
        data = item.attrib.get("data", "")
        parts = data.split("|")
        if len(parts) < 6 or not re.match(r"^\d{8}$", parts[0]):
            continue
        rows.append(
            {
                "Date": pd.to_datetime(parts[0], format="%Y%m%d"),
                "Open": int(parts[1]),
                "High": int(parts[2]),
                "Low": int(parts[3]),
                "Close": int(parts[4]),
                "Volume": int(parts[5]),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    df["Change"] = df["Close"].pct_change()
    return df


def main() -> None:
    events = pd.read_csv(EVENTS_IN, dtype={"종목코드": str})
    eligible = events[events["match_status"].isin(VALID_STATUSES)].copy()
    eligible = eligible[eligible["시장"].isin(VALID_MARKETS)]
    codes = sorted(eligible["종목코드"].dropna().unique())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    print(f"eligible events: {len(eligible):,}")
    print(f"codes: {len(codes):,}")

    for i, code in enumerate(codes, start=1):
        out_path = OUT_DIR / f"{code}.csv"
        try:
            df = fetch_chart(code)
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            if df.empty:
                print(f"[{i}/{len(codes)}] {code}: 0 rows")
            else:
                print(
                    f"[{i}/{len(codes)}] {code}: {len(df):,} rows "
                    f"{df['Date'].min().date()} ~ {df['Date'].max().date()}"
                )
        except Exception as exc:
            failures.append({"종목코드": code, "error": repr(exc)})
            print(f"[{i}/{len(codes)}] {code}: FAILED {exc!r}")
        time.sleep(0.15)

    if failures:
        fail_path = OUT_DIR.parent / "fetch_failures.csv"
        pd.DataFrame(failures).to_csv(fail_path, index=False, encoding="utf-8-sig")
        print(f"failures: {len(failures):,} -> {fail_path}")


if __name__ == "__main__":
    main()
