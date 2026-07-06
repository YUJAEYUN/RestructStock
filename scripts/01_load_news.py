"""
빅카인즈(BigKinds) 뉴스 검색 결과 엑셀 4개를 하나로 합치고,
빅카인즈 자체가 표시한 중복/예외 기사를 제거한다.

입력: NewsResult_YYYYMMDD-YYYYMMDD.xlsx (프로젝트 루트)
출력: data/processed/news_clean.parquet
"""
import glob
import pandas as pd

INPUT_GLOB = "NewsResult_*.xlsx"
OUTPUT_PATH = "data/processed/news_clean.parquet"


def load_all():
    frames = []
    for path in sorted(glob.glob(INPUT_GLOB)):
        df = pd.read_excel(path, engine="openpyxl")
        df["__source_file"] = path
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main():
    df = load_all()
    print(f"전체 기사 수: {len(df)}")

    flagged = df["분석제외 여부"].notna()
    print(f"빅카인즈 표시 중복/예외 제외: {flagged.sum()}건")

    clean = df[~flagged].copy()
    clean["일자"] = pd.to_datetime(clean["일자"].astype(str), format="%Y%m%d", errors="coerce")
    print(f"정제 후 기사 수: {len(clean)}")

    clean.to_parquet(OUTPUT_PATH, index=False)
    print(f"저장 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
