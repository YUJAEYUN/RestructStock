"""
정리된 뉴스(data/processed/news_clean.parquet)에서 기사별로 "실제 회사명 후보"를 추출한다.

문제: "구조조정" 키워드가 정부기관/협회/노조/외국기업/지역명/업종 통칭/인물명을
가리키는 기사에도 많이 쓰여서, 회사 이벤트만 걸러내려면 이런 노이즈를 제거해야 한다.

방법 (정밀도 우선, 재현율은 희생):
1) title_lead: 제목이 "회사명, ..." 형태로 시작하는 경우 (한국 뉴스 제목 관행상 신뢰도 높음)
2) org_fallback: 빅카인즈가 추출한 '기관' 컬럼의 첫 항목이 회사 접미사(전자/증권/은행/...)로
   끝나거나 알려진 회사명 목록에 있고, 그 이름이 실제로 제목에도 등장하는 경우만 채택
   (기관 컬럼 첫 항목이 기사 주제와 무관한 경우가 많아, 제목에 등장하는지로 재검증)

두 경로 모두 아래 블록리스트/규칙을 통과해야 하며, '인물' 컬럼에 등록된 사람 이름과
일치하면 후보에서 제외한다 (정치인 발언 기사가 회사명처럼 잡히는 것을 방지).

이 블록리스트는 수작업으로 반복 보완한 것으로 완전하지 않다. 특히 하위 빈도
후보들은 놓친 노이즈가 남아있을 수 있어 최종적으로는 사람이 한 번 더 훑어봐야 한다.

입력: data/processed/news_clean.parquet
출력: data/processed/matched_articles.parquet   (회사 후보가 잡힌 기사)
      data/processed/unmatched_articles.parquet (보류 - 후보를 못 찾은 기사)
      data/processed/company_candidates.csv     (고유 회사 후보 요약, 검수용)
"""
import re
import pandas as pd

INPUT_PATH = "data/processed/news_clean.parquet"
OUT_MATCHED = "data/processed/matched_articles.parquet"
OUT_UNMATCHED = "data/processed/unmatched_articles.parquet"
OUT_CANDIDATES_CSV = "data/processed/company_candidates.csv"

# ---------------------------------------------------------------------------
# 1. 노이즈 블록리스트 (카테고리별로 계속 보완)
# ---------------------------------------------------------------------------

GOV_AGENCIES = """
정부 청와대 국회 국회의원 정무위원회 정무위 예결위 기획재정위원회 정책위의장 인수위 인수위원회
금융위 금융위원회 금감원 금융감독원 금감원장 금융당국 기재부 기획재정부 고용노동부 고용부
산업통상자원부 산업부 지경부 국토교통부 국토부 보건복지부 복지부 중소벤처기업부 중기부 중기청
법무부 행정안전부 행안부 통일부 외교부 국방부 여성가족부 환경부 문화체육관광부 교육부 교과부
공정위 공정거래위원회 감사원 국세청 통계청 한경연 한국경제연구원 신보
검찰 경찰 대법원 헌법재판소 서울회생법원 법원 서울중앙지검 회생법원
정부서울청사 정부세종청사 총리실 국무조정실 국무총리실 대통령 대통령실 당국 당정 당정청 여야정 야3당
당정 여야 정치권 국민의당 더불어민주당 자유한국당 국민의힘 정의당 민주당 새누리당 새누리 민주통합당
민생당 바른미래당 열린우리당 한국당 더민주
지방자치단체 서울시 부산시 인천시 대구시 광주시 대전시 울산시 세종시 경기도 강원도
충청북도 충청남도 충북 충남 충북도 전라북도 전라남도 전북 전남 경상북도 경상남도 경북 경남 제주도
전남도 경남도 경북도 인천도개공 전남도의회 경북교육청
창원시 김해시 진도군 순창군 괴산군 부여군 수원시 원주시 구미시 군산시
전국경제인연합회 전경련 한국경영자총협회 경총 대한상공회의소 상공회의소 한국무역협회 무역협회
금투협 금융투자협회
민주노총 한국노총 노동조합 노조 노사 노사정
채권단 주채권은행 채권은행 채권은 주채 대주주 컨소시엄 국책은행 은행들 금융지주 금융지주사
산업은행 산은 KDB산업은행 수출입은행 수은 예금보험공사 예보 한국자산관리공사 캠코
신용보증기금 기술보증기금 정책금융공사 한국정책금융공사 서울보증 서울보증보험
경남신보 울산신보 경남발전연구원
한국은행 한은 중앙은행 한국거래소 거래소 유가증권 코스콤 코스피
한국가스공사 한국전력 한전 한국토지주택공사 LH 한국도로공사 한국수자원공사 한국철도공사 코레일
광물공사 한국광물자원공사 해양진흥공사 한국해양진흥공사 인천국제공항공사 한국공항공사 석유공사
한국개발연구원 KDI 대외경제정책연구원 출연연 국책연구원 국책연구기관 한국성장금융
수협 농협 농협금융 농협금융지주 새마을금고 신협 산림조합
경제협력개발기구 OECD IMF EU WTO UN 유엔 세계은행 IMF구제금융 국제결제은행 아시아인프라투자은행
국민연금 국민경제자문회의
""".split()

PERSON_NAME = "유일호 트럼프 권혁세 최경환 김석동 이주열 최상목 김종인 임종룡 박지원".split()

MISC_BLOCK = ("AI BNP파리바 C3.ai 무디스 피치 김앤장 스탠다드앤드푸어스 해진공 "
              "부산항 인천항 광양항 울산항 평택항 S&P").split()

FOREIGN_COUNTRY = """
미국 중국 일본 독일 영국 프랑스 러시아 인도 베트남 캐나다 호주 대만 스페인 이탈리아
네덜란드 스위스 스웨덴 노르웨이 핀란드 덴마크 벨기에 오스트리아 그리스 포르투갈
브라질 멕시코 아르헨티나 남아공 사우디 이란 이라크 이스라엘 터키 태국 인도네시아
말레이시아 싱가포르 필리핀 홍콩 마카오 북한 중동 아시아 유럽 아프리카
""".split()

FOREIGN_COMPANY = """
애플 구글 알파벳 마이크로소프트 MS 아마존 메타 페이스북 트위터 테슬라 넷플릭스
텐센트 알리바바 화웨이 샤오미 바이두 소니 도요타 토요타 닛산 혼다 미쓰비시
포드 GM 제너럴모터스 제너럴 모터스 보잉 에어버스 인텔 IBM HP 델 노키아 지멘스 폭스바겐 BMW 벤츠 다임러
월마트 디즈니 우버 에어비앤비 스타벅스 맥도날드 야후 오라클 시스코 퀄컴 AMD
엔비디아 코스트코 유니클로 자라 이케아 로레알 네슬레 유니레버
도이체방크 신일본제철 도쿄전력 모간스탠리 골드만삭스 UBS UBS증권 GE BP 인민은행
말레이시아항공 비구이위안 헝다 필립모리스 페르노리카 파나소닉 샤프 도시바 징가 머스크
코카콜라 일본항공 하이닉스 씨티그룹 HSBC 왓츠앱
""".split()

MEDIA = """
YTN 연합뉴스 로이터 로이터통신 블룸버그 블룸버그통신 한경닷컴 더벨 이투데이 뉴스핌 뉴시스 AP통신
조선일보 중앙일보 동아일보 한겨레 경향신문 매일경제 한국경제 서울경제 헤럴드경제
파이낸셜뉴스 아시아경제 머니투데이 이데일리 뉴스1 KBS MBC SBS JTBC 채널A TV조선
""".split()

UNIV_SUFFIX = ("대", "대학", "대학교")
UNIV_EXPLICIT = "중앙대 고려대 명지대 한성대 경주대 서원대 사립대 국립대 의대 카이스트 서울대 연세대".split()

GENERIC_NOUN = """
구조조정 희망퇴직 인력감축 대주주 채권단 컨소시엄 금융권 은행권 증권업 조선업 해운업
철강업 화학업 반도체업 자동차업 유통업 보험업 건설업 제조업 항공업 카드업 캐피탈업
중공업계 조선 해운 철강 화학 반도체 자동차 유통 보험 건설 제조 항공 카드 캐피탈
석유화학 정보통신 생명보험 손해보험 저축은행 저축은 시중은행 지방은행 인터넷은행
공사 공단 재단 협회 조합 연맹 총연맹 진흥원 연구원 연구소 위원회 이사회 간담회
채권 국민경제 세계경제 산업별 리서치 세미나 창사 국민연 최고경영자 유가증권
주주협의회 문화재단 사립학교법 CEO IB MOU SC CGT 시공사 공사비 피해 은행
대기업 중소기업 중소기업계 카드업계 유통업계 보험업계 철강업계 증권가 재계 건설주
산업계 보험사 증권업계 항공업계 금융투자업계 생보사 석화업계 제약업계 조선업계 건설업계
증권사 증권 홀딩스 생명 기업 투자은행 주식워런트증권 원샷법 PEF 업은행 타은행 국민은
현중 EY한영 한기평 상업은행 주주은행 STX그룹주
""".split()

FACILITY_SUFFIX = ("공장", "조선소", "지사", "지점", "사업장", "사업소", "센터", "연구소", "캠퍼스", "본부")
REGION_TOKEN = set(
    "서울 부산 인천 대구 광주 대전 울산 세종 경기 강원 충북 충남 전북 전남 경북 경남 제주 "
    "군산 거제 창원 통영 목포 포항 여수 순천 광양 평택 아산 천안 나주 구미".split()
)

BLOCKLIST = (
    set(GOV_AGENCIES) | set(PERSON_NAME) | set(FOREIGN_COUNTRY) | set(FOREIGN_COMPANY)
    | set(MEDIA) | set(UNIV_EXPLICIT) | set(GENERIC_NOUN) | REGION_TOKEN | set(MISC_BLOCK)
)

ANON_RE = re.compile(r"^[A-Z](사|은행|저축은행|증권|카드|그룹|기업)$")
GROUPCOUNT_RE = re.compile(r"^[0-9]+대(그룹|기업|은행|증권|계열사|사)$")
PARTYCOUNT_RE = re.compile(r"^[0-9]+당$")

COMPANY_SUFFIX = (
    "전자", "중공업", "조선해양", "증권", "은행", "카드", "캐피탈", "생명", "화재", "해운",
    "항공", "건설", "산업", "물산", "상사", "에너지", "디스플레이", "반도체", "철강", "제철", "화학", "정유",
    "타이어", "시멘트", "제약", "바이오", "헬스케어", "푸드", "홀딩스", "금융지주", "인프라코어",
    "모터스", "자동차", "텔레콤", "스틸", "머티리얼즈", "솔루션", "시스템즈",
    "쇼핑", "마트", "백화점", "리테일", "생명과학", "통신", "로직스", "호텔", "리조트", "엔지니어링",
    "방직", "실업", "상선", "로보틱스", "정공", "정밀", "손해보험", "생명보험", "금융",
)

KNOWN_SHORT_NAMES = set("""
삼성전자 현대차 현대자동차 기아 SK하이닉스 LG전자 LG화학 LG디스플레이 LGD 포스코 POSCO
한화 한화솔루션 한화오션 대우조선 대우조선해양 STX조선 STX조선해양 삼성중공업 현대중공업
현대미포조선 한진중공업 한진칼 한진해운 아시아나항공 대한항공 제주항공 진에어 티웨이항공
에어부산 이스타항공 이마트 롯데쇼핑 롯데마트 롯데하이마트 롯데온 롯데홈쇼핑 롯데면세점
롯데케미칼 롯데칠성음료 롯데건설 홈플러스 GS리테일 GS건설 신세계 신세계인터내셔날
현대백화점 CJ제일제당 CJ CGV 두산 두산인프라코어 두산중공업 두산건설 두산에너빌리티
한국GM 르노삼성 르노삼성자동차 르노삼성차 쌍용차 쌍용자동차 KG모빌리티 현대제철 동부제철 동국제강
세아제강 현대상선 HMM 팬오션 SK이노베이션 SK온 SK네트웍스 SK텔레콤 SK브로드밴드 SKC
SK스퀘어 KT KT&G LGU+ LG유플러스 카카오 네이버 엔씨소프트 넥슨 넷마블 신한은행 신한지주
국민은행 KB국민은행 KB금융 우리은행 우리금융 우리금융지주 하나은행 하나금융 하나금융지주 하나금융투자 KEB하나은행
씨티은행 한국씨티은행 한국SC은행 SC제일은행 IBK기업은행 기업은행 NH농협은행 농협은행
BNK금융 BNK부산은행 부산은행 DGB금융 대구은행 광주은행 전북은행 제주은행 경남은행
삼성증권 미래에셋대우 미래에셋증권 한국투자증권 한국금융지주 NH투자증권 KB증권 대신증권 유안타증권
신영증권 SK증권 유진투자증권 이베스트투자증권 현대차증권 메리츠증권 메리츠종금증권
KTB투자증권 하이투자증권 다올투자증권 IBK투자증권 키움증권 KDB대우증권 동양증권 대우증권
우리투자증권 하나대투증권 iM증권 케이프투자증권 유화증권 아이엠투자증권 상호저축은행
삼성카드 KB국민카드 신한카드 우리카드 하나카드 롯데카드 현대카드 BC카드
삼성화재 현대해상 메리츠화재 KB손해보험 KB손보 한화손해보험 한화손보 흥국화재 MG손해보험 MG손보 악사손해보험 DB손해보험
한화생명 삼성생명 교보생명 신한라이프 미래에셋생명 동양생명 KDB생명 알리안츠생명 푸르덴셜생명
신한생명 흥국생명 우리아비바생명 KB생명 에이스생명 ING생명 금호생명 현대라이프
아모레퍼시픽 LG생활건강 LG생건 오리온 하이트진로 오비맥주 롯데칠성 CJ대한통운 한진 현대글로비스
금호타이어 한국타이어 넥센타이어 효성 효성첨단소재 코오롱 코오롱인더스트리 코오롱FnC OCI 한솔제지
대한전선 LS전선 LS산전 LS일렉트릭 LS 웅진코웨이 코웨이 웅진씽크빅 웅진에너지 대성산업 대성그룹 남양건설 진흥기업
NHN NHN한국사이버결제 위메이드 컴투스 카카오게임즈 카카오엔터프라이즈 크래프톤 엔에이치엔
푸르밀 남양유업 매일유업 동원산업 동원F&B SPC삼립 오뚜기 농심 삼양식품 삼양사
현대오일뱅크 GS칼텍스 S-Oil 에쓰오일 SK에너지
아주 한라그룹 한라 만도 금호아시아나 금호산업 금호석유화학
동부그룹 동부화재 DB금융투자
유암코 IMM인베스트먼트 보스턴컨설팅그룹 CGV 11번가
KCC 한화케미칼 롯데손해보험 에이블씨엔씨 휠라홀딩스 하이마트 LG헬로비전 요기요
이마트에브리데이 파리크라상 팬택 한앤컴퍼니 현대카드 대우증권 코오롱
일동제약 하나투어 한화큐셀 신세계면세점 흥국화재 조흥은행 한미은행 대우차판매 롯데그룹
DB금융투자 현대일렉트릭 성동조선 현대미포조선 티몬 넷마블 SK넥실리스 티와이홀딩스
데브시스터즈 에쓰오일 한온시스템 동부건설 S&T모티브 태웅 휴맥스 극동건설 남진건설
동아건설 빗썸 모두투어 천경해운 멜파스 파인텍 엔에스엔 이랜드 디오 동아원 엠에스오토텍
바이오니아 중흥건설 여천NCC KBI국인산업 인터파크 유니온스틸 삼성종합화학 삼성에버랜드
현대건설 대우건설 성지건설 서울반도체 락앤락 SSG닷컴 롯데웰푸드 롯데멤버스 클리오
넷마블 SK플래닛 팬오션 오리엔탈정공 현대중공업그룹 현대차그룹 두산그룹 필립모리스코리아
한화-DL 삼성전기 삼성디스플레이 쌍용건설 중앙건설 롯데물산 BGF리테일 포스코엠텍 포스코플랜텍
LS네트웍스 KTH 김해시 웅진 티켓몬스터 야놀자 쿠팡 마켓컬리 배달의민족 우아한형제들
""".split())

ALIAS = {
    "현대중": "현대중공업", "아시아나": "아시아나항공", "롯데칠성": "롯데칠성음료", "LGD": "LG디스플레이",
    "LGU+": "LG유플러스", "LG생건": "LG생활건강", "STX조선": "STX조선해양", "한국지엠": "한국GM",
    "KDB대우증권": "대우증권", "하나금투": "하나금융투자", "현대차": "현대자동차",
    "POSCO": "포스코", "씨티": "한국씨티은행", "기아차": "기아", "BNK금융": "BNK금융지주",
}


def is_blocked(name):
    if name is None or isinstance(name, float):
        return True
    if len(name) <= 1:
        return True
    if re.match(r"^[0-9]+$", name):
        return True
    if name in BLOCKLIST:
        return True
    if any(name.endswith(suf) for suf in UNIV_SUFFIX) and name not in ("현대", "기아", "삼성", "한화"):
        return True
    if any(name.endswith(suf) for suf in FACILITY_SUFFIX):
        return True
    if name.endswith("노조") or name.endswith("노동조합"):
        return True
    return False


def is_blocked_final(name):
    if is_blocked(name):
        return True
    if name in KNOWN_SHORT_NAMES:
        return False
    if ANON_RE.match(name) or GROUPCOUNT_RE.match(name) or PARTYCOUNT_RE.match(name):
        return True
    if re.search(r"(시|군|구|청|원|처|위|회|도)$", name) and len(name) <= 5:
        return True
    return False


def clean_bracket(title):
    return re.sub(r"^(\[[^\]]+\]\s*)+", "", str(title)).strip()


def leading_name(title):
    t = clean_bracket(title)
    m = re.match(r"^([가-힣A-Za-z0-9&\.\-]{1,20})\s*[,·]", t)
    if m:
        return m.group(1).replace(" ", "")
    return None


def first_org(s):
    if pd.isna(s):
        return None
    parts = [p.strip().replace(" ", "") for p in str(s).split(",") if p.strip()]
    return parts[0] if parts else None


def normalize(name):
    return ALIAS.get(name, name)


def is_person(name, persons_field):
    if pd.isna(persons_field):
        return False
    persons = [p.strip() for p in str(persons_field).split(",") if p.strip()]
    return name in persons


def pick_candidate(row):
    lead = row["leading"]
    org = row["first_org"]
    title_flat = str(row["제목"]).replace(" ", "")

    if lead is not None and not is_blocked_final(lead):
        if lead in KNOWN_SHORT_NAMES or not is_person(lead, row.get("인물")):
            return normalize(lead), "title_lead"

    if org is not None and not is_blocked_final(org):
        is_company_like = org in KNOWN_SHORT_NAMES or any(org.endswith(suf) for suf in COMPANY_SUFFIX)
        if is_company_like and org in title_flat:
            return normalize(org), "org_fallback"

    return None, None


def main():
    clean = pd.read_parquet(INPUT_PATH)
    clean["leading"] = clean["제목"].apply(leading_name)
    clean["first_org"] = clean["기관"].apply(first_org)

    result = clean.apply(pick_candidate, axis=1, result_type="expand")
    clean["candidate"] = result[0]
    clean["match_type"] = result[1]

    matched = clean[clean["candidate"].notna()].copy()
    unmatched = clean[clean["candidate"].isna()].copy()

    print(f"전체 기사: {len(clean)}")
    print(f"회사 후보 매칭: {len(matched)} "
          f"(title_lead: {(matched['match_type'] == 'title_lead').sum()}, "
          f"org_fallback: {(matched['match_type'] == 'org_fallback').sum()})")
    print(f"미분류(보류): {len(unmatched)}")
    print(f"고유 회사 후보 수: {matched['candidate'].nunique()}")

    matched.to_parquet(OUT_MATCHED, index=False)
    unmatched.to_parquet(OUT_UNMATCHED, index=False)

    summary = (
        matched.groupby("candidate")
        .agg(기사수=("candidate", "size"), 최초날짜=("일자", "min"), 최종날짜=("일자", "max"),
             대표제목=("제목", lambda s: s.iloc[0]))
        .reset_index()
        .rename(columns={"candidate": "회사명후보"})
        .sort_values("기사수", ascending=False)
    )
    summary.to_csv(OUT_CANDIDATES_CSV, index=False, encoding="utf-8-sig")
    print(f"저장 완료: {OUT_MATCHED}, {OUT_UNMATCHED}, {OUT_CANDIDATES_CSV}")


if __name__ == "__main__":
    main()
