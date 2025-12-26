#!/usr/bin/env python3
"""
데이터 검증 모듈 - 베트맨 크롤러 vs KSPO API 데이터 비교

핵심 기능:
1. 두 소스 간 데이터 비교 및 불일치 감지
2. 팀명 정규화 및 유사도 기반 매칭
3. 불일치 유형 분류 및 자동 수정 제안
4. 검증 보고서 생성

사용 예시:
    validator = DataValidator()
    result = await validator.compare_sources("soccer_wdl")
    report = await validator.generate_report()
    print(report)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MismatchType(Enum):
    """불일치 유형"""
    TEAM_NAME_MISMATCH = "team_name_mismatch"  # 팀명 불일치
    GAME_COUNT_MISMATCH = "game_count_mismatch"  # 경기 수 불일치
    ORDER_MISMATCH = "order_mismatch"  # 경기 순서 불일치
    DATE_TIME_MISMATCH = "date_time_mismatch"  # 날짜/시간 불일치
    ROUND_MISMATCH = "round_mismatch"  # 회차 번호 불일치
    MISSING_GAME = "missing_game"  # 경기 누락


@dataclass
class Mismatch:
    """불일치 항목"""
    game_number: int
    mismatch_type: MismatchType
    field: str  # "home_team", "away_team", "date", "time", "round"
    crawler_value: str
    api_value: str
    similarity: float  # 0~1 유사도
    suggested_action: str  # "use_crawler", "use_api", "manual_review"
    description: str = ""  # 추가 설명

    def __str__(self):
        return (
            f"경기 {self.game_number:02d} - {self.field}: "
            f"크롤러='{self.crawler_value}' vs API='{self.api_value}' "
            f"(유사도: {self.similarity:.1%}, 권장: {self.suggested_action})"
        )


@dataclass
class ValidationResult:
    """검증 결과"""
    is_valid: bool  # 100% 일치 여부
    match_rate: float  # 일치율 0~1
    total_games: int  # 총 경기 수
    matched_games: int  # 일치하는 경기 수
    mismatches: List[Mismatch] = field(default_factory=list)  # 불일치 항목들
    crawler_data: Optional[Tuple] = None  # (RoundInfo, List[Dict])
    api_data: Optional[Tuple] = None  # (RoundInfo, List[Dict])
    validated_at: datetime = field(default_factory=datetime.now)

    def __str__(self):
        status = "✅ 일치" if self.is_valid else "⚠️ 불일치"
        return (
            f"{status} - 일치율: {self.match_rate:.1%} "
            f"({self.matched_games}/{self.total_games}경기)"
        )


class DataValidator:
    """데이터 검증기"""

    # 팀명 정규화 매핑 (약어 및 변형 처리)
    TEAM_NAME_MAPPINGS = {
        # 축구 팀명
        "레스터시티": ["레스터C", "레스터", "레스터 시티"],
        "맨체스터유나이티드": ["맨체스U", "맨유", "맨체스터U", "맨체스터 유나이티드"],
        "맨체스터시티": ["맨시티", "맨체스터C", "맨체스터 시티"],
        "토트넘홋스퍼": ["토트넘", "토트넘홋"],
        "노팅엄포레스트": ["노팅엄F", "노팅엄", "노팅엄 포레스트"],
        "웨스트햄유나이티드": ["웨스트햄U", "웨스트햄", "웨스트햄U"],
        "뉴캐슬유나이티드": ["뉴캐슬U", "뉴캐슬", "뉴캐슬U"],

        # 농구 팀명
        "울산현대모비스": ["울산모비스", "현대모비스", "모비스"],
        "수원KT소닉붐": ["수원KT", "KT소닉붐", "KT"],
        "서울삼성썬더스": ["서울삼성", "삼성썬더스", "삼성"],
        "창원LG세이커스": ["창원LG", "LG세이커스", "LG"],
        "안양정관장레드부스터": ["안양정관장", "정관장", "안양"],
        "고양소노스카이거너스": ["고양소노", "소노", "고양"],
        "서울SK나이츠": ["서울SK", "SK나이츠", "SK"],
        "부산KCC이지스": ["부산KCC", "KCC이지스", "KCC"],
        "대구한국가스공사": ["대구가스공사", "한국가스공사", "가스공사"],
        "전주KCC이지스": ["전주KCC", "KCC"],

        # NBA 팀명 (필요시 추가)
        "골든스테이트워리어스": ["골든스테이트", "워리어스", "GSW"],
        "로스앤젤레스레이커스": ["LA레이커스", "레이커스", "LAL"],
    }

    def __init__(self):
        # 역매핑 생성 (약어 -> 정식명)
        self._reverse_mappings: Dict[str, str] = {}
        for full_name, aliases in self.TEAM_NAME_MAPPINGS.items():
            for alias in aliases:
                self._reverse_mappings[alias] = full_name
            self._reverse_mappings[full_name] = full_name

    # ========== 메인 검증 로직 ==========

    async def compare_sources(
        self,
        game_type: str = "soccer_wdl",
        use_cache: bool = False
    ) -> ValidationResult:
        """
        크롤러 데이터와 API 데이터를 비교하여 불일치 항목 반환

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"
            use_cache: 캐시 사용 여부 (False면 강제 새로고침)

        Returns:
            ValidationResult: 검증 결과
        """
        from src.services.round_manager import RoundManager

        manager = RoundManager()

        # 1. 두 소스에서 데이터 수집
        logger.info(f"데이터 검증 시작: {game_type}")

        try:
            # 크롤러 데이터
            if game_type == "soccer_wdl":
                crawler_info, crawler_games = await manager.get_soccer_wdl_round(
                    force_refresh=not use_cache,
                    source="crawler"
                )
            else:  # basketball_w5l
                crawler_info, crawler_games = await manager.get_basketball_w5l_round(
                    force_refresh=not use_cache,
                    source="crawler"
                )
            logger.info(f"✅ 크롤러: {crawler_info.round_number}회차 {len(crawler_games)}경기")
        except Exception as e:
            logger.error(f"❌ 크롤러 데이터 수집 실패: {e}")
            crawler_info = None
            crawler_games = []

        try:
            # API 데이터
            if game_type == "soccer_wdl":
                api_info, api_games = await manager.get_soccer_wdl_round(
                    force_refresh=not use_cache,
                    source="api"
                )
            else:  # basketball_w5l
                api_info, api_games = await manager.get_basketball_w5l_round(
                    force_refresh=not use_cache,
                    source="api"
                )
            logger.info(f"✅ API: {api_info.round_number}회차 {len(api_games)}경기")
        except Exception as e:
            logger.error(f"❌ API 데이터 수집 실패: {e}")
            api_info = None
            api_games = []

        # 2. 데이터 비교
        mismatches = []

        # 경기 수 검증
        crawler_count = len(crawler_games)
        api_count = len(api_games)

        if crawler_count != api_count:
            mismatches.append(Mismatch(
                game_number=0,
                mismatch_type=MismatchType.GAME_COUNT_MISMATCH,
                field="game_count",
                crawler_value=str(crawler_count),
                api_value=str(api_count),
                similarity=0.0,
                suggested_action="use_crawler" if crawler_count == 14 else "manual_review",
                description=f"경기 수 불일치: 크롤러 {crawler_count}경기 vs API {api_count}경기"
            ))

        # 회차 번호 검증
        if crawler_info and api_info and crawler_info.round_number != api_info.round_number:
            mismatches.append(Mismatch(
                game_number=0,
                mismatch_type=MismatchType.ROUND_MISMATCH,
                field="round_number",
                crawler_value=str(crawler_info.round_number),
                api_value=str(api_info.round_number),
                similarity=0.0,
                suggested_action="use_crawler",
                description=f"회차 번호 불일치: 크롤러 {crawler_info.round_number}회 vs API {api_info.round_number}회"
            ))

        # 3. 경기별 비교 (작은 쪽 기준)
        min_count = min(crawler_count, api_count)
        matched_count = 0

        for i in range(min_count):
            crawler_game = crawler_games[i]
            api_game = api_games[i]

            game_mismatches = self._compare_game(i + 1, crawler_game, api_game)

            if not game_mismatches:
                matched_count += 1
            else:
                mismatches.extend(game_mismatches)

        # 4. 누락된 경기 처리
        if crawler_count > api_count:
            for i in range(api_count, crawler_count):
                mismatches.append(Mismatch(
                    game_number=i + 1,
                    mismatch_type=MismatchType.MISSING_GAME,
                    field="game",
                    crawler_value=f"{crawler_games[i].get('hteam_han_nm', '')} vs {crawler_games[i].get('ateam_han_nm', '')}",
                    api_value="(없음)",
                    similarity=0.0,
                    suggested_action="use_crawler",
                    description="API에 경기 누락"
                ))
        elif api_count > crawler_count:
            for i in range(crawler_count, api_count):
                mismatches.append(Mismatch(
                    game_number=i + 1,
                    mismatch_type=MismatchType.MISSING_GAME,
                    field="game",
                    crawler_value="(없음)",
                    api_value=f"{api_games[i].get('hteam_han_nm', '')} vs {api_games[i].get('ateam_han_nm', '')}",
                    similarity=0.0,
                    suggested_action="manual_review",
                    description="크롤러에 경기 누락"
                ))

        # 5. 결과 생성
        total_games = max(crawler_count, api_count)
        match_rate = matched_count / total_games if total_games > 0 else 0.0
        is_valid = len(mismatches) == 0

        result = ValidationResult(
            is_valid=is_valid,
            match_rate=match_rate,
            total_games=total_games,
            matched_games=matched_count,
            mismatches=mismatches,
            crawler_data=(crawler_info, crawler_games) if crawler_info else None,
            api_data=(api_info, api_games) if api_info else None,
            validated_at=datetime.now()
        )

        logger.info(f"검증 완료: {result}")
        return result

    def _compare_game(self, game_number: int, crawler_game: Dict, api_game: Dict) -> List[Mismatch]:
        """개별 경기 비교"""
        mismatches = []

        # 홈팀 비교
        crawler_home = crawler_game.get("hteam_han_nm", "")
        api_home = api_game.get("hteam_han_nm", "")

        home_similarity = self._calculate_team_similarity(crawler_home, api_home)
        if home_similarity < 0.9:  # 90% 미만이면 불일치
            mismatches.append(Mismatch(
                game_number=game_number,
                mismatch_type=MismatchType.TEAM_NAME_MISMATCH,
                field="home_team",
                crawler_value=crawler_home,
                api_value=api_home,
                similarity=home_similarity,
                suggested_action=self._suggest_action(home_similarity),
                description=f"홈팀명 불일치"
            ))

        # 원정팀 비교
        crawler_away = crawler_game.get("ateam_han_nm", "")
        api_away = api_game.get("ateam_han_nm", "")

        away_similarity = self._calculate_team_similarity(crawler_away, api_away)
        if away_similarity < 0.9:
            mismatches.append(Mismatch(
                game_number=game_number,
                mismatch_type=MismatchType.TEAM_NAME_MISMATCH,
                field="away_team",
                crawler_value=crawler_away,
                api_value=api_away,
                similarity=away_similarity,
                suggested_action=self._suggest_action(away_similarity),
                description=f"원정팀명 불일치"
            ))

        # 날짜 비교
        crawler_date = crawler_game.get("match_ymd", "")
        api_date = api_game.get("match_ymd", "")

        if crawler_date != api_date:
            mismatches.append(Mismatch(
                game_number=game_number,
                mismatch_type=MismatchType.DATE_TIME_MISMATCH,
                field="date",
                crawler_value=crawler_date,
                api_value=api_date,
                similarity=0.0,
                suggested_action="use_crawler",
                description=f"경기 날짜 불일치"
            ))

        # 시간 비교 (5분 오차 허용)
        crawler_time = str(crawler_game.get("match_tm", "0000")).zfill(4)
        api_time = str(api_game.get("match_tm", "0000")).zfill(4)

        time_diff = self._calculate_time_diff(crawler_time, api_time)
        if time_diff > 5:  # 5분 초과 차이
            mismatches.append(Mismatch(
                game_number=game_number,
                mismatch_type=MismatchType.DATE_TIME_MISMATCH,
                field="time",
                crawler_value=crawler_time,
                api_value=api_time,
                similarity=0.0,
                suggested_action="use_crawler",
                description=f"경기 시간 불일치 ({time_diff}분 차이)"
            ))

        return mismatches

    # ========== 팀명 정규화 및 유사도 계산 ==========

    def _normalize_team_name(self, team_name: str) -> str:
        """팀명 정규화"""
        # 공백 제거
        team_name = team_name.strip().replace(" ", "")

        # 매핑 테이블에서 정식 명칭 찾기
        if team_name in self._reverse_mappings:
            return self._reverse_mappings[team_name]

        # 부분 매칭 시도
        for full_name, aliases in self.TEAM_NAME_MAPPINGS.items():
            if team_name in aliases or team_name == full_name:
                return full_name
            # 포함 관계 확인
            for alias in aliases:
                if team_name in alias or alias in team_name:
                    return full_name

        return team_name

    def _calculate_team_similarity(self, team1: str, team2: str) -> float:
        """
        팀명 유사도 계산

        Returns:
            0~1 유사도 (1.0 = 완전 일치)
        """
        if not team1 or not team2:
            return 0.0

        # 정규화
        norm1 = self._normalize_team_name(team1)
        norm2 = self._normalize_team_name(team2)

        # 정규화 후 일치하면 1.0
        if norm1 == norm2:
            return 1.0

        # 원본이 일치하면 1.0
        if team1 == team2:
            return 1.0

        # SequenceMatcher로 유사도 계산
        similarity = SequenceMatcher(None, norm1, norm2).ratio()

        # 추가: 한쪽이 다른 쪽을 포함하면 보너스
        if norm1 in norm2 or norm2 in norm1:
            similarity = max(similarity, 0.8)

        return similarity

    def _calculate_time_diff(self, time1: str, time2: str) -> int:
        """
        시간 차이 계산 (분 단위)

        Args:
            time1, time2: HHMM 형식

        Returns:
            분 단위 차이
        """
        try:
            h1, m1 = int(time1[:2]), int(time1[2:4])
            h2, m2 = int(time2[:2]), int(time2[2:4])

            min1 = h1 * 60 + m1
            min2 = h2 * 60 + m2

            return abs(min1 - min2)
        except (ValueError, IndexError):
            return 0

    def _suggest_action(self, similarity: float) -> str:
        """
        유사도에 따른 수정 제안

        Args:
            similarity: 0~1 유사도

        Returns:
            "use_crawler" | "use_api" | "manual_review"
        """
        if similarity >= 0.7:
            return "use_crawler"  # 크롤러가 더 정확함
        elif similarity >= 0.3:
            return "manual_review"  # 수동 검토 필요
        else:
            return "manual_review"  # 완전히 다름

    # ========== 보고서 생성 ==========

    async def generate_report(
        self,
        game_type: str = "soccer_wdl",
        use_cache: bool = False
    ) -> str:
        """
        마크다운 형식의 검증 보고서 생성

        Args:
            game_type: "soccer_wdl" | "basketball_w5l"
            use_cache: 캐시 사용 여부

        Returns:
            마크다운 형식 보고서
        """
        result = await self.compare_sources(game_type, use_cache)

        # 헤더
        game_type_name = "축구 승무패" if game_type == "soccer_wdl" else "농구 승5패"
        status_emoji = "✅" if result.is_valid else "⚠️"

        report = [
            "# 데이터 검증 보고서",
            f"## {game_type_name}",
            "",
            f"**검증 시각**: {result.validated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**검증 결과**: {status_emoji} {'일치' if result.is_valid else '불일치'}",
            f"**일치율**: {result.match_rate:.1%} ({result.matched_games}/{result.total_games}경기)",
            "",
            "---",
            "",
        ]

        # 회차 정보
        if result.crawler_data and result.api_data:
            crawler_info, crawler_games = result.crawler_data
            api_info, api_games = result.api_data

            report.extend([
                "## 데이터 소스 정보",
                "",
                "| 항목 | 베트맨 크롤러 | KSPO API |",
                "|------|--------------|----------|",
                f"| 회차 번호 | {crawler_info.round_number}회 | {api_info.round_number}회 |",
                f"| 경기 수 | {len(crawler_games)}경기 | {len(api_games)}경기 |",
                f"| 경기 날짜 | {crawler_info.match_date} | {api_info.match_date} |",
                f"| 상태 | {crawler_info.status} | {api_info.status} |",
                "",
                "---",
                "",
            ])

        # 불일치 항목
        if result.mismatches:
            report.extend([
                f"## 불일치 항목 ({len(result.mismatches)}건)",
                "",
            ])

            # 유형별 그룹화
            by_type: Dict[MismatchType, List[Mismatch]] = {}
            for m in result.mismatches:
                by_type.setdefault(m.mismatch_type, []).append(m)

            for mismatch_type, items in by_type.items():
                type_name_map = {
                    MismatchType.TEAM_NAME_MISMATCH: "팀명 불일치",
                    MismatchType.GAME_COUNT_MISMATCH: "경기 수 불일치",
                    MismatchType.ORDER_MISMATCH: "경기 순서 불일치",
                    MismatchType.DATE_TIME_MISMATCH: "날짜/시간 불일치",
                    MismatchType.ROUND_MISMATCH: "회차 번호 불일치",
                    MismatchType.MISSING_GAME: "경기 누락",
                }

                report.extend([
                    f"### {type_name_map.get(mismatch_type, str(mismatch_type))} ({len(items)}건)",
                    "",
                    "| 경기 | 필드 | 크롤러 | API | 유사도 | 권장 조치 |",
                    "|------|------|--------|-----|--------|-----------|",
                ])

                for m in items:
                    game_num = f"{m.game_number:02d}" if m.game_number > 0 else "-"
                    similarity_str = f"{m.similarity:.1%}" if m.similarity > 0 else "-"
                    action_map = {
                        "use_crawler": "크롤러 사용",
                        "use_api": "API 사용",
                        "manual_review": "수동 검토"
                    }
                    action = action_map.get(m.suggested_action, m.suggested_action)

                    report.append(
                        f"| {game_num} | {m.field} | {m.crawler_value} | {m.api_value} | "
                        f"{similarity_str} | {action} |"
                    )

                report.append("")
        else:
            report.extend([
                "## 검증 결과",
                "",
                "모든 데이터가 일치합니다.",
                "",
            ])

        # 권장 사항
        report.extend([
            "---",
            "",
            "## 권장 사항",
            "",
        ])

        if result.is_valid:
            report.extend([
                "- 두 소스의 데이터가 완전히 일치합니다.",
                "- 어떤 소스를 사용해도 무방합니다.",
                "",
            ])
        else:
            # 크롤러 권장 개수
            crawler_recommended = sum(1 for m in result.mismatches if m.suggested_action == "use_crawler")
            api_recommended = sum(1 for m in result.mismatches if m.suggested_action == "use_api")
            manual_review = sum(1 for m in result.mismatches if m.suggested_action == "manual_review")

            report.extend([
                f"- **크롤러 사용 권장**: {crawler_recommended}건",
                f"- **API 사용 권장**: {api_recommended}건",
                f"- **수동 검토 필요**: {manual_review}건",
                "",
            ])

            if crawler_recommended > api_recommended:
                report.extend([
                    "**결론**: 베트맨 크롤러 데이터 사용을 권장합니다.",
                    "",
                    "이유:",
                    "- 크롤러는 베트맨 공식 웹사이트에서 직접 수집하므로 더 정확합니다.",
                    "- KSPO API는 turn_no 누락, 경기 누락 등의 문제가 있습니다.",
                    "",
                ])
            else:
                report.extend([
                    "**결론**: 수동 검토 후 결정하세요.",
                    "",
                ])

        # 경기 목록 상세 비교 (첫 5경기만)
        if result.crawler_data and result.api_data:
            crawler_info, crawler_games = result.crawler_data
            api_info, api_games = result.api_data

            report.extend([
                "---",
                "",
                "## 경기 목록 상세 비교 (처음 5경기)",
                "",
            ])

            for i in range(min(5, len(crawler_games), len(api_games))):
                c_game = crawler_games[i]
                a_game = api_games[i]

                c_home = c_game.get("hteam_han_nm", "")
                c_away = c_game.get("ateam_han_nm", "")
                c_time = str(c_game.get("match_tm", "0000")).zfill(4)

                a_home = a_game.get("hteam_han_nm", "")
                a_away = a_game.get("ateam_han_nm", "")
                a_time = str(a_game.get("match_tm", "0000")).zfill(4)

                match_emoji = "✅" if (c_home == a_home and c_away == a_away) else "⚠️"

                report.extend([
                    f"### {i+1:02d}번 경기 {match_emoji}",
                    "",
                    f"**크롤러**: {c_home} vs {c_away} ({c_time[:2]}:{c_time[2:]})",
                    f"**API**: {a_home} vs {a_away} ({a_time[:2]}:{a_time[2:]})",
                    "",
                ])

        return "\n".join(report)

    async def get_validation_summary(self, game_type: str = "soccer_wdl") -> Dict:
        """
        검증 결과 요약 (JSON 형식)

        Returns:
            {
                "is_valid": bool,
                "match_rate": float,
                "total_games": int,
                "mismatches_count": int,
                "recommended_source": "crawler" | "api" | "manual",
            }
        """
        result = await self.compare_sources(game_type)

        # 권장 소스 결정
        crawler_recommended = sum(1 for m in result.mismatches if m.suggested_action == "use_crawler")
        api_recommended = sum(1 for m in result.mismatches if m.suggested_action == "use_api")

        if result.is_valid:
            recommended = "both"
        elif crawler_recommended > api_recommended:
            recommended = "crawler"
        elif api_recommended > crawler_recommended:
            recommended = "api"
        else:
            recommended = "manual"

        return {
            "is_valid": result.is_valid,
            "match_rate": result.match_rate,
            "total_games": result.total_games,
            "matched_games": result.matched_games,
            "mismatches_count": len(result.mismatches),
            "recommended_source": recommended,
            "validated_at": result.validated_at.isoformat(),
        }


# ========== 테스트 ==========

async def test_validator():
    """검증기 테스트"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    validator = DataValidator()

    # 축구 승무패 검증
    print("=" * 80)
    print("⚽ 축구 승무패 데이터 검증")
    print("=" * 80)
    print()

    try:
        report = await validator.generate_report("soccer_wdl", use_cache=False)
        print(report)
        print()

        # 요약 정보
        summary = await validator.get_validation_summary("soccer_wdl")
        print("=" * 80)
        print("검증 요약 (JSON)")
        print("=" * 80)
        import json
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 80)
    print("🏀 농구 승5패 데이터 검증")
    print("=" * 80)
    print()

    try:
        report = await validator.generate_report("basketball_w5l", use_cache=False)
        print(report)
        print()

        summary = await validator.get_validation_summary("basketball_w5l")
        print("=" * 80)
        print("검증 요약 (JSON)")
        print("=" * 80)
        import json
        print(json.dumps(summary, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_validator())
