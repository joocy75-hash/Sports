"""
팀명 정규화 모듈 - 베트맨 ↔ KSPO API 팀명 매칭

베트맨 웹사이트와 KSPO API의 팀명 형식이 다름:
- 베트맨: "레스터C", "맨체스U", "A빌라"
- KSPO API: "레스터시티", "맨체스터유나이티드", "아스톤빌라"

이 모듈은 두 시스템 간의 팀명을 매칭합니다.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple


@dataclass
class MatchResult:
    """팀명 매칭 결과"""
    betman_name: str
    api_name: str
    confidence: float
    method: str  # "exact", "mapping", "fuzzy"


class TeamNameNormalizer:
    """팀명 정규화 클래스"""

    # 베트맨 → KSPO API 매핑 (축약형 → 정식명칭)
    TEAM_MAPPINGS: Dict[str, List[str]] = {
        # 영국 프리미어리그
        "레스터C": ["레스터시티", "레스터", "레스터 시티"],
        "맨체스U": ["맨체스터유나이티드", "맨유", "맨체스터 유나이티드"],
        "맨체스C": ["맨체스터시티", "맨시티", "맨체스터 시티"],
        "노팅엄포": ["노팅엄포리스트", "노팅엄", "노팅엄 포리스트"],
        "A빌라": ["아스톤빌라", "아스톤 빌라", "빌라"],
        "크리스탈P": ["크리스탈팰리스", "크리스탈 팰리스", "팰리스"],
        "뉴캐슬U": ["뉴캐슬유나이티드", "뉴캐슬", "뉴캐슬 유나이티드"],
        "웨스트햄U": ["웨스트햄유나이티드", "웨스트햄", "웨스트햄 유나이티드"],
        "토트넘H": ["토트넘홋스퍼", "토트넘", "스퍼스"],
        "브라이튼H": ["브라이튼호브알비온", "브라이튼", "브라이튼 호브 알비온"],
        "울버햄튼W": ["울버햄튼원더러스", "울브스", "울버햄튼"],
        "입스위치T": ["입스위치타운", "입스위치", "입스위치 타운"],
        "사우샘프턴": ["사우샘프턴FC", "사우샘프턴", "세인츠"],

        # 영국 챔피언십
        "노리치C": ["노리치시티", "노리치", "노리치 시티"],
        "셰필드U": ["셰필드유나이티드", "셰필드", "셰필드 유나이티드"],
        "셰필드W": ["셰필드웬즈데이", "셰필드 웬즈데이"],
        "더비카운": ["더비카운티", "더비", "더비 카운티"],
        "스토크C": ["스토크시티", "스토크", "스토크 시티"],
        "스완지C": ["스완지시티", "스완지", "스완지 시티"],
        "카디프C": ["카디프시티", "카디프", "카디프 시티"],
        "브리스틀C": ["브리스틀시티", "브리스틀", "브리스틀 시티"],
        "코번트리C": ["코번트리시티", "코번트리", "코번트리 시티"],
        "버밍엄C": ["버밍엄시티", "버밍엄", "버밍엄 시티"],
        "헐C": ["헐시티", "헐", "헐 시티"],
        "리즈U": ["리즈유나이티드", "리즈", "리즈 유나이티드"],
        "QPR": ["퀸즈파크레인저스", "퀸즈 파크 레인저스"],
        "WBA": ["웨스트브로미치앨비언", "웨스트브롬", "웨스트 브로미치"],
        "플리머스A": ["플리머스아가일", "플리머스", "플리머스 아가일"],
        "옥스포드U": ["옥스포드유나이티드", "옥스포드", "옥스포드 유나이티드"],
        "포츠머스": ["포츠머스FC", "포츠머스"],
        "프레스턴NE": ["프레스턴노스엔드", "프레스턴", "프레스턴 노스 엔드"],
        "밀월": ["밀월FC", "밀월"],
        "루턴T": ["루턴타운", "루턴", "루턴 타운"],

        # KBO 야구
        "삼성": ["삼성라이온즈", "삼성 라이온즈"],
        "롯데": ["롯데자이언츠", "롯데 자이언츠"],
        "두산": ["두산베어스", "두산 베어스"],
        "LG": ["LG트윈스", "LG 트윈스"],
        "KIA": ["KIA타이거즈", "KIA 타이거즈"],
        "KT": ["KT위즈", "KT 위즈"],
        "NC": ["NC다이노스", "NC 다이노스"],
        "SSG": ["SSG랜더스", "SSG 랜더스"],
        "키움": ["키움히어로즈", "키움 히어로즈"],
        "한화": ["한화이글스", "한화 이글스"],

        # KBL 농구
        "울산모비스": ["울산현대모비스피버스", "울산현대모비스", "울산 현대모비스"],
        "서울삼성": ["서울삼성썬더스", "서울 삼성 썬더스", "삼성썬더스"],
        "원주DB": ["원주DB프로미", "원주 DB 프로미", "DB프로미"],
        "안양KGC": ["안양KGC인삼공사", "안양 KGC", "KGC인삼공사"],
        "고양소노": ["고양소노스카이거너스", "고양 소노", "소노스카이거너스"],
        "부산KCC": ["부산KCC이지스", "부산 KCC", "KCC이지스"],
        "대구한국가스": ["대구한국가스공사", "대구 한국가스공사", "한국가스공사"],
        "서울SK": ["서울SK나이츠", "서울 SK", "SK나이츠"],
        "수원KT": ["수원KT소닉붐", "수원 KT", "KT소닉붐"],
        "창원LG": ["창원LG세이커스", "창원 LG", "LG세이커스"],

        # NBA 농구
        "미네소타": ["미네소타팀버울브스", "미네소타 팀버울브스", "팀버울브스"],
        "LA레이커스": ["로스앤젤레스레이커스", "LA 레이커스", "레이커스"],
        "LA클리퍼스": ["로스앤젤레스클리퍼스", "LA 클리퍼스", "클리퍼스"],
        "골든스테이트": ["골든스테이트워리어스", "골든스테이트 워리어스", "워리어스"],
        "샌안토니오": ["샌안토니오스퍼스", "샌안토니오 스퍼스", "스퍼스"],
        "뉴올리언스": ["뉴올리언스펠리컨스", "뉴올리언스 펠리컨스", "펠리컨스"],
        "오클라호마시티": ["오클라호마시티썬더", "오클라호마시티 썬더", "썬더"],
        "포틀랜드": ["포틀랜드트레일블레이저스", "포틀랜드 트레일블레이저스", "블레이저스"],
        "유타": ["유타재즈", "유타 재즈", "재즈"],
        "덴버": ["덴버너겟츠", "덴버 너겟츠", "너겟츠"],
        "피닉스": ["피닉스선즈", "피닉스 선즈", "선즈"],
        "새크라멘토": ["새크라멘토킹스", "새크라멘토 킹스", "킹스"],
        "시카고": ["시카고불스", "시카고 불스", "불스"],
        "클리블랜드": ["클리블랜드캐벌리어스", "클리블랜드 캐벌리어스", "캐벌리어스"],
        "디트로이트": ["디트로이트피스톤스", "디트로이트 피스톤스", "피스톤스"],
        "인디애나": ["인디애나페이서스", "인디애나 페이서스", "페이서스"],
        "밀워키": ["밀워키벅스", "밀워키 벅스", "벅스"],
        "애틀랜타": ["애틀랜타호크스", "애틀랜타 호크스", "호크스"],
        "샬럿": ["샬럿호네츠", "샬럿 호네츠", "호네츠"],
        "마이애미": ["마이애미히트", "마이애미 히트", "히트"],
        "올랜도": ["올랜도매직", "올랜도 매직", "매직"],
        "워싱턴": ["워싱턴위저즈", "워싱턴 위저즈", "위저즈"],
        "보스턴": ["보스턴셀틱스", "보스턴 셀틱스", "셀틱스"],
        "브루클린": ["브루클린네츠", "브루클린 네츠", "네츠"],
        "뉴욕": ["뉴욕닉스", "뉴욕 닉스", "닉스"],
        "필라델피아": ["필라델피아세븐티식서스", "필라델피아 76ers", "식서스"],
        "토론토": ["토론토랩터스", "토론토 랩터스", "랩터스"],
        "댈러스": ["댈러스매버릭스", "댈러스 매버릭스", "매버릭스"],
        "휴스턴": ["휴스턴로케츠", "휴스턴 로케츠", "로케츠"],
        "멤피스": ["멤피스그리즐리스", "멤피스 그리즐리스", "그리즐리스"],
    }

    def __init__(self):
        # 역방향 매핑 생성 (API명 → 베트맨명)
        self.reverse_mapping: Dict[str, str] = {}
        for betman_name, api_names in self.TEAM_MAPPINGS.items():
            for api_name in api_names:
                self.reverse_mapping[api_name.lower()] = betman_name

    def normalize(self, team_name: str) -> str:
        """팀명 정규화 (공백/특수문자 제거, 소문자 변환)"""
        if not team_name:
            return ""
        return team_name.strip().lower().replace(" ", "").replace(".", "")

    def match_team(self, betman_name: str, api_name: str) -> MatchResult:
        """
        베트맨 팀명과 KSPO API 팀명 매칭

        Returns:
            MatchResult: 매칭 결과 (confidence 0.0~1.0)
        """
        # 1. 정확히 일치
        if self.normalize(betman_name) == self.normalize(api_name):
            return MatchResult(betman_name, api_name, 1.0, "exact")

        # 2. 매핑 테이블에서 찾기
        if betman_name in self.TEAM_MAPPINGS:
            for mapped_name in self.TEAM_MAPPINGS[betman_name]:
                if self.normalize(mapped_name) == self.normalize(api_name):
                    return MatchResult(betman_name, api_name, 0.95, "mapping")

        # 3. 역방향 매핑 확인
        normalized_api = self.normalize(api_name)
        if normalized_api in self.reverse_mapping:
            if self.reverse_mapping[normalized_api] == betman_name:
                return MatchResult(betman_name, api_name, 0.95, "mapping")

        # 4. 부분 문자열 매칭
        norm_betman = self.normalize(betman_name)
        norm_api = self.normalize(api_name)
        if norm_betman in norm_api or norm_api in norm_betman:
            return MatchResult(betman_name, api_name, 0.8, "substring")

        # 5. Fuzzy 매칭 (difflib)
        ratio = SequenceMatcher(None, norm_betman, norm_api).ratio()
        if ratio >= 0.6:
            return MatchResult(betman_name, api_name, ratio, "fuzzy")

        return MatchResult(betman_name, api_name, 0.0, "none")

    def find_best_match(
        self,
        betman_name: str,
        api_teams: List[str]
    ) -> Optional[Tuple[str, MatchResult]]:
        """
        베트맨 팀명에 가장 잘 맞는 API 팀명 찾기

        Args:
            betman_name: 베트맨 팀명
            api_teams: KSPO API 팀명 리스트

        Returns:
            (api_team, MatchResult) 또는 None
        """
        best_match = None
        best_result = None

        for api_team in api_teams:
            result = self.match_team(betman_name, api_team)
            if result.confidence > 0 and (best_result is None or result.confidence > best_result.confidence):
                best_match = api_team
                best_result = result

        if best_match and best_result and best_result.confidence >= 0.6:
            return (best_match, best_result)

        return None

    def find_team_in_api_data(
        self,
        betman_name: str,
        api_data: List[Dict],
        home_key: str = "hteam_han_nm",
        away_key: str = "ateam_han_nm"
    ) -> Optional[Dict]:
        """
        API 데이터에서 베트맨 팀명과 매칭되는 경기 찾기

        Args:
            betman_name: 베트맨 팀명
            api_data: KSPO API 응답 리스트
            home_key: 홈팀 필드명
            away_key: 원정팀 필드명

        Returns:
            매칭된 API 데이터 또는 None
        """
        for item in api_data:
            home_team = item.get(home_key, "")
            away_team = item.get(away_key, "")

            home_result = self.match_team(betman_name, home_team)
            if home_result.confidence >= 0.6:
                return item

            away_result = self.match_team(betman_name, away_team)
            if away_result.confidence >= 0.6:
                return item

        return None

    def match_games(
        self,
        betman_games: List[Dict],
        api_games: List[Dict]
    ) -> List[Tuple[Dict, Optional[Dict], float]]:
        """
        베트맨 경기 리스트와 API 경기 리스트 매칭

        Returns:
            List[(betman_game, api_game or None, confidence)]
        """
        results = []
        used_api_matches = set()

        for betman_game in betman_games:
            home = betman_game.get("home_team", "")
            away = betman_game.get("away_team", "")

            best_api_game = None
            best_score = 0.0

            for i, api_game in enumerate(api_games):
                if i in used_api_matches:
                    continue

                api_home = api_game.get("hteam_han_nm", "")
                api_away = api_game.get("ateam_han_nm", "")

                home_result = self.match_team(home, api_home)
                away_result = self.match_team(away, api_away)

                if home_result.confidence >= 0.6 and away_result.confidence >= 0.6:
                    combined = (home_result.confidence + away_result.confidence) / 2
                    if combined > best_score:
                        best_score = combined
                        best_api_game = (i, api_game)

            if best_api_game:
                used_api_matches.add(best_api_game[0])
                results.append((betman_game, best_api_game[1], best_score))
            else:
                results.append((betman_game, None, 0.0))

        return results


# 전역 인스턴스
team_normalizer = TeamNameNormalizer()


# 테스트
def test_team_normalizer():
    """팀명 정규화 테스트"""
    normalizer = TeamNameNormalizer()

    test_cases = [
        ("레스터C", "레스터시티"),
        ("맨체스U", "맨체스터유나이티드"),
        ("노팅엄포", "노팅엄포리스트"),
        ("울산모비스", "울산현대모비스피버스"),
        ("미네소타", "미네소타팀버울브스"),
        ("A빌라", "아스톤빌라"),
        ("크리스탈P", "크리스탈팰리스"),
    ]

    print("=" * 60)
    print("팀명 정규화 테스트")
    print("=" * 60)

    for betman, api in test_cases:
        result = normalizer.match_team(betman, api)
        status = "O" if result.confidence >= 0.6 else "X"
        print(f"  [{status}] {betman:15} <-> {api:20} ({result.method}, {result.confidence:.2f})")


if __name__ == "__main__":
    test_team_normalizer()
