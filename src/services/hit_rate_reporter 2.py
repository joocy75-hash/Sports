"""
적중률 리포트 시스템 - 적중률 리포트 생성 및 포맷팅

핵심 기능:
1. 회차별 적중률 리포트 생성
2. 텔레그램 메시지 포맷팅
3. 누적 통계 리포트 생성
"""

import logging
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

from src.services.prediction_tracker import prediction_tracker, CumulativeStats

logger = logging.getLogger(__name__)


@dataclass
class HitRateReport:
    """적중률 리포트"""
    round_number: int
    game_type: str
    collected_at: str

    # 통계
    total_games: int
    correct_predictions: int
    hit_rate: float
    single_hit: bool

    # 복수 베팅
    multi_games_count: int
    multi_correct_count: int
    multi_combinations_hit: int

    # 경기별 결과
    game_results: List[dict]

    # 누적 통계 (선택)
    cumulative_stats: Optional[CumulativeStats] = None


class HitRateReporter:
    """적중률 리포트 생성기"""

    def __init__(self):
        self.tracker = prediction_tracker

    def generate_report(
        self,
        round_number: int,
        game_type: str,
        include_cumulative: bool = True
    ) -> Optional[HitRateReport]:
        """
        특정 회차의 적중률 리포트 생성

        Args:
            round_number: 회차 번호
            game_type: "soccer_wdl" | "basketball_w5l"
            include_cumulative: 누적 통계 포함 여부

        Returns:
            HitRateReport 또는 None
        """
        # 결과 데이터 로드
        result = self.tracker.get_result(round_number, game_type)
        if not result:
            logger.warning(f"결과 데이터 없음: {game_type} {round_number}회차")
            return None

        summary = result.get("summary", {})
        results = result.get("results", [])

        # 복수 베팅 통계 계산
        multi_games = [r for r in results if r.get("predicted_multi")]
        multi_correct = [r for r in multi_games if r.get("is_multi_correct")]

        # 누적 통계
        cumulative = None
        if include_cumulative:
            cumulative = self.tracker.get_cumulative_stats(game_type, last_n_rounds=10)

        report = HitRateReport(
            round_number=round_number,
            game_type=game_type,
            collected_at=result.get("collected_at", datetime.now().isoformat()),
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

        return report

    def format_telegram_message(self, report: HitRateReport) -> str:
        """
        텔레그램 메시지 포맷팅

        Args:
            report: HitRateReport 객체

        Returns:
            포맷팅된 메시지 문자열
        """
        # 아이콘 및 게임명
        if report.game_type == "soccer_wdl":
            icon = "⚽"
            game_name = "축구 승무패"
        else:
            icon = "🏀"
            game_name = "농구 승5패"

        # 헤더
        lines = [
            f"{icon} *{game_name} {report.round_number}회차 적중률 리포트*",
            f"📅 {report.collected_at[:16].replace('T', ' ')}",
            "",
            "━" * 24,
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
            is_multi_correct = r.get("is_multi_correct", False)

            # 점수
            score_home = r.get("score_home", "-")
            score_away = r.get("score_away", "-")
            score_str = f"({score_home}:{score_away})" if score_home != "-" else ""

            # 적중 표시
            if is_correct:
                result_icon = "✅"
            elif is_multi and is_multi_correct:
                result_icon = "🔵"  # 복수 베팅 적중
            else:
                result_icon = "❌"

            # 복수 베팅 표시
            multi_label = " [복수]" if is_multi else ""
            predicted_multi = r.get("predicted_multi", [])
            if predicted_multi:
                pred_str = "/".join(predicted_multi)
            else:
                pred_str = predicted

            lines.append(f"{game_num}. {home} vs {away}{multi_label}")
            lines.append(f"     예측: [{pred_str}] → 실제: {actual} {score_str} {result_icon}")
            lines.append("")

        # 적중 통계
        lines.extend([
            "━" * 24,
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
                "🎉 *14경기 전체 적중!* 🎉",
            ])

        # 누적 통계
        if report.cumulative_stats:
            stats = report.cumulative_stats
            lines.extend([
                "",
                "━" * 24,
                f"📊 *누적 통계 (최근 {stats.total_rounds}회차)*",
                "",
                f"• 평균 단식 적중률: {stats.avg_hit_rate * 100:.1f}%",
                f"• 최고 적중률: {stats.best_hit_rate * 100:.1f}% ({stats.best_round}회차)",
                f"• 최저 적중률: {stats.worst_hit_rate * 100:.1f}% ({stats.worst_round}회차)",
            ])

            if stats.recent_5_avg > 0:
                lines.append(f"• 최근 5회차: {stats.recent_5_avg * 100:.1f}%")

        lines.extend([
            "━" * 24,
            "",
            "_프로토 AI 분석 시스템_"
        ])

        return "\n".join(lines)

    def format_simple_summary(self, report: HitRateReport) -> str:
        """
        간단한 요약 메시지 생성

        Args:
            report: HitRateReport 객체

        Returns:
            간단한 요약 문자열
        """
        if report.game_type == "soccer_wdl":
            icon = "⚽"
            game_name = "축구 승무패"
        else:
            icon = "🏀"
            game_name = "농구 승5패"

        hit_status = "🎉 전체 적중!" if report.single_hit else ""

        summary = f"""
{icon} *{game_name} {report.round_number}회차 결과*

📊 *적중률*: {report.hit_rate * 100:.1f}% ({report.correct_predictions}/{report.total_games})
{hit_status}

---
_프로토 AI 분석 시스템_
"""

        return summary.strip()

    def format_cumulative_stats(self, stats: CumulativeStats) -> str:
        """
        누적 통계 메시지 생성

        Args:
            stats: CumulativeStats 객체

        Returns:
            누적 통계 메시지 문자열
        """
        if stats.game_type == "soccer_wdl":
            icon = "⚽"
            game_name = "축구 승무패"
        else:
            icon = "🏀"
            game_name = "농구 승5패"

        message = f"""
📈 *{game_name} 누적 통계*

📊 *총 {stats.total_rounds}회차 분석*

✅ 평균 적중률: {stats.avg_hit_rate * 100:.1f}%
🏆 최고 적중률: {stats.best_hit_rate * 100:.1f}% ({stats.best_round}회차)
📉 최저 적중률: {stats.worst_hit_rate * 100:.1f}% ({stats.worst_round}회차)

📈 *최근 트렌드*
• 최근 5회차: {stats.recent_5_avg * 100:.1f}%
• 최근 10회차: {stats.recent_10_avg * 100:.1f}%

---
_프로토 AI 분석 시스템_
"""

        return message.strip()


# 전역 인스턴스
hit_rate_reporter = HitRateReporter()


# 테스트
def test_hit_rate_reporter():
    """테스트"""
    reporter = HitRateReporter()

    # 완료된 회차 확인
    completed = prediction_tracker.get_completed_rounds("soccer_wdl")
    print("=" * 60)
    print(f"완료된 축구 승무패 회차: {completed}")

    if completed:
        round_num = completed[0]
        report = reporter.generate_report(round_num, "soccer_wdl")
        if report:
            print()
            print("=" * 60)
            print(reporter.format_telegram_message(report))
        else:
            print(f"리포트 생성 실패: {round_num}회차")

    # 누적 통계
    stats = prediction_tracker.get_cumulative_stats("soccer_wdl")
    if stats:
        print()
        print("=" * 60)
        print(reporter.format_cumulative_stats(stats))


if __name__ == "__main__":
    test_hit_rate_reporter()
