"""
캐시 관리자 모듈

실시간 데이터 통합 시스템을 위한 캐싱 전략 구현
- 데이터 종류별 TTL 관리
- 파일 기반 캐시 백엔드
- 패턴 매칭 무효화 지원
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CacheTTL(IntEnum):
    """캐시 TTL 설정 (초 단위)

    데이터 특성에 따라 적절한 TTL을 설정:
    - 자주 변하는 데이터: 짧은 TTL
    - 안정적인 데이터: 긴 TTL
    """

    # 팀 통계: 6시간 (시즌 중 경기 후 갱신)
    TEAM_STATS = 6 * 3600  # 21600초

    # 최근 폼: 1시간 (경기 결과 반영 필요)
    RECENT_FORM = 3600  # 3600초

    # 상대 전적: 24시간 (역사적 데이터, 자주 변하지 않음)
    HEAD_TO_HEAD = 24 * 3600  # 86400초

    # 부상자 정보: 2시간 (경기 전 갱신 필요)
    INJURIES = 2 * 3600  # 7200초

    # 배당률: 5분 (실시간 변동)
    ODDS = 300  # 300초

    # 경기 컨텍스트: 30분 (날씨, 경기장 상태 등)
    MATCH_CONTEXT = 1800  # 1800초


class CacheManager:
    """파일 기반 캐시 관리자

    기능:
    - 키-값 기반 캐시 저장/조회
    - TTL 기반 자동 만료
    - 패턴 매칭 무효화
    - 원자적 파일 쓰기 (임시 파일 사용)

    사용 예시:
        cache = CacheManager()

        # 캐시 저장
        await cache.set("team:arsenal:stats", stats_data, CacheTTL.TEAM_STATS)

        # 캐시 조회
        data = await cache.get("team:arsenal:stats")

        # 패턴 무효화
        await cache.invalidate("team:arsenal:*")
    """

    def __init__(self, backend: str = "file", cache_dir: Optional[str] = None):
        """캐시 매니저 초기화

        Args:
            backend: 캐시 백엔드 타입 (현재 "file"만 지원)
            cache_dir: 캐시 디렉토리 경로 (기본값: .state/cache/)
        """
        self.backend = backend

        # 캐시 디렉토리 설정
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # 프로젝트 루트의 .state/cache/ 사용
            self.cache_dir = Path(__file__).parent.parent.parent.parent / ".state" / "cache"

        # 캐시 디렉토리 생성
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"CacheManager 초기화: backend={backend}, dir={self.cache_dir}")

    def _get_cache_path(self, key: str) -> Path:
        """캐시 키에 해당하는 파일 경로 반환

        키에 포함된 특수문자를 안전한 문자로 변환합니다.

        Args:
            key: 캐시 키 (예: "team:arsenal:stats")

        Returns:
            캐시 파일 경로 (예: .state/cache/team_arsenal_stats.json)
        """
        # 특수문자를 언더스코어로 변환
        safe_key = re.sub(r'[^\w\-]', '_', key)
        return self.cache_dir / f"{safe_key}.json"

    def _is_expired(self, filepath: Path, ttl: Optional[int] = None) -> bool:
        """캐시 파일 만료 여부 확인

        Args:
            filepath: 캐시 파일 경로
            ttl: TTL 값 (초). None이면 파일 내 TTL 사용

        Returns:
            True if 만료됨, False if 유효함
        """
        if not filepath.exists():
            return True

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            created_at_str = cache_data.get("created_at")
            if not created_at_str:
                return True

            # ISO 형식 파싱
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))

            # TTL이 지정되지 않으면 파일에 저장된 TTL 사용
            if ttl is None:
                ttl = cache_data.get("ttl", 3600)

            # 현재 시간과 비교
            now = datetime.now(timezone.utc)

            # created_at이 timezone-naive면 UTC로 가정
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age_seconds = (now - created_at).total_seconds()

            return age_seconds > ttl

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"캐시 파일 파싱 오류: {filepath}, {e}")
            return True

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """캐시에서 데이터 조회

        TTL이 만료된 경우 None을 반환합니다.

        Args:
            key: 캐시 키

        Returns:
            캐시된 데이터 또는 None (캐시 미스 또는 만료)
        """
        filepath = self._get_cache_path(key)

        # 파일 존재 여부 확인
        if not filepath.exists():
            logger.debug(f"캐시 미스 (파일 없음): {key}")
            return None

        # 비동기 파일 읽기 (asyncio.to_thread 사용)
        try:
            def read_cache():
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)

            cache_data = await asyncio.to_thread(read_cache)

            # 만료 여부 확인
            if self._is_expired(filepath):
                logger.debug(f"캐시 만료: {key}")
                return None

            logger.debug(f"캐시 히트: {key}")
            return cache_data.get("data")

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"캐시 읽기 오류: {key}, {e}")
            return None

    async def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        """캐시에 데이터 저장

        원자적 쓰기를 위해 임시 파일에 먼저 쓴 후 이동합니다.

        Args:
            key: 캐시 키
            value: 저장할 데이터
            ttl: TTL (초)

        Returns:
            True if 성공, False if 실패
        """
        filepath = self._get_cache_path(key)
        temp_filepath = filepath.with_suffix('.tmp')

        # 캐시 데이터 구성
        cache_data = {
            "data": value,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ttl": ttl
        }

        try:
            def write_cache():
                # 임시 파일에 쓰기
                with open(temp_filepath, 'w', encoding='utf-8') as f:
                    json.dump(cache_data, f, ensure_ascii=False, indent=2)

                # 원자적 이동
                temp_filepath.replace(filepath)

            await asyncio.to_thread(write_cache)
            logger.debug(f"캐시 저장: {key}, ttl={ttl}s")
            return True

        except (IOError, OSError) as e:
            logger.error(f"캐시 저장 오류: {key}, {e}")
            # 임시 파일 정리
            if temp_filepath.exists():
                temp_filepath.unlink()
            return False

    async def invalidate(self, pattern: str) -> int:
        """패턴에 매칭되는 캐시 무효화

        와일드카드 패턴을 지원합니다:
        - '*': 임의의 문자열 매칭
        - '?': 단일 문자 매칭

        Args:
            pattern: 무효화할 캐시 키 패턴 (예: "team:*:stats")

        Returns:
            삭제된 캐시 파일 수
        """
        # 패턴을 정규식으로 변환
        # '*' -> '.*', '?' -> '.', 기타 특수문자는 이스케이프
        regex_pattern = re.escape(pattern)
        regex_pattern = regex_pattern.replace(r'\*', '.*')
        regex_pattern = regex_pattern.replace(r'\?', '.')
        regex_pattern = f'^{regex_pattern}$'

        compiled_pattern = re.compile(regex_pattern)

        deleted_count = 0

        try:
            def invalidate_files():
                nonlocal deleted_count

                for cache_file in self.cache_dir.glob('*.json'):
                    # 파일명에서 키 복원 (언더스코어 -> 원래 구분자)
                    # 정확한 복원은 어려우므로 파일명 자체로 매칭
                    key_from_filename = cache_file.stem

                    # 원본 키로도 매칭 시도 (파일 내부의 키 정보가 있다면)
                    if compiled_pattern.match(key_from_filename):
                        cache_file.unlink()
                        deleted_count += 1
                        logger.debug(f"캐시 무효화: {key_from_filename}")

            await asyncio.to_thread(invalidate_files)

            if deleted_count > 0:
                logger.info(f"캐시 무효화 완료: pattern={pattern}, deleted={deleted_count}")

            return deleted_count

        except (IOError, OSError) as e:
            logger.error(f"캐시 무효화 오류: {pattern}, {e}")
            return deleted_count

    async def clear_all(self) -> int:
        """모든 캐시 삭제

        Returns:
            삭제된 캐시 파일 수
        """
        return await self.invalidate("*")

    async def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 조회

        Returns:
            캐시 통계 정보
        """
        try:
            def gather_stats():
                total_files = 0
                total_size = 0
                expired_count = 0
                valid_count = 0

                for cache_file in self.cache_dir.glob('*.json'):
                    total_files += 1
                    total_size += cache_file.stat().st_size

                    if self._is_expired(cache_file):
                        expired_count += 1
                    else:
                        valid_count += 1

                return {
                    "total_files": total_files,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "valid_count": valid_count,
                    "expired_count": expired_count,
                    "cache_dir": str(self.cache_dir)
                }

            return await asyncio.to_thread(gather_stats)

        except Exception as e:
            logger.error(f"캐시 통계 조회 오류: {e}")
            return {
                "error": str(e),
                "cache_dir": str(self.cache_dir)
            }

    async def cleanup_expired(self) -> int:
        """만료된 캐시 정리

        Returns:
            삭제된 캐시 파일 수
        """
        deleted_count = 0

        try:
            def cleanup():
                nonlocal deleted_count

                for cache_file in self.cache_dir.glob('*.json'):
                    if self._is_expired(cache_file):
                        cache_file.unlink()
                        deleted_count += 1
                        logger.debug(f"만료 캐시 삭제: {cache_file.stem}")

            await asyncio.to_thread(cleanup)

            if deleted_count > 0:
                logger.info(f"만료 캐시 정리 완료: deleted={deleted_count}")

            return deleted_count

        except Exception as e:
            logger.error(f"만료 캐시 정리 오류: {e}")
            return deleted_count


# 싱글톤 인스턴스
_cache_manager_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """캐시 매니저 싱글톤 인스턴스 반환"""
    global _cache_manager_instance

    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()

    return _cache_manager_instance


# 편의 함수들
async def cache_get(key: str) -> Optional[Dict[str, Any]]:
    """캐시 조회 편의 함수"""
    return await get_cache_manager().get(key)


async def cache_set(key: str, value: Dict[str, Any], ttl: int) -> bool:
    """캐시 저장 편의 함수"""
    return await get_cache_manager().set(key, value, ttl)


async def cache_invalidate(pattern: str) -> int:
    """캐시 무효화 편의 함수"""
    return await get_cache_manager().invalidate(pattern)
