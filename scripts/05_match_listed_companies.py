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


MANUAL_MAPPING = {
    # Company Name: Ticker
    "포스코": "005490",       # POSCO홀딩스
    "현대중공업": "009540",   # HD현대 (holding company containing historical prices before split)
    "대우조선": "042660",     # 한화오션
    "대우조선해양": "042660",  # 한화오션
    "국민은행": "105560",     # KB금융 (holding company for events representing the bank)
    "KB국민은행": "105560",   # KB금융
    "신한은행": "055550",     # 신한지주
    "하나은행": "086790",     # 하나금융지주
    "하나금융": "086790",     # 하나금융지주
    "우리은행": "000030",     # 우리은행 (delisted ticker, which covers historical price before 2019)
    "삼성물산": "028260",     # 삼성물산 (listed ticker)
    "미래에셋증권": "006800", # 미래에셋증권
    "두산건설": "011160",     # 두산건설 (delisted ticker)
    "SK": "034730",           # SK
    "광주은행": "192530",     # 광주은행 (delisted ticker)
    "경남은행": "192520",     # 경남은행 (delisted ticker)
    "금호건설": "002990",     # 금호건설
    "핸디소프트": "220180",   # 핸디소프트
    "엔씨소프트": "036570",   # NC
    "엔씨": "036570",         # NC
    "현대상선": "011200",     # HMM
    "두산인프라코어": "042670",# HD현대인프라코어
    "두산중공업": "034020",   # 두산에너빌리티
    "하이투자증권": "139130",  # iM금융지주 (DGB금융지주)
    "한화케미칼": "009830",   # 한화솔루션
    "삼성정밀화학": "004000", # 롯데정밀화학
    "현대자동차": "005380",   # 현대차
    "한화손보": "000370",     # 한화손해보험
    "롯데마트": "023530",     # 롯데쇼핑
    "삼성디스플레이": "005930",# 삼성전자
    "우리투자증권": "005940", # NH투자증권 (merged)
    "HJ중공업": "097230",     # HJ중공업 (renamed from 한진중공업)
    "한진중공업": "097230",   # HJ중공업
    "SKB": "017670",          # SK텔레콤
    "SK브로드밴드": "017670", # SK텔레콤
    "롯데칠성음료": "005300", # 롯데칠성
    "카카오엔터프라이즈": "035720", # 카카오
    "IBK투자증권": "024110",  # 기업은행
    "KB국민카드": "105560",   # KB금융
    "동부화재": "005830",     # DB손해보험
    "동양네트웍스": "030790", # 비케이탑스 (delisted)
    "롯데그룹": "004990",     # 롯데지주
    "롯데백화점": "023530",   # 롯데쇼핑
    "롯데온": "023530",       # 롯데쇼핑
    "만도": "204320",         # HL만도
    "신한금융투자": "055550", # 신한지주
    "신한생명": "055550",     # 신한지주
    "쌍용차": "003620",       # KG모빌리티
    "쌍용자동차": "003620",   # KG모빌리티
    "우리카드": "316140",     # 우리금융지주
    "하나카드": "086790",     # 하나금융지주
    "현대미포조선": "010620", # HD현대미포
    "현대일렉트릭": "267260", # HD현대일렉트릭
    "휠라홀딩스": "081660",   # 휠라홀딩스
    "두산그룹": "000150",     # 두산
    "신한카드": "055550",     # 신한지주
    "오비맥주": "exclude",
    "한국GM": "exclude",
    "씨티은행": "exclude",
    "한국씨티은행": "exclude",
    "홈플러스": "exclude",
    "르노삼성차": "exclude",
    "르노삼성": "exclude",
    "르노삼성자동차": "exclude",
    "유암코": "exclude",
    "이스타항공": "exclude",
    "11번가": "exclude",
    "롯데면세점": "exclude",
    "넥슨": "exclude",
    "농협은행": "exclude",
    "NH농협은행": "exclude",
    "성동조선": "exclude",
    "이랜드": "exclude",
    "한국SC은행": "exclude",
    "SC은행": "exclude",
    "SC제일은행": "exclude",
    "흥국생명": "exclude",
    "삼성": "exclude",
}


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
    if name in MANUAL_MAPPING:
        code = MANUAL_MAPPING[name]
        if code == "exclude":
            return {
                "match_status": "exclude",
                "종목코드": None,
                "상장사명": None,
                "시장": None,
                "업종": None,
                "상장일": None,
                "상장폐지일": None,
                "상장폐지사유": None,
            }
        
        # Search for code in listed/delisted lookups
        found_matches = []
        for key, item_list in listed_lookup.items():
            for item in item_list:
                if item["종목코드"] == code:
                    found_matches.append(item)
        for key, item_list in delisted_lookup.items():
            for item in item_list:
                if item["종목코드"] == code:
                    found_matches.append(item)
        
        if found_matches:
            return found_matches[0]
            
        return {
            "match_status": "manual_code",
            "종목코드": code,
            "상장사명": name,
            "시장": None,
            "업종": None,
            "상장일": None,
            "상장폐지일": None,
            "상장폐지사유": None,
        }

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
