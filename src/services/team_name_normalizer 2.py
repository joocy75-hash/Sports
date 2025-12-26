"""
팀명 정규화 모듈

베트맨 팀명과 KSPO API 팀명을 매칭하는 정규화 모듈.
- 베트맨: 축약형 (예: "레스터C", "맨체스U", "노팅엄포")
- KSPO API: 정식 명칭 (예: "레스터시티", "맨체스터유나이티드", "노팅엄포리스트")

사용 예시:
    from src.services.team_name_normalizer import team_normalizer

    result = team_normalizer.match_team("레스터C", "레스터시티")
    print(f"신뢰도: {result.confidence:.2f}")  # 0.95
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import difflib
import re


@dataclass
class TeamMatchResult:
    """팀명 매칭 결과"""
    betman_name: str      # 베트맨 팀명
    matched_name: str     # 매칭된 팀명 (정규화)
    confidence: float     # 매칭 신뢰도 (0.0 ~ 1.0)
    match_type: str       # "exact" | "mapping" | "fuzzy" | "none"


class TeamNameNormalizer:
    """팀명 정규화 및 매칭"""

    # 베트맨 팀명 → KSPO API 팀명 매핑
    TEAM_NAME_MAPPING: Dict[str, List[str]] = {
        # ============================================================
        # 잉글랜드 프리미어리그
        # ============================================================
        "레스터C": ["레스터시티", "레스터 시티", "Leicester City", "Leicester"],
        "맨체스U": ["맨체스터유나이티드", "맨체스터 유나이티드", "Manchester United", "Man United", "맨유"],
        "맨체스C": ["맨체스터시티", "맨체스터 시티", "Manchester City", "Man City", "맨시티"],
        "노팅엄포": ["노팅엄포리스트", "노팅엄 포리스트", "Nottingham Forest", "Nottingham"],
        "토트넘": ["토트넘핫스퍼", "토트넘 핫스퍼", "Tottenham Hotspur", "Tottenham", "Spurs"],
        "A빌라": ["아스톤빌라", "아스톤 빌라", "Aston Villa", "Villa"],
        "뉴캐슬U": ["뉴캐슬유나이티드", "뉴캐슬 유나이티드", "Newcastle United", "Newcastle"],
        "웨스트햄": ["웨스트햄유나이티드", "웨스트햄 유나이티드", "West Ham United", "West Ham"],
        "브라이튼": ["브라이튼앤호브알비온", "브라이튼 앤 호브 알비온", "Brighton & Hove Albion", "Brighton"],
        "울브스": ["울버햄튼", "울버햄튼 원더러스", "Wolverhampton Wanderers", "Wolverhampton", "Wolves"],
        "본머스": ["AFC본머스", "AFC 본머스", "AFC Bournemouth", "Bournemouth"],
        "풀럼": ["풀럼FC", "풀럼 FC", "Fulham FC", "Fulham"],
        "리버풀": ["리버풀FC", "리버풀 FC", "Liverpool FC", "Liverpool"],
        "아스널": ["아스널FC", "아스널 FC", "Arsenal FC", "Arsenal"],
        "첼시": ["첼시FC", "첼시 FC", "Chelsea FC", "Chelsea"],
        "에버턴": ["에버턴FC", "에버턴 FC", "Everton FC", "Everton"],
        "크리스탈P": ["크리스탈팰리스", "크리스탈 팰리스", "Crystal Palace"],
        "브렌트퍼드": ["브렌트퍼드FC", "브렌트퍼드 FC", "Brentford FC", "Brentford"],
        "입스위치": ["입스위치타운", "입스위치 타운", "Ipswich Town", "Ipswich"],

        # ============================================================
        # 잉글랜드 챔피언십
        # ============================================================
        "노리치C": ["노리치시티", "노리치 시티", "Norwich City", "Norwich"],
        "왓포드": ["왓포드FC", "왓포드 FC", "Watford FC", "Watford"],
        "번리": ["번리FC", "번리 FC", "Burnley FC", "Burnley"],
        "스토크C": ["스토크시티", "스토크 시티", "Stoke City", "Stoke"],
        "미들즈브": ["미들즈브러", "미들즈브러 FC", "Middlesbrough FC", "Middlesbrough", "Boro"],
        "셰필드U": ["셰필드유나이티드", "셰필드 유나이티드", "Sheffield United", "Sheffield Utd"],
        "셰필드W": ["셰필드웬즈데이", "셰필드 웬즈데이", "Sheffield Wednesday", "Sheffield Wed"],
        "웨스트브": ["웨스트브롬위치", "웨스트 브롬위치", "West Bromwich Albion", "West Brom", "WBA"],
        "사우샘프": ["사우샘프턴", "사우스햄튼", "Southampton FC", "Southampton", "Saints"],
        "스완지C": ["스완지시티", "스완지 시티", "Swansea City", "Swansea"],
        "카디프C": ["카디프시티", "카디프 시티", "Cardiff City", "Cardiff"],
        "QPR": ["퀸즈파크레인저스", "퀸즈 파크 레인저스", "Queens Park Rangers"],
        "블랙번R": ["블랙번로버스", "블랙번 로버스", "Blackburn Rovers", "Blackburn"],
        "프레스턴": ["프레스턴노스엔드", "프레스턴 노스 엔드", "Preston North End", "Preston"],
        "더비C": ["더비카운티", "더비 카운티", "Derby County", "Derby"],
        "옥스퍼드": ["옥스퍼드유나이티드", "옥스퍼드 유나이티드", "Oxford United", "Oxford"],
        "찰턴": ["찰턴애슬레틱", "찰턴 애슬레틱", "Charlton Athletic", "Charlton"],
        "리즈U": ["리즈유나이티드", "리즈 유나이티드", "Leeds United", "Leeds"],
        "선덜랜드": ["선덜랜드AFC", "선덜랜드 AFC", "Sunderland AFC", "Sunderland"],
        "플리머스": ["플리머스아가일", "플리머스 아가일", "Plymouth Argyle", "Plymouth"],
        "밀월": ["밀월FC", "밀월 FC", "Millwall FC", "Millwall"],
        "루턴": ["루턴타운", "루턴 타운", "Luton Town", "Luton"],
        "헐C": ["헐시티", "헐 시티", "Hull City", "Hull"],
        "포츠머스": ["포츠머스FC", "포츠머스 FC", "Portsmouth FC", "Portsmouth"],
        "코번트리": ["코번트리시티", "코번트리 시티", "Coventry City", "Coventry"],
        "브리스톨C": ["브리스톨시티", "브리스톨 시티", "Bristol City", "Bristol"],

        # ============================================================
        # KBO 야구
        # ============================================================
        "삼성": ["삼성라이온즈", "삼성 라이온즈", "Samsung Lions"],
        "LG": ["LG트윈스", "LG 트윈스", "LG Twins"],
        "두산": ["두산베어스", "두산 베어스", "Doosan Bears"],
        "기아": ["기아타이거즈", "기아 타이거즈", "KIA타이거즈", "KIA 타이거즈", "Kia Tigers"],
        "NC": ["NC다이노스", "NC 다이노스", "NC Dinos"],
        "키움": ["키움히어로즈", "키움 히어로즈", "Kiwoom Heroes"],
        "SSG": ["SSG랜더스", "SSG 랜더스", "SSG Landers"],
        "롯데": ["롯데자이언츠", "롯데 자이언츠", "Lotte Giants"],
        "한화": ["한화이글스", "한화 이글스", "Hanwha Eagles"],
        "KT": ["KT위즈", "KT 위즈", "KT Wiz"],

        # ============================================================
        # KBL 농구
        # ============================================================
        "울산모비스": ["울산현대모비스", "울산 현대모비스", "울산현대모비스피버스", "울산 현대모비스 피버스", "Ulsan Mobis"],
        "수원KT": ["수원KT소닉붐", "수원 KT소닉붐", "수원KT 소닉붐", "Suwon KT"],
        "서울SK": ["서울SK나이츠", "서울 SK나이츠", "서울SK 나이츠", "Seoul SK"],
        "안양KGC": ["안양KGC인삼공사", "안양 KGC", "안양KGC 인삼공사", "Anyang KGC"],
        "창원LG": ["창원LG세이커스", "창원 LG세이커스", "창원LG 세이커스", "Changwon LG"],
        "부산KCC": ["부산KCC이지스", "부산 KCC", "부산KCC 이지스", "Busan KCC"],
        "고양소노": ["고양소노스카이썬더스", "고양 소노", "고양소노 스카이썬더스", "Goyang Sono"],
        "대구한국가스": ["대구한국가스공사", "대구 한국가스공사", "대구한국가스 공사", "Daegu Gas"],
        "서울삼성": ["서울삼성썬더스", "서울 삼성썬더스", "서울삼성 썬더스", "Seoul Samsung"],
        "원주DB": ["원주DB프로미", "원주 DB프로미", "원주DB 프로미", "Wonju DB"],

        # ============================================================
        # NBA
        # ============================================================
        "LA레이커스": ["로스앤젤레스레이커스", "LA 레이커스", "Los Angeles Lakers", "Lakers"],
        "LA클리퍼스": ["로스앤젤레스클리퍼스", "LA 클리퍼스", "Los Angeles Clippers", "Clippers"],
        "골든스테이트": ["골든스테이트워리어스", "골든스테이트 워리어스", "Golden State Warriors", "Warriors"],
        "브루클린": ["브루클린네츠", "브루클린 네츠", "Brooklyn Nets", "Nets"],
        "보스턴": ["보스턴셀틱스", "보스턴 셀틱스", "Boston Celtics", "Celtics"],
        "뉴욕닉스": ["뉴욕닉스", "뉴욕 닉스", "New York Knicks", "Knicks"],
        "필라델피아": ["필라델피아세븐티식서스", "필라델피아 세븐티식서스", "Philadelphia 76ers", "76ers", "Sixers"],
        "마이애미": ["마이애미히트", "마이애미 히트", "Miami Heat", "Heat"],
        "밀워키": ["밀워키벅스", "밀워키 벅스", "Milwaukee Bucks", "Bucks"],
        "덴버": ["덴버너겟츠", "덴버 너겟츠", "Denver Nuggets", "Nuggets"],
        "피닉스": ["피닉스선즈", "피닉스 선즈", "Phoenix Suns", "Suns"],
        "댈러스": ["댈러스매버릭스", "댈러스 매버릭스", "Dallas Mavericks", "Mavericks", "Mavs"],
        "휴스턴": ["휴스턴로켓츠", "휴스턴 로켓츠", "Houston Rockets", "Rockets"],
        "미네소타": ["미네소타팀버울브스", "미네소타 팀버울브스", "Minnesota Timberwolves", "Timberwolves", "Wolves"],
        "클리블랜드": ["클리블랜드캐벌리어스", "클리블랜드 캐벌리어스", "Cleveland Cavaliers", "Cavaliers", "Cavs"],
        "토론토": ["토론토랩터스", "토론토 랩터스", "Toronto Raptors", "Raptors"],
        "샬럿": ["샬럿호네츠", "샬럿 호네츠", "Charlotte Hornets", "Hornets"],
        "애틀랜타": ["애틀랜타호크스", "애틀랜타 호크스", "Atlanta Hawks", "Hawks"],
        "시카고": ["시카고불스", "시카고 불스", "Chicago Bulls", "Bulls"],
        "인디애나": ["인디애나페이서스", "인디애나 페이서스", "Indiana Pacers", "Pacers"],
        "디트로이트": ["디트로이트피스톤스", "디트로이트 피스톤스", "Detroit Pistons", "Pistons"],
        "워싱턴": ["워싱턴위저즈", "워싱턴 위저즈", "Washington Wizards", "Wizards"],
        "올랜도": ["올랜도매직", "올랜도 매직", "Orlando Magic", "Magic"],
        "포틀랜드": ["포틀랜드트레일블레이저스", "포틀랜드 트레일블레이저스", "Portland Trail Blazers", "Blazers"],
        "유타": ["유타재즈", "유타 재즈", "Utah Jazz", "Jazz"],
        "오클라호마": ["오클라호마시티썬더", "오클라호마시티 썬더", "Oklahoma City Thunder", "Thunder", "OKC"],
        "멤피스": ["멤피스그리즐리스", "멤피스 그리즐리스", "Memphis Grizzlies", "Grizzlies"],
        "새크라멘토": ["새크라멘토킹스", "새크라멘토 킹스", "Sacramento Kings", "Kings"],
        "뉴올리언스": ["뉴올리언스펠리컨스", "뉴올리언스 펠리컨스", "New Orleans Pelicans", "Pelicans"],
        "샌안토니오": ["샌안토니오스퍼스", "샌안토니오 스퍼스", "San Antonio Spurs", "Spurs"],
    }

    def __init__(self):
        """초기화: 역방향 매핑 생성"""
        # 역방향 매핑 (정규화된 이름 → 베트맨 이름)
        self._reverse_mapping: Dict[str, str] = {}
        for betman_name, variants in self.TEAM_NAME_MAPPING.items():
            for variant in variants:
                self._reverse_mapping[self._normalize_string(variant)] = betman_name

    def _normalize_string(self, s: str) -> str:
        """
        문자열 정규화 (공백/특수문자 제거, 소문자)

        Args:
            s: 정규화할 문자열

        Returns:
            정규화된 문자열

        Example:
            >>> self._normalize_string("레스터 시티")
            'leicestersiti'
            >>> self._normalize_string("Manchester United")
            'manchesterunited'
        """
        return re.sub(r'[^가-힣a-zA-Z0-9]', '', s).lower()

    def normalize(self, team_name: str) -> str:
        """
        팀명을 표준 형식(베트맨 형식)으로 정규화

        Args:
            team_name: 정규화할 팀명

        Returns:
            정규화된 팀명 (베트맨 형식)

        Example:
            >>> normalizer.normalize("레스터시티")
            '레스터C'
            >>> normalizer.normalize("맨체스터유나이티드")
            '맨체스U'
        """
        normalized = self._normalize_string(team_name)

        # 1. 역방향 매핑에서 찾기 (정식 명칭 → 베트맨 명칭)
        if normalized in self._reverse_mapping:
            return self._reverse_mapping[normalized]

        # 2. 베트맨 매핑 키에서 찾기 (이미 베트맨 형식인 경우)
        for key in self.TEAM_NAME_MAPPING:
            if self._normalize_string(key) == normalized:
                return key

        # 3. 매핑을 못 찾으면 원본 반환
        return team_name

    def match_team(self, betman_name: str, api_name: str) -> TeamMatchResult:
        """
        베트맨 팀명과 KSPO API 팀명 매칭

        Args:
            betman_name: 베트맨 팀명 (축약형)
            api_name: KSPO API 팀명 (정식 명칭)

        Returns:
            TeamMatchResult: 매칭 결과 (신뢰도 포함)

        Example:
            >>> result = normalizer.match_team("레스터C", "레스터시티")
            >>> print(f"{result.match_type}: {result.confidence:.2f}")
            mapping: 0.95
        """
        # 1. 정확히 일치
        if betman_name == api_name:
            return TeamMatchResult(
                betman_name=betman_name,
                matched_name=api_name,
                confidence=1.0,
                match_type="exact"
            )

        # 2. 매핑 테이블 확인
        if betman_name in self.TEAM_NAME_MAPPING:
            variants = self.TEAM_NAME_MAPPING[betman_name]
            for variant in variants:
                if self._normalize_string(variant) == self._normalize_string(api_name):
                    return TeamMatchResult(
                        betman_name=betman_name,
                        matched_name=api_name,
                        confidence=0.95,
                        match_type="mapping"
                    )

        # 3. 퍼지 매칭 (유사도 기반)
        normalized_betman = self._normalize_string(betman_name)
        normalized_api = self._normalize_string(api_name)

        ratio = difflib.SequenceMatcher(None, normalized_betman, normalized_api).ratio()

        if ratio >= 0.6:
            return TeamMatchResult(
                betman_name=betman_name,
                matched_name=api_name,
                confidence=ratio,
                match_type="fuzzy"
            )

        # 4. 매칭 실패
        return TeamMatchResult(
            betman_name=betman_name,
            matched_name="",
            confidence=0.0,
            match_type="none"
        )

    def find_team_in_api_data(
        self,
        target_team: str,
        api_matches: List[Dict],
        team_field: str = "hteam_han_nm"
    ) -> Optional[Dict]:
        """
        API 데이터에서 해당 팀이 참여한 경기 찾기

        Args:
            target_team: 찾을 팀명 (베트맨 형식)
            api_matches: API 경기 목록
            team_field: 팀명 필드 ("hteam_han_nm" 또는 "ateam_han_nm")

        Returns:
            매칭된 경기 딕셔너리 또는 None

        Example:
            >>> match = normalizer.find_team_in_api_data(
            ...     "레스터C",
            ...     api_matches,
            ...     team_field="hteam_han_nm"
            ... )
        """
        best_match = None
        best_confidence = 0.0

        for match in api_matches:
            api_team = match.get(team_field, "")
            result = self.match_team(target_team, api_team)

            if result.confidence > best_confidence:
                best_confidence = result.confidence
                best_match = match

        return best_match if best_confidence >= 0.6 else None

    def match_games(
        self,
        betman_games: List[Dict],
        api_matches: List[Dict]
    ) -> List[Tuple[Dict, Optional[Dict], float]]:
        """
        베트맨 경기와 API 경기 매칭

        Args:
            betman_games: 베트맨 경기 목록 (예측)
                예: [{"home_team": "레스터C", "away_team": "왓포드"}, ...]
            api_matches: KSPO API 경기 목록 (결과)
                예: [{"hteam_han_nm": "레스터시티", "ateam_han_nm": "왓포드FC"}, ...]

        Returns:
            List[(betman_game, api_match, confidence)]: 매칭 결과
                - betman_game: 베트맨 경기 정보
                - api_match: 매칭된 API 경기 (없으면 None)
                - confidence: 매칭 신뢰도 (0.0 ~ 1.0)

        Example:
            >>> results = normalizer.match_games(betman_games, api_matches)
            >>> for betman, api, conf in results:
            ...     if api:
            ...         print(f"{betman['home_team']} vs {betman['away_team']} → {conf:.2f}")
        """
        results = []
        used_api_matches = set()

        for betman_game in betman_games:
            # 팀명 필드 이름이 다를 수 있으므로 여러 경우 처리
            home_team = betman_game.get("home_team") or betman_game.get("hteam_han_nm", "")
            away_team = betman_game.get("away_team") or betman_game.get("ateam_han_nm", "")

            best_api_match = None
            best_score = 0.0

            for i, api_match in enumerate(api_matches):
                if i in used_api_matches:
                    continue

                api_home = api_match.get("hteam_han_nm", "")
                api_away = api_match.get("ateam_han_nm", "")

                # 홈팀과 원정팀 모두 매칭
                home_result = self.match_team(home_team, api_home)
                away_result = self.match_team(away_team, api_away)

                # 양팀 모두 매칭되어야 함 (신뢰도 60% 이상)
                if home_result.confidence >= 0.6 and away_result.confidence >= 0.6:
                    combined_score = (home_result.confidence + away_result.confidence) / 2
                    if combined_score > best_score:
                        best_score = combined_score
                        best_api_match = (i, api_match)

            if best_api_match:
                used_api_matches.add(best_api_match[0])
                results.append((betman_game, best_api_match[1], best_score))
            else:
                # 매칭 실패
                results.append((betman_game, None, 0.0))

        return results


# 전역 인스턴스 (다른 모듈에서 import하여 사용)
team_normalizer = TeamNameNormalizer()


def test_normalizer():
    """테스트 함수"""
    normalizer = TeamNameNormalizer()

    # 테스트 케이스
    test_cases = [
        # 축구
        ("레스터C", "레스터시티"),
        ("맨체스U", "맨체스터유나이티드"),
        ("노팅엄포", "노팅엄포리스트"),
        ("A빌라", "아스톤빌라"),
        ("웨스트햄", "웨스트햄유나이티드"),
        ("노리치C", "노리치시티"),
        ("스토크C", "스토크시티"),
        ("블랙번R", "블랙번로버스"),

        # 농구 (KBL)
        ("울산모비스", "울산현대모비스피버스"),
        ("수원KT", "수원KT소닉붐"),
        ("창원LG", "창원LG세이커스"),

        # 농구 (NBA)
        ("미네소타", "미네소타팀버울브스"),
        ("LA레이커스", "로스앤젤레스레이커스"),
        ("골든스테이트", "골든스테이트워리어스"),

        # 야구
        ("기아", "KIA타이거즈"),
        ("삼성", "삼성라이온즈"),
    ]

    print("=" * 80)
    print("팀명 매칭 테스트")
    print("=" * 80)
    print(f"{'베트맨 팀명':<20} {'API 팀명':<30} {'매칭 타입':<10} {'신뢰도':<10}")
    print("-" * 80)

    for betman, api in test_cases:
        result = normalizer.match_team(betman, api)
        print(f"{betman:<20} {api:<30} {result.match_type:<10} {result.confidence:>6.2f}")

    print("=" * 80)
    print("\n정규화 테스트 (API 팀명 → 베트맨 팀명)")
    print("=" * 80)

    api_names = [
        "레스터시티",
        "맨체스터유나이티드",
        "울산현대모비스피버스",
        "미네소타팀버울브스",
    ]

    for api_name in api_names:
        normalized = normalizer.normalize(api_name)
        print(f"{api_name:<30} → {normalized}")

    print("=" * 80)


def test_match_games():
    """경기 매칭 테스트"""
    normalizer = TeamNameNormalizer()

    # 베트맨 경기 (예측)
    betman_games = [
        {"home_team": "레스터C", "away_team": "왓포드"},
        {"home_team": "노리치C", "away_team": "찰턴"},
        {"home_team": "울산모비스", "away_team": "수원KT"},
    ]

    # API 경기 (결과)
    api_matches = [
        {"hteam_han_nm": "레스터시티", "ateam_han_nm": "왓포드FC", "result": "W"},
        {"hteam_han_nm": "노리치시티", "ateam_han_nm": "찰턴애슬레틱", "result": "D"},
        {"hteam_han_nm": "울산현대모비스피버스", "ateam_han_nm": "수원KT소닉붐", "result": "W"},
    ]

    print("\n경기 매칭 테스트")
    print("=" * 80)

    results = normalizer.match_games(betman_games, api_matches)

    for betman_game, api_match, confidence in results:
        home = betman_game.get("home_team", "")
        away = betman_game.get("away_team", "")

        if api_match:
            api_home = api_match.get("hteam_han_nm", "")
            api_away = api_match.get("ateam_han_nm", "")
            result = api_match.get("result", "")
            print(f"{home} vs {away}")
            print(f"  ↔ {api_home} vs {api_away} (결과: {result})")
            print(f"  신뢰도: {confidence:.2f}")
        else:
            print(f"{home} vs {away}")
            print(f"  ↔ 매칭 실패")
        print()

    print("=" * 80)


if __name__ == "__main__":
    test_normalizer()
    test_match_games()
