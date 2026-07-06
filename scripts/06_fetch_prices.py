"""
매칭된 이벤트에 필요한 종목/지수 일별 데이터를 FinanceDataReader로 수집한다.

기본 범위:
  이벤트 시작일 - 90일 ~ 이벤트 시작일 + 370일

출력:
  data/prices/stocks/{code}.csv
  data/prices/indices/KS11.csv
  data/prices/indices/KQ11.csv

주의:
  수집 시간이 오래 걸릴 수 있어, 기본값은 자동 매칭된 현재 상장사만 대상으로 한다.
  상장폐지 종목 가격은 provider에서 과거 데이터를 못 주는 경우가 있어 별도 검증이 필요하다.
"""
from pathlib import Path
import time

import FinanceDataReader as fdr
import pandas as pd

EVENTS_IN = Path("data/processed/events_with_listings.csv")
STOCK_OUT_DIR = Path("data/prices/stocks")
INDEX_OUT_DIR = Path("data/prices/indices")
VALID_STATUSES = {"current_exact"}
INDEX_CODES = {"KOSPI": "KS11", "KOSDAQ": "KQ11", "KOSDAQ GLOBAL": "KQ11"}


def fetch_reader(code: str, start: str, end: str) -> pd.DataFrame:
    df = fdr.DataReader(code, start, end)
    out = df.reset_index()
    out.columns = [str(c) for c in out.columns]
    return out


def date_window(events: pd.DataFrame) -> tuple[str, str]:
    dates = pd.to_datetime(events["이벤트시작일"])
    start = (dates.min() - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    end = (dates.max() + pd.Timedelta(days=370)).strftime("%Y-%m-%d")
    return start, end


def main() -> None:
    events = pd.read_csv(EVENTS_IN, dtype={"종목코드": str})
    eligible = events[events["match_status"].isin(VALID_STATUSES)].copy()
    eligible = eligible[eligible["시장"].isin(INDEX_CODES.keys())]
    start, end = date_window(eligible)

    STOCK_OUT_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"price window: {start} ~ {end}")
    print(f"eligible events: {len(eligible):,}")

    for index_code in sorted(set(INDEX_CODES.values())):
        out_path = INDEX_OUT_DIR / f"{index_code}.csv"
        df = fetch_reader(index_code, start, end)
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"index {index_code}: {len(df):,} rows -> {out_path}")
        time.sleep(0.2)

    codes = sorted(eligible["종목코드"].dropna().unique())
    failures = []
    for i, code in enumerate(codes, start=1):
        out_path = STOCK_OUT_DIR / f"{code}.csv"
        try:
            df = fetch_reader(code, start, end)
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"[{i}/{len(codes)}] {code}: {len(df):,} rows")
        except Exception as exc:
            failures.append({"종목코드": code, "error": repr(exc)})
            print(f"[{i}/{len(codes)}] {code}: FAILED {exc!r}")
        time.sleep(0.25)

    if failures:
        fail_path = Path("data/prices/fetch_failures.csv")
        pd.DataFrame(failures).to_csv(fail_path, index=False, encoding="utf-8-sig")
        print(f"failures: {len(failures):,} -> {fail_path}")


if __name__ == "__main__":
    main()
