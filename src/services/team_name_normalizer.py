"""
팀명 정규화 모듈 - 베트맨 ↔ KSPO API 팀명 매칭

베트맨 웹사이트와 KSPO API의 팀명 형식이 다름:
- 베트맨: "레스터C", "맨체스U", "A빌라"
- KSPO API: "레스터시티", "맨체스터유나이티드", "아스톤빌라"

팀 매핑은 config/teams.yaml에서 관리됩니다.
새 팀 추가 시 YAML 파일만 수정하면 됩니다.
"""

import logging
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    betman_name: str
    api_name: str
    confidence: float
    method: str


class TeamNameNormalizer:
    
    def __init__(self):
        self.team_mappings = self._load_team_mappings()
        self.reverse_mapping = self._build_reverse_mapping()
    
    def _load_team_mappings(self) -> Dict[str, List[str]]:
        try:
            from src.config.yaml_loader import yaml_loader
            mappings = yaml_loader.get_team_mappings()
            if mappings:
                logger.debug(f"YAML에서 {len(mappings)}개 팀 매핑 로드")
                return mappings
        except ImportError:
            logger.warning("yaml_loader를 import할 수 없음, fallback 매핑 사용")
        except Exception as e:
            logger.warning(f"YAML 로드 실패: {e}, fallback 매핑 사용")
        
        return self._get_fallback_mappings()
    
    def _get_fallback_mappings(self) -> Dict[str, List[str]]:
        return {
            "레스터C": ["레스터시티", "레스터"],
            "맨체스U": ["맨체스터유나이티드", "맨유"],
            "맨체스C": ["맨체스터시티", "맨시티"],
            "A빌라": ["아스톤빌라", "빌라"],
            "울산모비스": ["울산현대모비스피버스", "울산현대모비스"],
            "미네소타": ["미네소타팀버울브스", "팀버울브스"],
        }
    
    def _build_reverse_mapping(self) -> Dict[str, str]:
        reverse = {}
        for betman_name, api_names in self.team_mappings.items():
            for api_name in api_names:
                reverse[api_name.lower()] = betman_name
        return reverse

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
        if self.normalize(betman_name) == self.normalize(api_name):
            return MatchResult(betman_name, api_name, 1.0, "exact")

        if betman_name in self.team_mappings:
            for mapped_name in self.team_mappings[betman_name]:
                if self.normalize(mapped_name) == self.normalize(api_name):
                    return MatchResult(betman_name, api_name, 0.95, "mapping")

        normalized_api = self.normalize(api_name)
        if normalized_api in self.reverse_mapping:
            if self.reverse_mapping[normalized_api] == betman_name:
                return MatchResult(betman_name, api_name, 0.95, "mapping")

        norm_betman = self.normalize(betman_name)
        norm_api = self.normalize(api_name)
        if norm_betman in norm_api or norm_api in norm_betman:
            return MatchResult(betman_name, api_name, 0.8, "substring")

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
