"""
적중률 리포터 - 리포트 생성 및 텔레그램 메시지 포맷팅

핵심 기능:
1. 회차별 적중률 리포트 생성
2. 텔레그램 메시지 포맷팅
3. 누적 통계 포맷팅
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from src.services.prediction_tracker import prediction_tracker, CumulativeStats

logger = logging.getLogger(__name__)

# 상태 저장 경로
STATE_DIR = Path(__file__).parent.parent.parent / ".state"
RESULTS_DIR = STATE_DIR / "results"


@dataclass
class HitRateReport:
    """적중률 리포트"""
    round_number: int
    game_type: str
    generated_at: str

    # 적중 통계
    total_games: int
    correct_predictions: int
    hit_rate: float
    single_hit: bool

    # 복수 베팅
    multi_games_count: int
    multi_correct_count: int
    multi_combinations_hit: int

    # 경기별 결과
    game_results: List[Dict]

    # 누적 통계 (선택)
    cumulative_stats: Optional[CumulativeStats] = None


class HitRateReporter:
    """적중률 리포터"""

    def __init__(self):
        pass

    def generate_report(
        self,
        round_number: int,
        game_type: str = "soccer_wdl"
    ) -> Optional[HitRateReport]:
        """
        특정 회차의 적중률 리포트 생성

        Args:
            round_number: 회차 번호
            game_type: "soccer_wdl" | "basketball_w5l"

        Returns:
            HitRateReport: 리포트 (없으면 None)
        """
        result = prediction_tracker.get_result(round_number, game_type)
        if not result:
            logger.warning(f"결과 데이터 없음: {round_number}회차")
            return None

        summary = result.get("summary", {})
        results = result.get("results", [])

        # 복수 베팅 경기 수
        multi_games = [r for r in results if r.get("predicted_multi")]
        multi_correct = [r for r in multi_games if r.get("is_multi_correct")]

        # 누적 통계
        cumulative = prediction_tracker.get_cumulative_stats(game_type)

        return HitRateReport(
            round_number=round_number,
            game_type=game_type,
            generated_at=datetime.now().isoformat(),
            total_games=summary.get("total_games", 14),
            correct_predictions=summary.get("correct_predictions", 0),
            hit_rate=summary.get("hit_rate", 0.0),
            single_hit=summary.get("single_hit", False),
            multi_games_count=len(multi_games),
            multi_correct_count=len(multi_correct),
            multi_combinations_hit=summary.get("multi_combinations_hit", 0),
            game_results=results,
            cumulative_stats=cumulative,
        )

    def format_telegram_message(self, report: HitRateReport) -> str:
        """
        텔레그램 메시지 포맷팅

        Args:
            report: HitRateReport

        Returns:
            str: 텔레그램 메시지 (Markdown)
        """
        game_emoji = "⚽" if report.game_type == "soccer_wdl" else "🏀"
        game_name = "축구 승무패" if report.game_type == "soccer_wdl" else "농구 승5패"

        lines = [
            f"{game_emoji} *{game_name} {report.round_number}회차 적중률 리포트*",
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "📋 *경기별 결과*",
            "",
        ]

        # 경기별 결과
        for r in report.game_results:
            game_num_val = r.get("game_number", 0)
            if not isinstance(game_num_val, int):
                game_num_val = 0
            game_num = str(game_num_val).zfill(2)
            home = r.get("home_team", "") or ""
            away = r.get("away_team", "") or ""
            predicted = r.get("predicted", "")
            actual = r.get("actual", "-")
            is_correct = r.get("is_correct", False)
            is_multi = bool(r.get("predicted_multi"))

            # 적중 표시
            if is_correct:
                status = "✅"
            elif is_multi and r.get("is_multi_correct"):
                status = "🔵"  # 복수 베팅 적중
            else:
                status = "❌"

            # 스코어
            score_home = r.get("score_home")
            score_away = r.get("score_away")
            score_str = ""
            if score_home is not None and score_away is not None:
                score_str = f" ({score_home}:{score_away})"

            # 복수 베팅 표시
            multi_mark = " [복수]" if is_multi else ""

            lines.append(f"{game_num}. {home} vs {away}{multi_mark}")

            if is_multi:
                multi_sel = r.get("predicted_multi", [])
                lines.append(f"     예측: [{'/'.join(multi_sel)}] → 실제: {actual}{score_str} {status}")
            else:
                lines.append(f"     예측: [{predicted}] → 실제: {actual}{score_str} {status}")

            lines.append("")

        # 적중 통계
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "📈 *적중 통계*",
            "",
            f"• 단식 적중률: {report.hit_rate * 100:.1f}% ({report.correct_predictions}/{report.total_games})",
        ])

        if report.multi_games_count > 0:
            lines.append(f"• 복수 {report.multi_games_count}경기 적중: {report.multi_correct_count}/{report.multi_games_count}")
            # 동적으로 조합 수 계산 (2^n)
            total_combos = 2 ** report.multi_games_count
            lines.append(f"• {total_combos}조합 중 적중: {report.multi_combinations_hit}조합")

        # 전체 적중 축하
        if report.single_hit:
            lines.extend([
                "",
                "🎉 *전체 적중! 축하합니다!* 🎉",
            ])

        # 누적 통계
        if report.cumulative_stats:
            stats = report.cumulative_stats
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━",
                f"📊 *누적 통계 (최근 {stats.completed_rounds}회차)*",
                "",
                f"• 평균 단식 적중률: {stats.avg_hit_rate * 100:.1f}%",
                f"• 최고 적중률: {stats.best_hit_rate * 100:.1f}% ({stats.best_round}회차)",
                f"• 최저 적중률: {stats.worst_hit_rate * 100:.1f}% ({stats.worst_round}회차)",
                f"• 최근 5회차: {stats.recent_5_avg * 100:.1f}%",
            ])

            if stats.single_hits > 0:
                lines.append(f"• 전체 적중: {stats.single_hits}회")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            "_프로토 AI 분석 시스템_",
        ])

        return "\n".join(lines)

    def format_simple_summary(self, report: HitRateReport) -> str:
        """간단한 요약 메시지"""
        game_emoji = "⚽" if report.game_type == "soccer_wdl" else "🏀"
        game_name = "축구 승무패" if report.game_type == "soccer_wdl" else "농구 승5패"

        hit_status = "🎉 전체 적중!" if report.single_hit else f"✅ {report.correct_predictions}/{report.total_games}"

        return (
            f"{game_emoji} {game_name} {report.round_number}회차: "
            f"{report.hit_rate * 100:.1f}% {hit_status}"
        )

    def format_cumulative_summary(self, stats: CumulativeStats) -> str:
        """누적 통계 요약 메시지"""
        game_emoji = "⚽" if stats.game_type == "soccer_wdl" else "🏀"
        game_name = "축구 승무패" if stats.game_type == "soccer_wdl" else "농구 승5패"

        lines = [
            f"{game_emoji} *{game_name} 누적 통계*",
            "",
            f"📊 총 {stats.completed_rounds}회차 분석",
            "",
            f"• 평균 적중률: {stats.avg_hit_rate * 100:.1f}%",
            f"• 최고: {stats.best_hit_rate * 100:.1f}% ({stats.best_round}회차)",
            f"• 최저: {stats.worst_hit_rate * 100:.1f}% ({stats.worst_round}회차)",
            f"• 전체 적중: {stats.single_hits}회",
            "",
            f"📈 최근 트렌드",
            f"• 5회차 평균: {stats.recent_5_avg * 100:.1f}%",
            f"• 10회차 평균: {stats.recent_10_avg * 100:.1f}%",
        ]

        return "\n".join(lines)


# 전역 인스턴스
hit_rate_reporter = HitRateReporter()


# 테스트
def test_hit_rate_reporter():
    """테스트 실행"""
    reporter = HitRateReporter()

    # 완료된 회차에서 리포트 생성 테스트
    completed = prediction_tracker.get_completed_rounds("soccer_wdl")
    if completed:
        round_num = completed[0]
        report = reporter.generate_report(round_num, "soccer_wdl")
        if report:
            print("=" * 60)
            print(f"리포트 생성: {round_num}회차")
            print("=" * 60)
            print(reporter.format_telegram_message(report))
        else:
            print(f"리포트 생성 실패: {round_num}회차")
    else:
        print("완료된 회차 없음")


if __name__ == "__main__":
    test_hit_rate_reporter()
