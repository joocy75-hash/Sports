"""
YAML 설정 파일 로더

config/ 디렉토리의 YAML 파일을 로드하고 캐싱합니다.
팀 매핑, 리그 설정 등을 코드 수정 없이 변경 가능하게 합니다.

사용법:
    from src.config.yaml_loader import yaml_loader
    
    # 팀 매핑 로드
    mappings = yaml_loader.get_team_mappings()
    # {"레스터C": ["레스터시티", ...], "맨체스U": [...], ...}
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.warning("PyYAML이 설치되지 않음. pip install pyyaml 실행 필요")


class YAMLLoader:
    """
    YAML 설정 로더 (싱글톤 패턴)
    
    Features:
    - 파일 캐싱으로 반복 로드 방지
    - 파일 없거나 파싱 오류 시 graceful fallback
    - 동적 리로드 지원 (clear_cache)
    """
    
    _instance: Optional['YAMLLoader'] = None
    _teams_cache: Optional[Dict] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 프로젝트 루트/config 디렉토리
        self.config_dir = Path(__file__).parent.parent.parent / "config"
    
    def _load_yaml_file(self, filename: str) -> Dict[str, Any]:
        """
        YAML 파일 로드 (내부 헬퍼)
        
        Args:
            filename: config/ 디렉토리 내 파일명
            
        Returns:
            파싱된 딕셔너리 (실패 시 빈 딕셔너리)
        """
        if not YAML_AVAILABLE:
            logger.error("PyYAML 미설치로 YAML 로드 불가")
            return {}
        
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            logger.warning(f"YAML 파일 없음: {file_path}")
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            logger.debug(f"YAML 로드 성공: {filename}")
            return data or {}
        except yaml.YAMLError as e:
            logger.error(f"YAML 파싱 오류 ({filename}): {e}")
            return {}
        except Exception as e:
            logger.error(f"YAML 로드 오류 ({filename}): {e}")
            return {}
    
    def load_teams(self) -> Dict[str, Dict[str, List[str]]]:
        """
        config/teams.yaml 로드
        
        Returns:
            리그별 팀 매핑 딕셔너리
            예: {
                "premier_league": {"레스터C": ["레스터시티", ...]},
                "championship": {"노리치C": ["노리치시티", ...]},
                "kbl": {"울산모비스": ["울산현대모비스피버스", ...]},
                ...
            }
        """
        if self._teams_cache is not None:
            return self._teams_cache
        
        self._teams_cache = self._load_yaml_file("teams.yaml")
        
        if self._teams_cache:
            league_count = len(self._teams_cache)
            team_count = sum(
                len(teams) for teams in self._teams_cache.values() 
                if isinstance(teams, dict)
            )
            logger.info(f"teams.yaml 로드 완료: {league_count}개 리그, {team_count}개 팀")
        
        return self._teams_cache
    
    def get_team_mappings(self) -> Dict[str, List[str]]:
        """
        리그별 매핑을 평탄화하여 반환
        
        team_name_normalizer.py에서 사용하는 형식:
        {"레스터C": ["레스터시티", ...], "맨체스U": [...], ...}
        
        Returns:
            베트맨 팀명 → KSPO API 팀명 리스트 매핑
        """
        teams_data = self.load_teams()
        flat_mappings: Dict[str, List[str]] = {}
        
        for league, mappings in teams_data.items():
            if isinstance(mappings, dict):
                for betman_name, api_names in mappings.items():
                    if isinstance(api_names, list):
                        flat_mappings[betman_name] = api_names
                    else:
                        logger.warning(f"잘못된 매핑 형식: {betman_name} -> {api_names}")
        
        return flat_mappings
    
    def get_teams_by_league(self, league: str) -> Dict[str, List[str]]:
        """
        특정 리그의 팀 매핑만 반환
        
        Args:
            league: 리그 키 (예: "premier_league", "kbl", "nba")
            
        Returns:
            해당 리그의 팀 매핑 (없으면 빈 딕셔너리)
        """
        teams_data = self.load_teams()
        return teams_data.get(league, {})
    
    def get_all_betman_names(self) -> List[str]:
        """모든 베트맨 팀명 리스트 반환"""
        return list(self.get_team_mappings().keys())
    
    def get_all_api_names(self) -> List[str]:
        """모든 KSPO API 팀명 리스트 반환 (중복 제거)"""
        all_names = []
        for api_names in self.get_team_mappings().values():
            all_names.extend(api_names)
        return list(set(all_names))
    
    def clear_cache(self):
        """
        캐시 초기화 (설정 파일 변경 시 호출)
        
        Usage:
            yaml_loader.clear_cache()
            # 다음 호출 시 파일에서 다시 로드
        """
        self._teams_cache = None
        logger.info("YAML 캐시 초기화됨")
    
    def reload(self):
        """캐시 초기화 후 즉시 리로드"""
        self.clear_cache()
        self.load_teams()


# 전역 싱글톤 인스턴스
yaml_loader = YAMLLoader()


# ==================== 테스트 ====================

def _test_yaml_loader():
    """YAML 로더 테스트"""
    print("=" * 60)
    print("YAML 로더 테스트")
    print("=" * 60)
    
    loader = YAMLLoader()
    
    # 1. 팀 매핑 로드
    teams = loader.load_teams()
    print(f"\n1. 리그 수: {len(teams)}")
    for league in teams.keys():
        team_count = len(teams[league]) if isinstance(teams[league], dict) else 0
        print(f"   - {league}: {team_count}개 팀")
    
    # 2. 평탄화된 매핑
    flat = loader.get_team_mappings()
    print(f"\n2. 총 팀 매핑 수: {len(flat)}")
    
    # 3. 샘플 출력
    print("\n3. 샘플 매핑 (5개):")
    for i, (betman, api_names) in enumerate(flat.items()):
        if i >= 5:
            break
        print(f"   {betman} → {api_names[0] if api_names else 'N/A'}")
    
    # 4. 특정 리그
    kbl = loader.get_teams_by_league("kbl")
    print(f"\n4. KBL 팀 수: {len(kbl)}")
    
    # 5. 캐시 테스트
    print("\n5. 캐시 테스트:")
    print(f"   캐시 히트 (동일 인스턴스): {loader._teams_cache is not None}")
    loader.clear_cache()
    print(f"   캐시 클리어 후: {loader._teams_cache is None}")
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    _test_yaml_loader()
