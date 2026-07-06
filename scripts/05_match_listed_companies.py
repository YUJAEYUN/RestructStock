"""
뉴스 이벤트 회사명을 KRX 상장/상장폐지 종목 마스터에 매칭한다.

보수적 자동 매칭 원칙:
1) 현재 상장사 Name과 정확히 일치하면 current_exact
2) 상장폐지 Name과 정확히 일치하면 delisted_exact
3) 동일 이름으로 여러 코드가 잡히면 ambiguous로 남겨 수동 검수
4) 그 외는 unmatched로 남겨, 자회사/브랜드명/비상장/해외기업 여부를 사람이 확인

출력:
  data/processed/company_listing_matches.csv
  data/processed/events_with_listings.csv
"""
from pathlib import Path
import re

import pandas as pd

EVENTS_IN = Path("data/processed/events.csv")
LISTED_IN = Path("data/reference/listed_companies.csv")
DELISTED_IN = Path("data/reference/delisted_companies.csv")
MATCH_OUT = Path("data/processed/company_listing_matches.csv")
EVENTS_OUT = Path("data/processed/events_with_listings.csv")


def norm_name(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = re.sub(r"\s+", "", text)
    text = text.replace("(주)", "").replace("㈜", "")
    return text.strip()


def build_lookup(df: pd.DataFrame, status: str) -> dict[str, list[dict]]:
    lookup: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        name = norm_name(row.get("Name"))
        if not name:
            continue
        item = {
            "match_status": status,
            "종목코드": str(row.get("Code", "")).zfill(6),
            "상장사명": row.get("Name"),
            "시장": row.get("Market"),
            "업종": row.get("Industry") if "Industry" in row.index else row.get("Dept"),
            "상장일": row.get("ListingDate"),
            "상장폐지일": row.get("DelistingDate"),
            "상장폐지사유": row.get("Reason"),
        }
        lookup.setdefault(name, []).append(item)
    return lookup


def choose_match(name: str, listed_lookup: dict, delisted_lookup: dict) -> dict:
    key = norm_name(name)
    listed = listed_lookup.get(key, [])
    delisted = delisted_lookup.get(key, [])
    matches = listed + delisted

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        codes = ";".join(m["종목코드"] for m in matches)
        names = ";".join(str(m["상장사명"]) for m in matches)
        markets = ";".join(str(m["시장"]) for m in matches)
        return {
            "match_status": "ambiguous",
            "종목코드": codes,
            "상장사명": names,
            "시장": markets,
            "업종": None,
            "상장일": None,
            "상장폐지일": None,
            "상장폐지사유": None,
        }

    return {
        "match_status": "unmatched",
        "종목코드": None,
        "상장사명": None,
        "시장": None,
        "업종": None,
        "상장일": None,
        "상장폐지일": None,
        "상장폐지사유": None,
    }


def main() -> None:
    events = pd.read_csv(EVENTS_IN)
    listed = pd.read_csv(LISTED_IN, dtype={"Code": str})
    delisted = pd.read_csv(DELISTED_IN, dtype={"Code": str})

    listed_lookup = build_lookup(listed, "current_exact")
    delisted_lookup = build_lookup(delisted, "delisted_exact")

    companies = (
        events.groupby("회사명")
        .agg(이벤트수=("회사명", "size"), 최초이벤트일=("이벤트시작일", "min"), 최종이벤트일=("이벤트시작일", "max"))
        .reset_index()
        .sort_values(["이벤트수", "회사명"], ascending=[False, True])
    )

    match_rows = []
    for _, row in companies.iterrows():
        match = choose_match(row["회사명"], listed_lookup, delisted_lookup)
        match_rows.append({**row.to_dict(), **match, "검수결과": "", "검수메모": ""})

    matches = pd.DataFrame(match_rows)
    matches.to_csv(MATCH_OUT, index=False, encoding="utf-8-sig")

    events_with = events.merge(
        matches.drop(columns=["이벤트수", "최초이벤트일", "최종이벤트일"]),
        on="회사명",
        how="left",
    )
    events_with.to_csv(EVENTS_OUT, index=False, encoding="utf-8-sig")

    print(f"companies: {len(matches):,} -> {MATCH_OUT}")
    print(f"events: {len(events_with):,} -> {EVENTS_OUT}")
    print(matches["match_status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
