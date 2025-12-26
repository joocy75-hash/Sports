"""
최종 14경기 마킹 리스트 생성
- AI 합의도 포함
- 신뢰도 기반 마킹
"""

from typing import Dict, List, Optional
from datetime import datetime
from collections import Counter


class MarkingGenerator:
    """14경기 최종 마킹 생성기"""

    def generate(
        self,
        round_analysis: Dict
    ) -> Dict:
        """
        최종 마킹 리스트 생성

        Args:
            round_analysis: {
                'round_id': '123',
                'matches': [...],
                'upsets': [...],
                'markings': [...]
            }

        Returns:
            {
                'round_id': '123',
                'final_markings': [
                    {
                        'game_no': 1,
                        'match_name': '맨시티 vs 첼시',
                        'marking': ['홈승'],
                        'ai_consensus': '5/5 (100%)',
                        'confidence': 92,
                        'is_upset': False
                    },
                    ...
                ],
                'summary': {...}
            }
        """
        matches = round_analysis.get('matches', [])
        markings = round_analysis.get('markings', [])
        upsets = round_analysis.get('upsets', [])

        final_markings = []

        for i, match in enumerate(matches, 1):
            # 해당 경기의 마킹 정보 찾기
            marking_data = None
            if i <= len(markings):
                marking_data = markings[i-1]

            if not marking_data:
                # 마킹 정보가 없으면 기본값 생성
                marking_data = {
                    'marking_type': 'single',
                    'marked_outcomes': ['home'],
                    'expected_hit_rate': 0.5,
                    'reasoning': '기본 마킹'
                }

            # AI 합의도 계산
            consensus = self._calculate_consensus(match)

            # 한글 변환
            marked_kr = self._translate_outcomes(
                marking_data.get('marked_outcomes', ['home'])
            )

            # 이변 여부
            is_upset = any(
                u.get('match_id') == match.get('id')
                for u in upsets
            )

            # 확률 정보
            ai_pred = match.get('ai_prediction', {})
            probabilities = {
                '홈승': f"{ai_pred.get('home', 0.33):.0%}",
                '무승부': f"{ai_pred.get('draw', 0.33):.0%}",
                '원정승': f"{ai_pred.get('away', 0.33):.0%}"
            }

            final_markings.append({
                'game_no': i,
                'match_name': f"{match.get('home_team', 'Home')} vs {match.get('away_team', 'Away')}",
                'marking': marked_kr,
                'marking_type': marking_data.get('marking_type', 'single'),
                'ai_consensus': consensus['display'],
                'confidence': int(match.get('confidence', 0.5) * 100),
                'probabilities': probabilities,
                'is_upset': is_upset,
                'reasoning': marking_data.get('reasoning', '')
            })

        # 요약 통계
        summary = self._generate_summary(final_markings, round_analysis)

        return {
            'round_id': round_analysis.get('round_id', ''),
            'final_markings': final_markings,
            'summary': summary,
            'generated_at': datetime.now().isoformat()
        }

    def _calculate_consensus(self, match: Dict) -> Dict:
        """
        AI 합의도 계산

        Args:
            match: 경기 정보 (individual_predictions 포함)

        Returns:
            {
                'count': 3,
                'total': 5,
                'display': '3/5 (60%)',
                'outcome': 'home_win'
            }
        """
        # individual_predictions에서 가장 많이 선택된 결과 찾기
        predictions = match.get('individual_predictions', [])

        if not predictions:
            return {
                'count': 0,
                'total': 5,
                'display': '0/5 (0%)',
                'outcome': 'unknown'
            }

        # 각 AI의 최고 예측 추출
        best_outcomes = []
        for pred in predictions:
            # 예측 결과가 확률 형태인 경우
            if isinstance(pred, dict):
                # home_win_prob, draw_prob, away_win_prob 형태
                prob_keys = ['home_win_prob', 'draw_prob', 'away_win_prob']
                if all(k in pred for k in prob_keys):
                    best = max(prob_keys, key=lambda k: pred.get(k, 0))
                    best_outcomes.append(best.replace('_prob', ''))
                # home, draw, away 형태
                elif all(k in pred for k in ['home', 'draw', 'away']):
                    best = max(['home', 'draw', 'away'], key=lambda k: pred.get(k, 0))
                    best_outcomes.append(f"{best}_win" if best != 'draw' else 'draw')
            # 예측 결과가 문자열인 경우
            elif isinstance(pred, str):
                best_outcomes.append(pred)

        if not best_outcomes:
            return {
                'count': 0,
                'total': len(predictions),
                'display': f'0/{len(predictions)} (0%)',
                'outcome': 'unknown'
            }

        # 최빈값 찾기
        counts = Counter(best_outcomes)
        most_common = counts.most_common(1)[0]
        consensus_count = most_common[1]
        total = len(predictions)

        return {
            'count': consensus_count,
            'total': total,
            'display': f"{consensus_count}/{total} ({consensus_count/total:.0%})",
            'outcome': most_common[0]
        }

    def _translate_outcomes(self, outcomes: List[str]) -> List[str]:
        """
        영어 → 한글 변환

        Args:
            outcomes: ['home', 'draw', 'away']

        Returns:
            ['홈승', '무승부', '원정승']
        """
        translation = {
            'home': '홈승',
            'draw': '무승부',
            'away': '원정승',
            'home_win': '홈승',
            'away_win': '원정승'
        }
        return [translation.get(o, o) for o in outcomes]

    def _generate_summary(self, final_markings: List[Dict], round_analysis: Dict) -> Dict:
        """
        전체 요약 통계 생성

        Args:
            final_markings: 최종 마킹 리스트
            round_analysis: 전체 분석 결과

        Returns:
            요약 통계
        """
        total_games = len(final_markings)

        # 마킹 타입별 개수
        single_count = sum(1 for m in final_markings if m['marking_type'] == 'single')
        double_count = sum(1 for m in final_markings if m['marking_type'] == 'double')
        triple_count = sum(1 for m in final_markings if m['marking_type'] == 'triple')

        # 이변 후보 개수
        upset_count = sum(1 for m in final_markings if m['is_upset'])

        # 평균 신뢰도
        avg_confidence = sum(m['confidence'] for m in final_markings) / total_games if total_games > 0 else 0

        # 고신뢰도 단식 개수 (신뢰도 80% 이상)
        high_confidence_singles = sum(
            1 for m in final_markings
            if m['marking_type'] == 'single' and m['confidence'] >= 80
        )

        # 복수 마킹 비율
        multi_marking_ratio = (double_count + triple_count) / total_games if total_games > 0 else 0

        return {
            'total_games': total_games,
            'single_count': single_count,
            'double_count': double_count,
            'triple_count': triple_count,
            'upset_count': upset_count,
            'avg_confidence': round(avg_confidence, 1),
            'high_confidence_singles': high_confidence_singles,
            'multi_marking_ratio': round(multi_marking_ratio * 100, 1),
            'confidence_breakdown': {
                'high': sum(1 for m in final_markings if m['confidence'] >= 80),
                'medium': sum(1 for m in final_markings if 60 <= m['confidence'] < 80),
                'low': sum(1 for m in final_markings if m['confidence'] < 60)
            }
        }

    def format_for_display(self, result: Dict) -> str:
        """
        사용자 친화적인 포맷으로 변환

        Args:
            result: generate() 결과

        Returns:
            포맷팅된 문자열
        """
        lines = []
        lines.append("=" * 60)
        lines.append(f"🎯 프로토 {result['round_id']}회차 최종 마킹")
        lines.append("=" * 60)
        lines.append("")

        for marking in result['final_markings']:
            lines.append(f"경기 {marking['game_no']}: {marking['match_name']}")
            lines.append(f"  마킹: {', '.join(marking['marking'])} ({marking['marking_type']})")
            lines.append(f"  AI 합의: {marking['ai_consensus']} | 신뢰도: {marking['confidence']}%")
            lines.append(f"  확률: {marking['probabilities']['홈승']} / {marking['probabilities']['무승부']} / {marking['probabilities']['원정승']}")

            if marking['is_upset']:
                lines.append("  ⚠️ 이변 후보")

            lines.append("")

        # 요약
        summary = result['summary']
        lines.append("-" * 60)
        lines.append("📊 전체 요약")
        lines.append("-" * 60)
        lines.append(f"총 경기 수: {summary['total_games']}")
        lines.append(f"단식: {summary['single_count']}개 (고신뢰: {summary['high_confidence_singles']}개)")
        lines.append(f"2개 복수: {summary['double_count']}개")
        lines.append(f"3개 복수: {summary['triple_count']}개")
        lines.append(f"이변 후보: {summary['upset_count']}개")
        lines.append(f"평균 신뢰도: {summary['avg_confidence']}%")
        lines.append("")
        lines.append(f"생성 시각: {result['generated_at']}")
        lines.append("=" * 60)

        return "\n".join(lines)

    def export_to_json(self, result: Dict, filepath: str):
        """
        JSON 파일로 내보내기

        Args:
            result: generate() 결과
            filepath: 저장할 파일 경로
        """
        import json

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def export_to_csv(self, result: Dict, filepath: str):
        """
        CSV 파일로 내보내기

        Args:
            result: generate() 결과
            filepath: 저장할 파일 경로
        """
        import csv

        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['game_no', 'match_name', 'marking', 'marking_type',
                           'ai_consensus', 'confidence', 'is_upset', 'reasoning']
            )
            writer.writeheader()

            for marking in result['final_markings']:
                row = marking.copy()
                row['marking'] = ', '.join(row['marking'])
                # probabilities 필드 제거 (CSV에서는 복잡도 낮추기)
                row.pop('probabilities', None)
                writer.writerow(row)
