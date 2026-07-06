"""
FinanceDataReader로 국내 상장/상장폐지 기준 데이터를 내려받는다.

출력:
  data/reference/listed_companies.csv
  data/reference/delisted_companies.csv

현재 실행 환경에서 pykrx의 티커 목록 API가 빈 값을 반환하는 문제가 있어,
상장사/상장폐지 마스터는 FinanceDataReader를 기본 provider로 사용한다.
"""
from pathlib import Path

import FinanceDataReader as fdr
import pandas as pd

OUT_DIR = Path("data/reference")
LISTED_OUT = OUT_DIR / "listed_companies.csv"
DELISTED_OUT = OUT_DIR / "delisted_companies.csv"


def fetch_listed() -> pd.DataFrame:
    df = fdr.StockListing("KRX")
    keep = [
        "Code",
        "ISU_CD",
        "Name",
        "Market",
        "Dept",
        "MarketId",
        "Close",
        "Marcap",
        "Stocks",
    ]
    cols = [c for c in keep if c in df.columns]
    out = df[cols].copy()
    out["source"] = "FinanceDataReader.StockListing(KRX)"
    return out.sort_values(["Market", "Name", "Code"]).reset_index(drop=True)


def fetch_delisted() -> pd.DataFrame:
    df = fdr.StockListing("KRX-DELISTING")
    keep = [
        "Symbol",
        "Name",
        "Market",
        "SecuGroup",
        "ListingDate",
        "DelistingDate",
        "Reason",
        "Industry",
        "ToSymbol",
        "ToName",
    ]
    cols = [c for c in keep if c in df.columns]
    out = df[cols].copy()
    out = out.rename(columns={"Symbol": "Code"})
    out["source"] = "FinanceDataReader.StockListing(KRX-DELISTING)"
    return out.sort_values(["Market", "Name", "Code"]).reset_index(drop=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    listed = fetch_listed()
    delisted = fetch_delisted()

    listed.to_csv(LISTED_OUT, index=False, encoding="utf-8-sig")
    delisted.to_csv(DELISTED_OUT, index=False, encoding="utf-8-sig")

    print(f"listed: {len(listed):,} rows -> {LISTED_OUT}")
    print(f"delisted: {len(delisted):,} rows -> {DELISTED_OUT}")
    print("listed markets")
    print(listed["Market"].value_counts(dropna=False).to_string())
    print("delisted markets")
    print(delisted["Market"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
