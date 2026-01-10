"""
팀명 매핑 데이터베이스

베트맨/젠토토 팀명 <-> 외부 API 팀명 매핑
각 팀은 API별 ID와 별칭(aliases)을 포함합니다.

사용 예시:
    from src.services.data.team_mapping import TeamMapper

    mapper = TeamMapper()

    # 팀명으로 API ID 조회
    api_id = mapper.get_api_id("맨시티", api="api_football", sport="soccer")

    # 정규화된 팀명 조회
    normalized = mapper.get_normalized_name("맨체스터시티", sport="soccer")
"""

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


# =============================================================================
# 축구 팀 매핑 (SOCCER_TEAM_MAPPING)
# =============================================================================

SOCCER_TEAM_MAPPING: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # 프리미어리그 (Premier League)
    # =========================================================================
    "맨시티": {
        "aliases": ["맨체스터시티", "맨체스터 시티", "Manchester City", "Man City", "맨체스C"],
        "api_football_id": 50,
        "football_data_id": 65,
        "league": "Premier League",
    },
    "리버풀": {
        "aliases": ["리버풀FC", "Liverpool", "Liverpool FC", "레즈"],
        "api_football_id": 40,
        "football_data_id": 64,
        "league": "Premier League",
    },
    "아스널": {
        "aliases": ["아스날", "아스널FC", "Arsenal", "Arsenal FC", "거너스"],
        "api_football_id": 42,
        "football_data_id": 57,
        "league": "Premier League",
    },
    "첼시": {
        "aliases": ["첼시FC", "Chelsea", "Chelsea FC", "블루스"],
        "api_football_id": 49,
        "football_data_id": 61,
        "league": "Premier League",
    },
    "토트넘": {
        "aliases": ["토트넘홋스퍼", "토트넘H", "Tottenham", "Tottenham Hotspur", "스퍼스", "Spurs"],
        "api_football_id": 47,
        "football_data_id": 73,
        "league": "Premier League",
    },
    "맨유": {
        "aliases": ["맨체스터유나이티드", "맨체스터 유나이티드", "맨체스U", "Manchester United", "Man Utd", "레드데블스"],
        "api_football_id": 33,
        "football_data_id": 66,
        "league": "Premier League",
    },
    "뉴캐슬": {
        "aliases": ["뉴캐슬유나이티드", "뉴캐슬U", "뉴캐슬 유나이티드", "Newcastle United", "Newcastle"],
        "api_football_id": 34,
        "football_data_id": 67,
        "league": "Premier League",
    },
    "브라이튼": {
        "aliases": ["브라이튼호브알비온", "브라이튼H", "브라이튼 호브 알비온", "Brighton", "Brighton & Hove Albion"],
        "api_football_id": 51,
        "football_data_id": 397,
        "league": "Premier League",
    },
    "A빌라": {
        "aliases": ["아스톤빌라", "아스톤 빌라", "빌라", "Aston Villa"],
        "api_football_id": 66,
        "football_data_id": 58,
        "league": "Premier League",
    },
    "웨스트햄": {
        "aliases": ["웨스트햄유나이티드", "웨스트햄U", "웨스트햄 유나이티드", "West Ham", "West Ham United"],
        "api_football_id": 48,
        "football_data_id": 563,
        "league": "Premier League",
    },
    "풀럼": {
        "aliases": ["풀럼FC", "Fulham", "코티저스"],
        "api_football_id": 36,
        "football_data_id": 63,
        "league": "Premier League",
    },
    "본머스": {
        "aliases": ["본머스FC", "AFC본머스", "AFC Bournemouth", "Bournemouth", "체리스"],
        "api_football_id": 35,
        "football_data_id": 1044,
        "league": "Premier League",
    },
    "크리스탈P": {
        "aliases": ["크리스탈팰리스", "크리스탈 팰리스", "팰리스", "Crystal Palace"],
        "api_football_id": 52,
        "football_data_id": 354,
        "league": "Premier League",
    },
    "브렌트포드": {
        "aliases": ["브렌트포드FC", "Brentford", "비즈"],
        "api_football_id": 55,
        "football_data_id": 402,
        "league": "Premier League",
    },
    "에버턴": {
        "aliases": ["에버턴FC", "Everton", "토피스"],
        "api_football_id": 45,
        "football_data_id": 62,
        "league": "Premier League",
    },
    "노팅엄포": {
        "aliases": ["노팅엄포리스트", "노팅엄 포리스트", "노팅엄", "Nottingham Forest"],
        "api_football_id": 65,
        "football_data_id": 351,
        "league": "Premier League",
    },
    "울브스": {
        "aliases": ["울버햄튼원더러스", "울버햄튼W", "울버햄튼", "Wolverhampton", "Wolves"],
        "api_football_id": 39,
        "football_data_id": 76,
        "league": "Premier League",
    },
    "입스위치": {
        "aliases": ["입스위치타운", "입스위치T", "입스위치 타운", "Ipswich Town", "Ipswich"],
        "api_football_id": 57,
        "football_data_id": 349,
        "league": "Premier League",
    },
    "사우샘프턴": {
        "aliases": ["사우샘프턴FC", "Southampton", "세인츠"],
        "api_football_id": 41,
        "football_data_id": 340,
        "league": "Premier League",
    },
    "레스터": {
        "aliases": ["레스터시티", "레스터C", "레스터 시티", "Leicester City", "Leicester"],
        "api_football_id": 46,
        "football_data_id": 338,
        "league": "Premier League",
    },

    # =========================================================================
    # 세리에A (Serie A)
    # =========================================================================
    "인테르밀란": {
        "aliases": ["인테르", "인테르 밀란", "Inter Milan", "Inter", "인터밀란", "네라주리"],
        "api_football_id": 505,
        "football_data_id": 108,
        "league": "Serie A",
    },
    "밀란": {
        "aliases": ["AC밀란", "AC 밀란", "AC Milan", "Milan", "로소네리"],
        "api_football_id": 489,
        "football_data_id": 98,
        "league": "Serie A",
    },
    "유벤투스": {
        "aliases": ["유베", "Juventus", "Juve", "비안코네리"],
        "api_football_id": 496,
        "football_data_id": 109,
        "league": "Serie A",
    },
    "나폴리": {
        "aliases": ["SSC나폴리", "SSC Napoli", "Napoli"],
        "api_football_id": 492,
        "football_data_id": 113,
        "league": "Serie A",
    },
    "로마": {
        "aliases": ["AS로마", "AS Roma", "Roma", "지알로로시"],
        "api_football_id": 497,
        "football_data_id": 100,
        "league": "Serie A",
    },
    "라치오": {
        "aliases": ["SS라치오", "SS Lazio", "Lazio", "비안코첼레스티"],
        "api_football_id": 487,
        "football_data_id": 110,
        "league": "Serie A",
    },
    "아탈란타": {
        "aliases": ["아탈란타BC", "Atalanta", "Atalanta BC"],
        "api_football_id": 499,
        "football_data_id": 102,
        "league": "Serie A",
    },
    "피오렌티나": {
        "aliases": ["피오렌티나", "ACF피오렌티나", "ACF Fiorentina", "Fiorentina", "비올라"],
        "api_football_id": 502,
        "football_data_id": 99,
        "league": "Serie A",
    },
    "볼로냐": {
        "aliases": ["볼로냐FC", "Bologna", "Bologna FC", "로소블루"],
        "api_football_id": 500,
        "football_data_id": 103,
        "league": "Serie A",
    },
    "토리노": {
        "aliases": ["토리노FC", "Torino", "Torino FC"],
        "api_football_id": 503,
        "football_data_id": 586,
        "league": "Serie A",
    },
    "우디네세": {
        "aliases": ["우디네세칼초", "Udinese", "Udinese Calcio"],
        "api_football_id": 494,
        "football_data_id": 115,
        "league": "Serie A",
    },
    "엠폴리": {
        "aliases": ["엠폴리FC", "Empoli", "Empoli FC"],
        "api_football_id": 511,
        "football_data_id": 445,
        "league": "Serie A",
    },
    "베로나": {
        "aliases": ["헬라스베로나", "엘라스베로나", "Verona", "Hellas Verona"],
        "api_football_id": 504,
        "football_data_id": 450,
        "league": "Serie A",
    },
    "칼리아리": {
        "aliases": ["칼리아리칼초", "Cagliari", "Cagliari Calcio"],
        "api_football_id": 490,
        "football_data_id": 104,
        "league": "Serie A",
    },
    "제노아": {
        "aliases": ["제노아CFC", "Genoa", "Genoa CFC"],
        "api_football_id": 495,
        "football_data_id": 107,
        "league": "Serie A",
    },
    "레체": {
        "aliases": ["US레체", "Lecce", "US Lecce"],
        "api_football_id": 867,
        "football_data_id": 5911,
        "league": "Serie A",
    },
    "파르마": {
        "aliases": ["파르마칼초", "Parma", "Parma Calcio"],
        "api_football_id": 523,
        "football_data_id": 112,
        "league": "Serie A",
    },
    "코모1907": {
        "aliases": ["코모", "Como 1907", "Como"],
        "api_football_id": 867,
        "football_data_id": None,
        "league": "Serie A",
    },
    "베네치아": {
        "aliases": ["베네치아FC", "Venezia", "Venezia FC"],
        "api_football_id": 517,
        "football_data_id": 454,
        "league": "Serie A",
    },
    "몬자": {
        "aliases": ["AC몬자", "Monza", "AC Monza"],
        "api_football_id": 1579,
        "football_data_id": 5890,
        "league": "Serie A",
    },

    # =========================================================================
    # 분데스리가 (Bundesliga)
    # =========================================================================
    "바이에른": {
        "aliases": ["바이에른뮌헨", "Bayern Munich", "Bayern", "FC Bayern", "뮌헨"],
        "api_football_id": 157,
        "football_data_id": 5,
        "league": "Bundesliga",
    },
    "도르트문트": {
        "aliases": ["보루시아도르트문트", "Borussia Dortmund", "Dortmund", "BVB"],
        "api_football_id": 165,
        "football_data_id": 4,
        "league": "Bundesliga",
    },
    "라이프치히": {
        "aliases": ["RB라이프치히", "RB Leipzig", "Leipzig"],
        "api_football_id": 173,
        "football_data_id": 721,
        "league": "Bundesliga",
    },
    "레버쿠젠": {
        "aliases": ["바이어레버쿠젠", "Bayer Leverkusen", "Leverkusen", "바이어04"],
        "api_football_id": 168,
        "football_data_id": 3,
        "league": "Bundesliga",
    },
    "프랑크푸르트": {
        "aliases": ["아인트라흐트프랑크푸르트", "Eintracht Frankfurt", "Frankfurt"],
        "api_football_id": 169,
        "football_data_id": 19,
        "league": "Bundesliga",
    },
    "슈투트가르트": {
        "aliases": ["VfB슈투트가르트", "VfB Stuttgart", "Stuttgart"],
        "api_football_id": 172,
        "football_data_id": 10,
        "league": "Bundesliga",
    },
    "브레멘": {
        "aliases": ["베르더브레멘", "Werder Bremen", "Bremen"],
        "api_football_id": 162,
        "football_data_id": 12,
        "league": "Bundesliga",
    },
    "볼프스부르크": {
        "aliases": ["VfL볼프스부르크", "VfL Wolfsburg", "Wolfsburg"],
        "api_football_id": 161,
        "football_data_id": 11,
        "league": "Bundesliga",
    },
    "프라이부르크": {
        "aliases": ["SC프라이부르크", "SC Freiburg", "Freiburg"],
        "api_football_id": 160,
        "football_data_id": 17,
        "league": "Bundesliga",
    },
    "호펜하임": {
        "aliases": ["TSG호펜하임", "TSG Hoffenheim", "Hoffenheim", "1899호펜하임"],
        "api_football_id": 167,
        "football_data_id": 2,
        "league": "Bundesliga",
    },
    "마인츠": {
        "aliases": ["마인츠05", "FSV Mainz 05", "Mainz"],
        "api_football_id": 164,
        "football_data_id": 15,
        "league": "Bundesliga",
    },
    "묀헨글라트바흐": {
        "aliases": ["보루시아묀헨글라트바흐", "Borussia Monchengladbach", "Gladbach", "묀헨글라드바흐"],
        "api_football_id": 163,
        "football_data_id": 18,
        "league": "Bundesliga",
    },
    "아우크스부르크": {
        "aliases": ["FC아우크스부르크", "FC Augsburg", "Augsburg"],
        "api_football_id": 170,
        "football_data_id": 16,
        "league": "Bundesliga",
    },
    "보훔": {
        "aliases": ["VfL보훔", "VfL Bochum", "Bochum"],
        "api_football_id": 176,
        "football_data_id": 36,
        "league": "Bundesliga",
    },
    "하이덴하임": {
        "aliases": ["1.FC하이덴하임", "1. FC Heidenheim", "Heidenheim"],
        "api_football_id": 180,
        "football_data_id": 7911,
        "league": "Bundesliga",
    },
    "장크트파울리": {
        "aliases": ["FC장크트파울리", "FC St. Pauli", "St. Pauli"],
        "api_football_id": 186,
        "football_data_id": 20,
        "league": "Bundesliga",
    },
    "키엘": {
        "aliases": ["홀슈타인키엘", "Holstein Kiel", "Kiel"],
        "api_football_id": 191,
        "football_data_id": 720,
        "league": "Bundesliga",
    },
    "우니온베를린": {
        "aliases": ["우니온 베를린", "1.FC Union Berlin", "Union Berlin"],
        "api_football_id": 182,
        "football_data_id": 28,
        "league": "Bundesliga",
    },

    # =========================================================================
    # 라리가 (La Liga)
    # =========================================================================
    "레알마드리드": {
        "aliases": ["레알", "Real Madrid", "Real", "은하군단"],
        "api_football_id": 541,
        "football_data_id": 86,
        "league": "La Liga",
    },
    "바르셀로나": {
        "aliases": ["바르사", "FC Barcelona", "Barcelona", "Barca", "블라우그라나"],
        "api_football_id": 529,
        "football_data_id": 81,
        "league": "La Liga",
    },
    "AT마드리드": {
        "aliases": ["아틀레티코마드리드", "아틀레티코 마드리드", "Atletico Madrid", "Atletico"],
        "api_football_id": 530,
        "football_data_id": 78,
        "league": "La Liga",
    },
    "세비야": {
        "aliases": ["세비야FC", "Sevilla", "Sevilla FC"],
        "api_football_id": 536,
        "football_data_id": 559,
        "league": "La Liga",
    },
    "빌바오": {
        "aliases": ["아틀레틱빌바오", "아틀레틱 빌바오", "Athletic Bilbao", "Athletic Club"],
        "api_football_id": 531,
        "football_data_id": 77,
        "league": "La Liga",
    },
    "레알소시에다드": {
        "aliases": ["소시에다드", "Real Sociedad", "Sociedad"],
        "api_football_id": 548,
        "football_data_id": 92,
        "league": "La Liga",
    },
    "비야레알": {
        "aliases": ["비야레알CF", "Villarreal", "Villarreal CF", "옐로우서브마린"],
        "api_football_id": 533,
        "football_data_id": 94,
        "league": "La Liga",
    },
    "베티스": {
        "aliases": ["레알베티스", "Real Betis", "Betis"],
        "api_football_id": 543,
        "football_data_id": 90,
        "league": "La Liga",
    },
    "발렌시아": {
        "aliases": ["발렌시아CF", "Valencia", "Valencia CF"],
        "api_football_id": 532,
        "football_data_id": 95,
        "league": "La Liga",
    },
    "셀타비고": {
        "aliases": ["셀타 비고", "Celta Vigo", "Celta"],
        "api_football_id": 538,
        "football_data_id": 558,
        "league": "La Liga",
    },
    "헤타페": {
        "aliases": ["헤타페CF", "Getafe", "Getafe CF"],
        "api_football_id": 546,
        "football_data_id": 82,
        "league": "La Liga",
    },
    "오사수나": {
        "aliases": ["CA오사수나", "Osasuna", "CA Osasuna"],
        "api_football_id": 727,
        "football_data_id": 79,
        "league": "La Liga",
    },
    "지로나": {
        "aliases": ["지로나FC", "Girona", "Girona FC"],
        "api_football_id": 547,
        "football_data_id": 298,
        "league": "La Liga",
    },
    "마요르카": {
        "aliases": ["RCD마요르카", "RCD Mallorca", "Mallorca"],
        "api_football_id": 798,
        "football_data_id": 89,
        "league": "La Liga",
    },
    "알라베스": {
        "aliases": ["데포르티보알라베스", "Deportivo Alaves", "Alaves"],
        "api_football_id": 542,
        "football_data_id": 263,
        "league": "La Liga",
    },
    "라스팔마스": {
        "aliases": ["UD라스팔마스", "Las Palmas", "UD Las Palmas"],
        "api_football_id": 534,
        "football_data_id": 275,
        "league": "La Liga",
    },
    "에스파뇰": {
        "aliases": ["RCD에스파뇰", "Espanyol", "RCD Espanyol"],
        "api_football_id": 540,
        "football_data_id": 80,
        "league": "La Liga",
    },
    "라요바예카노": {
        "aliases": ["라요 바예카노", "Rayo Vallecano", "Rayo"],
        "api_football_id": 728,
        "football_data_id": 87,
        "league": "La Liga",
    },
    "레가네스": {
        "aliases": ["CD레가네스", "Leganes", "CD Leganes"],
        "api_football_id": 539,
        "football_data_id": 745,
        "league": "La Liga",
    },
    "바야돌리드": {
        "aliases": ["레알바야돌리드", "Real Valladolid", "Valladolid"],
        "api_football_id": 720,
        "football_data_id": 250,
        "league": "La Liga",
    },

    # =========================================================================
    # 챔피언십 (EFL Championship)
    # =========================================================================
    "리즈": {
        "aliases": ["리즈유나이티드", "리즈U", "리즈 유나이티드", "Leeds United", "Leeds"],
        "api_football_id": 63,
        "football_data_id": 341,
        "league": "Championship",
    },
    "번리": {
        "aliases": ["번리FC", "Burnley", "클라렛"],
        "api_football_id": 44,
        "football_data_id": 328,
        "league": "Championship",
    },
    "셰필드U": {
        "aliases": ["셰필드유나이티드", "셰필드 유나이티드", "Sheffield United", "Sheffield Utd"],
        "api_football_id": 62,
        "football_data_id": 356,
        "league": "Championship",
    },
    "노리치": {
        "aliases": ["노리치시티", "노리치C", "노리치 시티", "Norwich City", "Norwich"],
        "api_football_id": 71,
        "football_data_id": 68,
        "league": "Championship",
    },
    "미들즈브러": {
        "aliases": ["미들즈브러FC", "Middlesbrough", "보로"],
        "api_football_id": 56,
        "football_data_id": 343,
        "league": "Championship",
    },
    "선더랜드": {
        "aliases": ["선더랜드AFC", "Sunderland", "블랙캣츠"],
        "api_football_id": 740,
        "football_data_id": 71,
        "league": "Championship",
    },
    "왓포드": {
        "aliases": ["왓포드FC", "Watford", "호넷츠"],
        "api_football_id": 38,
        "football_data_id": 346,
        "league": "Championship",
    },
    "WBA": {
        "aliases": ["웨스트브로미치앨비언", "웨스트브롬", "웨스트 브로미치", "West Brom", "West Bromwich Albion"],
        "api_football_id": 60,
        "football_data_id": 74,
        "league": "Championship",
    },
    "스토크": {
        "aliases": ["스토크시티", "스토크C", "스토크 시티", "Stoke City", "Stoke"],
        "api_football_id": 75,
        "football_data_id": 70,
        "league": "Championship",
    },
    "브리스틀C": {
        "aliases": ["브리스틀시티", "브리스틀 시티", "Bristol City", "Bristol"],
        "api_football_id": 64,
        "football_data_id": 387,
        "league": "Championship",
    },
    "코번트리": {
        "aliases": ["코번트리시티", "코번트리C", "코번트리 시티", "Coventry City", "Coventry"],
        "api_football_id": 750,
        "football_data_id": 1076,
        "league": "Championship",
    },
    "스완지": {
        "aliases": ["스완지시티", "스완지C", "스완지 시티", "Swansea City", "Swansea"],
        "api_football_id": 72,
        "football_data_id": 72,
        "league": "Championship",
    },
    "QPR": {
        "aliases": ["퀸즈파크레인저스", "퀸즈 파크 레인저스", "Queens Park Rangers"],
        "api_football_id": 69,
        "football_data_id": 69,
        "league": "Championship",
    },
    "블랙번": {
        "aliases": ["블랙번로버스", "블랙번 로버스", "Blackburn Rovers", "Blackburn"],
        "api_football_id": 59,
        "football_data_id": 59,
        "league": "Championship",
    },
    "밀월": {
        "aliases": ["밀월FC", "Millwall"],
        "api_football_id": 67,
        "football_data_id": 384,
        "league": "Championship",
    },
    "프레스턴": {
        "aliases": ["프레스턴노스엔드", "프레스턴NE", "프레스턴 노스 엔드", "Preston North End", "Preston"],
        "api_football_id": 68,
        "football_data_id": 1081,
        "league": "Championship",
    },
    "헐시티": {
        "aliases": ["헐시티", "헐C", "헐 시티", "Hull City", "Hull"],
        "api_football_id": 73,
        "football_data_id": 322,
        "league": "Championship",
    },
    "카디프": {
        "aliases": ["카디프시티", "카디프C", "카디프 시티", "Cardiff City", "Cardiff"],
        "api_football_id": 61,
        "football_data_id": 715,
        "league": "Championship",
    },
    "더비": {
        "aliases": ["더비카운티", "더비카운", "더비 카운티", "Derby County", "Derby"],
        "api_football_id": 58,
        "football_data_id": 342,
        "league": "Championship",
    },
    "셰필드W": {
        "aliases": ["셰필드웬즈데이", "셰필드 웬즈데이", "Sheffield Wednesday"],
        "api_football_id": 74,
        "football_data_id": 345,
        "league": "Championship",
    },
    "포츠머스": {
        "aliases": ["포츠머스FC", "Portsmouth"],
        "api_football_id": 77,
        "football_data_id": 385,
        "league": "Championship",
    },
    "플리머스": {
        "aliases": ["플리머스아가일", "플리머스A", "플리머스 아가일", "Plymouth Argyle", "Plymouth"],
        "api_football_id": 753,
        "football_data_id": 1082,
        "league": "Championship",
    },
    "옥스포드": {
        "aliases": ["옥스포드유나이티드", "옥스포드U", "옥스포드 유나이티드", "Oxford United", "Oxford"],
        "api_football_id": 754,
        "football_data_id": 1085,
        "league": "Championship",
    },
    "루턴": {
        "aliases": ["루턴타운", "루턴T", "루턴 타운", "Luton Town", "Luton"],
        "api_football_id": 1359,
        "football_data_id": 389,
        "league": "Championship",
    },
    "찰턴": {
        "aliases": ["찰턴애슬레틱", "찰턴 애슬레틱", "Charlton Athletic", "Charlton"],
        "api_football_id": 1355,
        "football_data_id": 348,
        "league": "Championship",
    },
    "버밍엄": {
        "aliases": ["버밍엄시티", "버밍엄C", "버밍엄 시티", "Birmingham City", "Birmingham"],
        "api_football_id": 53,
        "football_data_id": 332,
        "league": "Championship",
    },

    # =========================================================================
    # 리그1 (Ligue 1)
    # =========================================================================
    "PSG": {
        "aliases": ["파리생제르맹", "파리 생제르맹", "Paris Saint-Germain", "Paris SG"],
        "api_football_id": 85,
        "football_data_id": 524,
        "league": "Ligue 1",
    },
    "마르세유": {
        "aliases": ["올림피크마르세유", "Olympique Marseille", "Marseille", "OM"],
        "api_football_id": 81,
        "football_data_id": 516,
        "league": "Ligue 1",
    },
    "모나코": {
        "aliases": ["AS모나코", "AS Monaco", "Monaco"],
        "api_football_id": 91,
        "football_data_id": 548,
        "league": "Ligue 1",
    },
    "릴": {
        "aliases": ["릴OSC", "LOSC Lille", "Lille"],
        "api_football_id": 79,
        "football_data_id": 521,
        "league": "Ligue 1",
    },
    "리옹": {
        "aliases": ["올림피크리옹", "Olympique Lyon", "Lyon", "OL"],
        "api_football_id": 80,
        "football_data_id": 523,
        "league": "Ligue 1",
    },
    "니스": {
        "aliases": ["OGC니스", "OGC Nice", "Nice"],
        "api_football_id": 84,
        "football_data_id": 522,
        "league": "Ligue 1",
    },
    "렌": {
        "aliases": ["스타드렌", "Stade Rennais", "Rennes"],
        "api_football_id": 94,
        "football_data_id": 529,
        "league": "Ligue 1",
    },
    "랑스": {
        "aliases": ["스타드랑스", "Stade Reims", "Reims"],
        "api_football_id": 93,
        "football_data_id": 547,
        "league": "Ligue 1",
    },

    # =========================================================================
    # 에레디비시 (Eredivisie)
    # =========================================================================
    "아약스": {
        "aliases": ["AFC아약스", "AFC Ajax", "Ajax"],
        "api_football_id": 194,
        "football_data_id": 666,
        "league": "Eredivisie",
    },
    "PSV": {
        "aliases": ["PSV에인트호번", "PSV Eindhoven", "PSV"],
        "api_football_id": 197,
        "football_data_id": 674,
        "league": "Eredivisie",
    },
    "페예노르트": {
        "aliases": ["페이에노르트", "Feyenoord"],
        "api_football_id": 193,
        "football_data_id": 675,
        "league": "Eredivisie",
    },

    # =========================================================================
    # 포르투갈 프리메이라리가 (Primeira Liga)
    # =========================================================================
    "벤피카": {
        "aliases": ["SL벤피카", "SL Benfica", "Benfica"],
        "api_football_id": 211,
        "football_data_id": 1903,
        "league": "Primeira Liga",
    },
    "포르투": {
        "aliases": ["FC포르투", "FC Porto", "Porto"],
        "api_football_id": 212,
        "football_data_id": 503,
        "league": "Primeira Liga",
    },
    "스포르팅": {
        "aliases": ["스포르팅CP", "스포르팅리스본", "Sporting CP", "Sporting Lisbon"],
        "api_football_id": 228,
        "football_data_id": 498,
        "league": "Primeira Liga",
    },
}


# =============================================================================
# 농구 팀 매핑 (BASKETBALL_TEAM_MAPPING)
# =============================================================================

BASKETBALL_TEAM_MAPPING: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # NBA (National Basketball Association)
    # =========================================================================
    "LA레이커스": {
        "aliases": ["로스앤젤레스레이커스", "LA 레이커스", "Los Angeles Lakers", "Lakers", "레이커스"],
        "api_basketball_id": 145,
        "league": "NBA",
    },
    "보스턴": {
        "aliases": ["보스턴셀틱스", "보스턴 셀틱스", "Boston Celtics", "Celtics", "셀틱스"],
        "api_basketball_id": 132,
        "league": "NBA",
    },
    "골든스테이트": {
        "aliases": ["골든스테이트워리어스", "골든스테이트 워리어스", "Golden State Warriors", "Warriors", "워리어스"],
        "api_basketball_id": 149,
        "league": "NBA",
    },
    "밀워키": {
        "aliases": ["밀워키벅스", "밀워키 벅스", "Milwaukee Bucks", "Bucks", "벅스"],
        "api_basketball_id": 142,
        "league": "NBA",
    },
    "덴버": {
        "aliases": ["덴버너겟츠", "덴버 너겟츠", "Denver Nuggets", "Nuggets", "너겟츠"],
        "api_basketball_id": 138,
        "league": "NBA",
    },
    "마이애미": {
        "aliases": ["마이애미히트", "마이애미 히트", "Miami Heat", "Heat", "히트"],
        "api_basketball_id": 141,
        "league": "NBA",
    },
    "필라델피아": {
        "aliases": ["필라델피아세븐티식서스", "필라델피아 76ers", "Philadelphia 76ers", "76ers", "식서스"],
        "api_basketball_id": 143,
        "league": "NBA",
    },
    "피닉스": {
        "aliases": ["피닉스선즈", "피닉스 선즈", "Phoenix Suns", "Suns", "선즈"],
        "api_basketball_id": 159,
        "league": "NBA",
    },
    "클리블랜드": {
        "aliases": ["클리블랜드캐벌리어스", "클리블랜드 캐벌리어스", "Cleveland Cavaliers", "Cavaliers", "캐브스"],
        "api_basketball_id": 137,
        "league": "NBA",
    },
    "뉴욕": {
        "aliases": ["뉴욕닉스", "뉴욕 닉스", "New York Knicks", "Knicks", "닉스"],
        "api_basketball_id": 157,
        "league": "NBA",
    },
    "브루클린": {
        "aliases": ["브루클린네츠", "브루클린 네츠", "Brooklyn Nets", "Nets", "네츠"],
        "api_basketball_id": 134,
        "league": "NBA",
    },
    "LA클리퍼스": {
        "aliases": ["로스앤젤레스클리퍼스", "LA 클리퍼스", "Los Angeles Clippers", "Clippers", "클리퍼스"],
        "api_basketball_id": 146,
        "league": "NBA",
    },
    "시카고": {
        "aliases": ["시카고불스", "시카고 불스", "Chicago Bulls", "Bulls", "불스"],
        "api_basketball_id": 136,
        "league": "NBA",
    },
    "토론토": {
        "aliases": ["토론토랩터스", "토론토 랩터스", "Toronto Raptors", "Raptors", "랩터스"],
        "api_basketball_id": 165,
        "league": "NBA",
    },
    "댈러스": {
        "aliases": ["댈러스매버릭스", "댈러스 매버릭스", "Dallas Mavericks", "Mavericks", "매버릭스"],
        "api_basketball_id": 150,
        "league": "NBA",
    },
    "멤피스": {
        "aliases": ["멤피스그리즐리스", "멤피스 그리즐리스", "Memphis Grizzlies", "Grizzlies", "그리즐리스"],
        "api_basketball_id": 147,
        "league": "NBA",
    },
    "새크라멘토": {
        "aliases": ["새크라멘토킹스", "새크라멘토 킹스", "Sacramento Kings", "Kings", "킹스"],
        "api_basketball_id": 161,
        "league": "NBA",
    },
    "애틀랜타": {
        "aliases": ["애틀랜타호크스", "애틀랜타 호크스", "Atlanta Hawks", "Hawks", "호크스"],
        "api_basketball_id": 131,
        "league": "NBA",
    },
    "미네소타": {
        "aliases": ["미네소타팀버울브스", "미네소타 팀버울브스", "Minnesota Timberwolves", "Timberwolves", "팀버울브스", "울브스"],
        "api_basketball_id": 152,
        "league": "NBA",
    },
    "뉴올리언스": {
        "aliases": ["뉴올리언스펠리컨스", "뉴올리언스 펠리컨스", "New Orleans Pelicans", "Pelicans", "펠리컨스"],
        "api_basketball_id": 155,
        "league": "NBA",
    },
    "오클라호마시티": {
        "aliases": ["오클라호마시티썬더", "오클라호마시티 썬더", "Oklahoma City Thunder", "Thunder", "썬더", "OKC"],
        "api_basketball_id": 158,
        "league": "NBA",
    },
    "포틀랜드": {
        "aliases": ["포틀랜드트레일블레이저스", "포틀랜드 트레일블레이저스", "Portland Trail Blazers", "Blazers", "블레이저스"],
        "api_basketball_id": 160,
        "league": "NBA",
    },
    "유타": {
        "aliases": ["유타재즈", "유타 재즈", "Utah Jazz", "Jazz", "재즈"],
        "api_basketball_id": 166,
        "league": "NBA",
    },
    "인디애나": {
        "aliases": ["인디애나페이서스", "인디애나 페이서스", "Indiana Pacers", "Pacers", "페이서스"],
        "api_basketball_id": 140,
        "league": "NBA",
    },
    "워싱턴": {
        "aliases": ["워싱턴위저즈", "워싱턴 위저즈", "Washington Wizards", "Wizards", "위저즈"],
        "api_basketball_id": 167,
        "league": "NBA",
    },
    "올랜도": {
        "aliases": ["올랜도매직", "올랜도 매직", "Orlando Magic", "Magic", "매직"],
        "api_basketball_id": 159,
        "league": "NBA",
    },
    "디트로이트": {
        "aliases": ["디트로이트피스톤스", "디트로이트 피스톤스", "Detroit Pistons", "Pistons", "피스톤스"],
        "api_basketball_id": 139,
        "league": "NBA",
    },
    "샬럿": {
        "aliases": ["샬럿호네츠", "샬럿 호네츠", "Charlotte Hornets", "Hornets", "호네츠"],
        "api_basketball_id": 135,
        "league": "NBA",
    },
    "휴스턴": {
        "aliases": ["휴스턴로케츠", "휴스턴 로케츠", "Houston Rockets", "Rockets", "로케츠"],
        "api_basketball_id": 153,
        "league": "NBA",
    },
    "샌안토니오": {
        "aliases": ["샌안토니오스퍼스", "샌안토니오 스퍼스", "San Antonio Spurs", "Spurs", "스퍼스"],
        "api_basketball_id": 162,
        "league": "NBA",
    },

    # =========================================================================
    # KBL (Korean Basketball League)
    # =========================================================================
    "울산모비스": {
        "aliases": ["울산현대모비스피버스", "울산현대모비스", "울산 현대모비스", "Ulsan Hyundai Mobis", "울산모비스피버스"],
        "api_basketball_id": None,
        "kbl_id": "01",
        "league": "KBL",
    },
    "서울SK": {
        "aliases": ["서울SK나이츠", "서울 SK", "SK나이츠", "Seoul SK Knights", "SK Knights"],
        "api_basketball_id": None,
        "kbl_id": "02",
        "league": "KBL",
    },
    "안양KGC": {
        "aliases": ["안양KGC인삼공사", "안양 KGC", "KGC인삼공사", "Anyang KGC", "KGC"],
        "api_basketball_id": None,
        "kbl_id": "03",
        "league": "KBL",
    },
    "원주DB": {
        "aliases": ["원주DB프로미", "원주 DB 프로미", "DB프로미", "Wonju DB Promy", "DB Promy"],
        "api_basketball_id": None,
        "kbl_id": "04",
        "league": "KBL",
    },
    "창원LG": {
        "aliases": ["창원LG세이커스", "창원 LG", "LG세이커스", "Changwon LG Sakers", "LG Sakers"],
        "api_basketball_id": None,
        "kbl_id": "05",
        "league": "KBL",
    },
    "고양소노": {
        "aliases": ["고양소노스카이거너스", "고양 소노", "소노스카이거너스", "Goyang Sono", "Sono Skygunners"],
        "api_basketball_id": None,
        "kbl_id": "06",
        "league": "KBL",
    },
    "수원KT": {
        "aliases": ["수원KT소닉붐", "수원 KT", "KT소닉붐", "Suwon KT Sonicboom", "KT Sonicboom"],
        "api_basketball_id": None,
        "kbl_id": "07",
        "league": "KBL",
    },
    "서울삼성": {
        "aliases": ["서울삼성썬더스", "서울 삼성 썬더스", "삼성썬더스", "Seoul Samsung Thunders", "Samsung Thunders"],
        "api_basketball_id": None,
        "kbl_id": "08",
        "league": "KBL",
    },
    "부산KCC": {
        "aliases": ["부산KCC이지스", "부산 KCC", "KCC이지스", "Busan KCC Egis", "KCC Egis"],
        "api_basketball_id": None,
        "kbl_id": "09",
        "league": "KBL",
    },
    "대구한국가스": {
        "aliases": ["대구한국가스공사", "대구 한국가스공사", "한국가스공사", "Daegu Korea Gas", "Korea Gas"],
        "api_basketball_id": None,
        "kbl_id": "10",
        "league": "KBL",
    },
}


# =============================================================================
# TeamMapper 클래스
# =============================================================================

@dataclass
class MatchResult:
    """매칭 결과"""
    original_name: str
    normalized_name: str
    confidence: float
    method: str  # "exact", "alias", "fuzzy"
    api_id: Optional[int] = None


class TeamMapper:
    """팀명 매퍼

    베트맨/젠토토 팀명을 외부 API의 팀 ID로 변환합니다.

    사용 예시:
        mapper = TeamMapper()

        # API ID 조회
        api_id = mapper.get_api_id("맨시티", api="api_football", sport="soccer")
        # 결과: 50

        # 정규화된 팀명 조회
        normalized = mapper.get_normalized_name("맨체스터시티", sport="soccer")
        # 결과: "맨시티"
    """

    def __init__(self):
        """초기화"""
        self.soccer_mapping = SOCCER_TEAM_MAPPING
        self.basketball_mapping = BASKETBALL_TEAM_MAPPING

        # 역방향 매핑 구축 (별칭 -> 정규화 팀명)
        self._soccer_reverse_mapping: Dict[str, str] = {}
        self._basketball_reverse_mapping: Dict[str, str] = {}
        self._build_reverse_mappings()

        logger.debug(f"TeamMapper 초기화: 축구 {len(self.soccer_mapping)}팀, 농구 {len(self.basketball_mapping)}팀")

    def _build_reverse_mappings(self) -> None:
        """역방향 매핑 구축"""
        # 축구
        for normalized_name, data in self.soccer_mapping.items():
            # 정규화 팀명 자체도 추가
            self._soccer_reverse_mapping[normalized_name.lower()] = normalized_name
            # 별칭들 추가
            for alias in data.get("aliases", []):
                self._soccer_reverse_mapping[alias.lower()] = normalized_name

        # 농구
        for normalized_name, data in self.basketball_mapping.items():
            self._basketball_reverse_mapping[normalized_name.lower()] = normalized_name
            for alias in data.get("aliases", []):
                self._basketball_reverse_mapping[alias.lower()] = normalized_name

    def get_api_id(
        self,
        team_name: str,
        api: str = "api_football",
        sport: str = "soccer"
    ) -> Optional[int]:
        """팀명으로 API ID 조회

        Args:
            team_name: 팀명 (한글 또는 영문)
            api: API 종류
                - soccer: "api_football", "football_data"
                - basketball: "api_basketball", "kbl"
            sport: 스포츠 종류 ("soccer" or "basketball")

        Returns:
            API ID 또는 None (매칭 실패 시)

        사용 예시:
            >>> mapper = TeamMapper()
            >>> mapper.get_api_id("맨시티", "api_football", "soccer")
            50
            >>> mapper.get_api_id("LA레이커스", "api_basketball", "basketball")
            145
        """
        mapping = self.soccer_mapping if sport == "soccer" else self.basketball_mapping
        id_key = f"{api}_id"

        # 1. 정확한 매칭
        if team_name in mapping:
            return mapping[team_name].get(id_key)

        # 2. 별칭 매칭
        team_name_lower = team_name.lower()
        for normalized_name, data in mapping.items():
            if team_name_lower == normalized_name.lower():
                return data.get(id_key)
            for alias in data.get("aliases", []):
                if team_name_lower == alias.lower():
                    return data.get(id_key)

        # 3. 퍼지 매칭 (최후 수단)
        return self._fuzzy_match(team_name, mapping, api)

    def get_normalized_name(
        self,
        team_name: str,
        sport: str = "soccer"
    ) -> Optional[str]:
        """정규화된 팀명 반환

        Args:
            team_name: 입력 팀명 (별칭 포함)
            sport: 스포츠 종류 ("soccer" or "basketball")

        Returns:
            정규화된 팀명 또는 None (매칭 실패 시)

        사용 예시:
            >>> mapper = TeamMapper()
            >>> mapper.get_normalized_name("맨체스터시티", "soccer")
            "맨시티"
            >>> mapper.get_normalized_name("울산현대모비스피버스", "basketball")
            "울산모비스"
        """
        reverse_mapping = (
            self._soccer_reverse_mapping
            if sport == "soccer"
            else self._basketball_reverse_mapping
        )
        mapping = self.soccer_mapping if sport == "soccer" else self.basketball_mapping

        team_name_lower = team_name.lower()

        # 1. 역방향 매핑에서 직접 조회
        if team_name_lower in reverse_mapping:
            return reverse_mapping[team_name_lower]

        # 2. 부분 문자열 매칭
        for alias, normalized in reverse_mapping.items():
            if alias in team_name_lower or team_name_lower in alias:
                return normalized

        # 3. 퍼지 매칭
        best_match = None
        best_ratio = 0.6  # 최소 60% 일치

        for normalized_name, data in mapping.items():
            # 정규화 팀명과 비교
            ratio = SequenceMatcher(None, team_name_lower, normalized_name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = normalized_name

            # 별칭과 비교
            for alias in data.get("aliases", []):
                ratio = SequenceMatcher(None, team_name_lower, alias.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = normalized_name

        return best_match

    def _fuzzy_match(
        self,
        name: str,
        mapping: Dict[str, Dict],
        api: str
    ) -> Optional[int]:
        """퍼지 매칭 (60% 이상 일치 시)

        Args:
            name: 검색할 팀명
            mapping: 팀 매핑 딕셔너리
            api: API 종류 (id 키 결정용)

        Returns:
            매칭된 API ID 또는 None
        """
        id_key = f"{api}_id"
        best_match_id = None
        best_ratio = 0.6  # 최소 60% 일치

        name_lower = name.lower()

        for normalized_name, data in mapping.items():
            # 정규화 팀명과 비교
            ratio = SequenceMatcher(None, name_lower, normalized_name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match_id = data.get(id_key)

            # 별칭과 비교
            for alias in data.get("aliases", []):
                ratio = SequenceMatcher(None, name_lower, alias.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match_id = data.get(id_key)

        if best_match_id and best_ratio >= 0.6:
            logger.debug(f"퍼지 매칭 성공: {name} -> ID {best_match_id} (유사도: {best_ratio:.2f})")
            return best_match_id

        logger.debug(f"퍼지 매칭 실패: {name} (최고 유사도: {best_ratio:.2f})")
        return None

    def match_team(
        self,
        team_name: str,
        sport: str = "soccer"
    ) -> MatchResult:
        """팀명 매칭 상세 결과 반환

        Args:
            team_name: 입력 팀명
            sport: 스포츠 종류

        Returns:
            MatchResult 객체 (원본, 정규화명, 신뢰도, 매칭방법)
        """
        mapping = self.soccer_mapping if sport == "soccer" else self.basketball_mapping
        reverse_mapping = (
            self._soccer_reverse_mapping
            if sport == "soccer"
            else self._basketball_reverse_mapping
        )

        team_name_lower = team_name.lower()

        # 1. 정확한 매칭
        if team_name in mapping:
            return MatchResult(
                original_name=team_name,
                normalized_name=team_name,
                confidence=1.0,
                method="exact"
            )

        # 2. 역방향 매핑 (별칭 매칭)
        if team_name_lower in reverse_mapping:
            normalized = reverse_mapping[team_name_lower]
            return MatchResult(
                original_name=team_name,
                normalized_name=normalized,
                confidence=0.95,
                method="alias"
            )

        # 3. 퍼지 매칭
        normalized = self.get_normalized_name(team_name, sport)
        if normalized:
            # 유사도 재계산
            best_ratio = 0.0
            for check_name in [normalized] + mapping.get(normalized, {}).get("aliases", []):
                ratio = SequenceMatcher(None, team_name_lower, check_name.lower()).ratio()
                best_ratio = max(best_ratio, ratio)

            return MatchResult(
                original_name=team_name,
                normalized_name=normalized,
                confidence=best_ratio,
                method="fuzzy"
            )

        # 4. 매칭 실패
        return MatchResult(
            original_name=team_name,
            normalized_name="",
            confidence=0.0,
            method="none"
        )

    def get_team_info(
        self,
        team_name: str,
        sport: str = "soccer"
    ) -> Optional[Dict[str, Any]]:
        """팀 전체 정보 조회

        Args:
            team_name: 팀명
            sport: 스포츠 종류

        Returns:
            팀 정보 딕셔너리 또는 None
        """
        normalized = self.get_normalized_name(team_name, sport)
        if not normalized:
            return None

        mapping = self.soccer_mapping if sport == "soccer" else self.basketball_mapping
        return mapping.get(normalized)

    def get_all_teams(self, sport: str = "soccer") -> List[str]:
        """모든 정규화된 팀명 목록 반환

        Args:
            sport: 스포츠 종류

        Returns:
            팀명 리스트
        """
        mapping = self.soccer_mapping if sport == "soccer" else self.basketball_mapping
        return list(mapping.keys())

    def get_teams_by_league(self, league: str, sport: str = "soccer") -> List[str]:
        """특정 리그의 팀 목록 반환

        Args:
            league: 리그명 (예: "Premier League", "NBA", "KBL")
            sport: 스포츠 종류

        Returns:
            해당 리그의 팀명 리스트
        """
        mapping = self.soccer_mapping if sport == "soccer" else self.basketball_mapping
        return [
            team_name
            for team_name, data in mapping.items()
            if data.get("league") == league
        ]


# =============================================================================
# 전역 인스턴스
# =============================================================================

team_mapper = TeamMapper()


# =============================================================================
# 테스트 함수
# =============================================================================

def test_team_mapper():
    """TeamMapper 테스트"""
    mapper = TeamMapper()

    print("=" * 70)
    print("TeamMapper 테스트")
    print("=" * 70)

    # 축구 팀 테스트
    print("\n[1] 축구 팀 API ID 조회 테스트")
    print("-" * 50)
    soccer_tests = [
        ("맨시티", "api_football", 50),
        ("맨체스터시티", "api_football", 50),
        ("Manchester City", "api_football", 50),
        ("리버풀", "api_football", 40),
        ("레스터C", "api_football", 46),
        ("코모1907", "api_football", 867),
    ]

    for team_name, api, expected_id in soccer_tests:
        result = mapper.get_api_id(team_name, api=api, sport="soccer")
        status = "O" if result == expected_id else "X"
        print(f"  [{status}] {team_name:20} -> {result} (예상: {expected_id})")

    # 농구 팀 테스트
    print("\n[2] 농구 팀 API ID 조회 테스트")
    print("-" * 50)
    basketball_tests = [
        ("LA레이커스", "api_basketball", 145),
        ("로스앤젤레스레이커스", "api_basketball", 145),
        ("울산모비스", "kbl", "01"),
        ("울산현대모비스피버스", "kbl", "01"),
    ]

    for team_name, api, expected_id in basketball_tests:
        result = mapper.get_api_id(team_name, api=api, sport="basketball")
        status = "O" if result == expected_id else "X"
        print(f"  [{status}] {team_name:25} -> {result} (예상: {expected_id})")

    # 정규화 테스트
    print("\n[3] 팀명 정규화 테스트")
    print("-" * 50)
    normalize_tests = [
        ("맨체스터시티", "soccer", "맨시티"),
        ("Manchester City", "soccer", "맨시티"),
        ("Man City", "soccer", "맨시티"),
        ("울산현대모비스피버스", "basketball", "울산모비스"),
        ("LA 레이커스", "basketball", "LA레이커스"),
    ]

    for team_name, sport, expected in normalize_tests:
        result = mapper.get_normalized_name(team_name, sport=sport)
        status = "O" if result == expected else "X"
        print(f"  [{status}] {team_name:25} -> {result} (예상: {expected})")

    # 퍼지 매칭 테스트
    print("\n[4] 퍼지 매칭 테스트")
    print("-" * 50)
    fuzzy_tests = [
        ("맨체스터 시티", "soccer"),
        ("아스톤빌라", "soccer"),
        ("노팅엄포레스트", "soccer"),
        ("골든스테이트워리어스", "basketball"),
    ]

    for team_name, sport in fuzzy_tests:
        result = mapper.match_team(team_name, sport=sport)
        status = "O" if result.confidence >= 0.6 else "X"
        print(f"  [{status}] {team_name:25} -> {result.normalized_name} ({result.method}, {result.confidence:.2f})")

    # 리그별 팀 조회
    print("\n[5] 리그별 팀 조회 테스트")
    print("-" * 50)
    for league in ["Premier League", "Serie A", "NBA", "KBL"]:
        sport = "basketball" if league in ["NBA", "KBL"] else "soccer"
        teams = mapper.get_teams_by_league(league, sport=sport)
        print(f"  {league}: {len(teams)}팀")

    print("\n" + "=" * 70)
    print("테스트 완료")
    print("=" * 70)


if __name__ == "__main__":
    test_team_mapper()
