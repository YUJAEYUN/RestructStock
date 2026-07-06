"""
회사 후보가 잡힌 기사(matched_articles.parquet)를 "이벤트" 단위로 묶는다.

같은 회사에 대해 여러 언론사가 근접한 날짜에 보도하면 같은 사건으로 보고 묶고,
그 사건의 시작일(가장 이른 보도일)을 이벤트 날짜로 사용한다. 같은 회사라도
날짜 간격이 30일을 넘어가면 별도의 이벤트(예: 2015년 구조조정, 2020년 구조조정)로 취급한다.

입력: data/processed/matched_articles.parquet
출력: data/processed/events.csv
"""
import pandas as pd

INPUT_PATH = "data/processed/matched_articles.parquet"
OUTPUT_PATH = "data/processed/events.csv"
GAP_DAYS = 30

KEYWORDS = ["구조조정", "희망퇴직", "인력감축"]


def keywords_in(title):
    return [k for k in KEYWORDS if k in str(title)]


def cluster_company(grp):
    grp = grp.sort_values("일자")
    dates = grp["일자"].tolist()
    events = []
    start_idx = 0
    prev_date = dates[0]
    n = len(dates)
    for i in range(1, n + 1):
        if i == n or (dates[i] - prev_date).days > GAP_DAYS:
            cluster = grp.iloc[start_idx:i]
            kws = sorted(set(k for t in cluster["제목"] for k in keywords_in(t)))
            events.append({
                "이벤트시작일": cluster["일자"].min(),
                "이벤트종료일(마지막보도)": cluster["일자"].max(),
                "기사수": len(cluster),
                "언론사수": cluster["언론사"].nunique(),
                "키워드종류": ",".join(kws),
                "대표제목": cluster.iloc[0]["제목"],
            })
            start_idx = i
            if i < n:
                prev_date = dates[i]
        else:
            prev_date = dates[i]
    return events


def main():
    matched = pd.read_parquet(INPUT_PATH)
    matched = matched.sort_values(["candidate", "일자"])

    rows = []
    for company, grp in matched.groupby("candidate"):
        for ev in cluster_company(grp):
            ev["회사명"] = company
            rows.append(ev)

    ev_df = pd.DataFrame(rows)
    ev_df = ev_df[["회사명", "이벤트시작일", "이벤트종료일(마지막보도)", "기사수", "언론사수", "키워드종류", "대표제목"]]
    ev_df["이벤트시작일"] = pd.to_datetime(ev_df["이벤트시작일"]).dt.strftime("%Y-%m-%d")
    ev_df["이벤트종료일(마지막보도)"] = pd.to_datetime(ev_df["이벤트종료일(마지막보도)"]).dt.strftime("%Y-%m-%d")
    ev_df = ev_df.sort_values(["회사명", "이벤트시작일"]).reset_index(drop=True)

    print(f"총 이벤트 수: {len(ev_df)}")
    print(f"고유 회사 수: {ev_df['회사명'].nunique()}")
    print(f"기사 1건짜리 이벤트(저신뢰): {(ev_df['기사수'] == 1).sum()}건")

    ev_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
