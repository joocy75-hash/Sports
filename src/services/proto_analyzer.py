"""
한국 프로토 14경기 분석 시스템

공식 배당을 사용하지 않고 순수 데이터 기반으로 AI가 확률을 계산하여
이변 가능성이 높은 경기를 찾고 복수 베팅을 추천합니다.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics
from datetime import datetime


@dataclass
class UpsetSignal:
    """이변 신호"""
    signal_type: str  # 'ambiguous', 'disagreement', 'form_conflict', 'rank_mismatch'
    strength: float  # 0-100
    description: str
    evidence: Dict


@dataclass
class MatchMarking:
    """경기 마킹 결과"""
    match_id: str
    match_number: int  # 1-14
    home_team: str
    away_team: str
    league: str
    match_time: str

    # AI 합의 결과
    consensus_outcome: str  # 'H', 'D', 'A'
    consensus_probability: float  # 0-1

    # 이변 분석
    upset_probability: float  # 0-100
    is_upset_prone: bool
    upset_signals: List[UpsetSignal]

    # 복수 베팅 추천
    recommended_outcomes: List[str]  # ['H'] or ['H', 'D']
    is_multiple_bet: bool

    # 근거
    reasoning: str
    model_agreement: float  # 0-1 (모델 합의도)


@dataclass
class ProtoAnalysisResult:
    """프로토 14경기 전체 분석 결과"""
    round_id: str
    analyzed_at: str
    game_type: str  # '승무패' or '승5패'

    # 전체 마킹 리스트
    markings: List[MatchMarking]

    # 복수 베팅 경기 (4개)
    multiple_bet_matches: List[MatchMarking]

    # 통계
    high_confidence_count: int  # 신뢰도 높은 경기 수
    upset_prone_count: int  # 이변 가능성 높은 경기 수
    average_model_agreement: float

    # 전략 추천
    recommended_strategy: str
    strategy_reasoning: str


class ProtoAnalyzer:
    """프로토 14경기 분석기"""

    def __init__(self):
        # 임계값 설정
        self.AMBIGUOUS_THRESHOLD = 0.15  # 확률 차이 15% 이하 → 애매함
        self.DISAGREEMENT_THRESHOLD = 0.20  # 모델 간 표준편차 20% 이상 → 불일치
        self.UPSET_THRESHOLD = 55  # 이변 확률 55% 이상 → 복수 베팅 권장
        self.MULTIPLE_BET_COUNT = 4  # 축구 승무패: 복수 베팅 경기 수

    def analyze_round(
        self,
        round_id: str,
        matches: List[Dict],
        game_type: str = '승무패'
    ) -> ProtoAnalysisResult:
        """
        회차 전체 분석 (14경기)

        Args:
            round_id: 회차 ID (예: '2024001')
            matches: 경기 리스트
                [
                    {
                        'match_id': 'xxx',
                        'match_number': 1,
                        'home_team': 'Arsenal',
                        'away_team': 'Liverpool',
                        'league': 'Premier League',
                        'match_time': '2024-01-15 20:00',
                        'model_predictions': [
                            {'provider': 'GPT-4', 'probabilities': {'H': 0.5, 'D': 0.3, 'A': 0.2}},
                            ...
                        ],
                        'team_stats': {...},
                        'recent_form': {...}
                    },
                    ...
                ]
            game_type: '승무패' or '승5패'

        Returns:
            ProtoAnalysisResult
        """

        markings = []

        # 1. 각 경기 분석
        for match in matches:
            marking = self._analyze_single_match(match)
            markings.append(marking)

        # 2. 이변 가능성 순으로 정렬하여 복수 베팅 경기 선택
        upset_ranked = sorted(
            markings,
            key=lambda x: x.upset_probability,
            reverse=True
        )

        # 복수 베팅 경기 (이변 확률 높은 상위 4개)
        multiple_bet_count = self.MULTIPLE_BET_COUNT if game_type == '승무패' else 0
        multiple_bet_matches = [
            m for m in upset_ranked[:multiple_bet_count] if m.is_upset_prone
        ]

        # 복수 베팅 플래그 설정
        multiple_bet_ids = {m.match_id for m in multiple_bet_matches}
        for marking in markings:
            marking.is_multiple_bet = marking.match_id in multiple_bet_ids

        # 3. 통계 계산
        high_confidence_count = sum(
            1 for m in markings if m.model_agreement >= 0.75
        )
        upset_prone_count = sum(
            1 for m in markings if m.is_upset_prone
        )
        avg_agreement = statistics.mean(
            m.model_agreement for m in markings
        ) if markings else 0

        # 4. 전략 추천
        strategy, strategy_reasoning = self._recommend_strategy(
            markings, multiple_bet_matches, game_type
        )

        return ProtoAnalysisResult(
            round_id=round_id,
            analyzed_at=datetime.now().isoformat(),
            game_type=game_type,
            markings=sorted(markings, key=lambda x: x.match_number),
            multiple_bet_matches=multiple_bet_matches,
            high_confidence_count=high_confidence_count,
            upset_prone_count=upset_prone_count,
            average_model_agreement=avg_agreement,
            recommended_strategy=strategy,
            strategy_reasoning=strategy_reasoning
        )

    def _analyze_single_match(self, match: Dict) -> MatchMarking:
        """단일 경기 분석"""

        model_predictions = match.get('model_predictions', [])
        team_stats = match.get('team_stats', {})
        recent_form = match.get('recent_form', {})

        # 1. AI 합의 확률 계산 (모델 평균)
        consensus_probs = self._calculate_consensus(model_predictions)
        consensus_outcome = max(consensus_probs, key=consensus_probs.get)
        consensus_probability = consensus_probs[consensus_outcome]

        # 2. 모델 합의도 계산
        model_agreement = self._calculate_model_agreement(model_predictions)

        # 3. 이변 신호 탐지
        upset_signals = []

        # 3-1. 확률 분포 애매함
        ambiguous_signal = self._detect_ambiguous_probability(consensus_probs)
        if ambiguous_signal:
            upset_signals.append(ambiguous_signal)

        # 3-2. 모델 간 불일치
        disagreement_signal = self._detect_model_disagreement(model_predictions)
        if disagreement_signal:
            upset_signals.append(disagreement_signal)

        # 3-3. 폼 상충
        if recent_form:
            form_signal = self._detect_form_conflict(recent_form, consensus_probs)
            if form_signal:
                upset_signals.append(form_signal)

        # 3-4. 랭킹 불일치
        if team_stats:
            rank_signal = self._detect_rank_mismatch(
                team_stats, consensus_probs,
                match.get('home_team', ''), match.get('away_team', '')
            )
            if rank_signal:
                upset_signals.append(rank_signal)

        # 4. 이변 확률 계산
        upset_prob = self._calculate_upset_probability(upset_signals, model_agreement)
        is_upset_prone = upset_prob >= self.UPSET_THRESHOLD

        # 5. 복수 베팅 추천
        recommended_outcomes = self._recommend_outcomes(
            consensus_probs, is_upset_prone
        )

        # 6. 분석 근거
        reasoning = self._generate_reasoning(
            consensus_outcome, consensus_probability,
            upset_signals, model_agreement
        )

        return MatchMarking(
            match_id=match.get('match_id', ''),
            match_number=match.get('match_number', 0),
            home_team=match.get('home_team', ''),
            away_team=match.get('away_team', ''),
            league=match.get('league', ''),
            match_time=match.get('match_time', ''),
            consensus_outcome=consensus_outcome,
            consensus_probability=consensus_probability,
            upset_probability=upset_prob,
            is_upset_prone=is_upset_prone,
            upset_signals=upset_signals,
            recommended_outcomes=recommended_outcomes,
            is_multiple_bet=False,  # 나중에 설정
            reasoning=reasoning,
            model_agreement=model_agreement
        )

    def _calculate_consensus(
        self,
        model_predictions: List[Dict]
    ) -> Dict[str, float]:
        """AI 모델들의 합의 확률 계산 (평균)"""

        if not model_predictions:
            return {'H': 0.33, 'D': 0.34, 'A': 0.33}

        # 각 결과별 확률 수집
        outcome_probs = {'H': [], 'D': [], 'A': []}

        for pred in model_predictions:
            probs = pred.get('probabilities', {})
            for outcome in ['H', 'D', 'A']:
                if outcome in probs:
                    outcome_probs[outcome].append(probs[outcome])

        # 평균 계산
        consensus = {}
        for outcome, probs in outcome_probs.items():
            if probs:
                consensus[outcome] = statistics.mean(probs)
            else:
                consensus[outcome] = 0.33

        # 정규화 (합이 1이 되도록)
        total = sum(consensus.values())
        if total > 0:
            consensus = {k: v/total for k, v in consensus.items()}

        return consensus

    def _calculate_model_agreement(
        self,
        model_predictions: List[Dict]
    ) -> float:
        """모델 합의도 계산 (0-1)"""

        if not model_predictions or len(model_predictions) < 2:
            return 0.5

        # 각 모델이 선택한 최선의 결과
        best_outcomes = []
        for pred in model_predictions:
            probs = pred.get('probabilities', {})
            if probs:
                best = max(probs, key=probs.get)
                best_outcomes.append(best)

        if not best_outcomes:
            return 0.5

        # 가장 많이 선택된 결과의 비율
        from collections import Counter
        counter = Counter(best_outcomes)
        most_common_count = counter.most_common(1)[0][1]
        agreement = most_common_count / len(best_outcomes)

        return agreement

    def _detect_ambiguous_probability(
        self,
        probabilities: Dict[str, float]
    ) -> Optional[UpsetSignal]:
        """확률 분포 애매함 감지"""

        sorted_probs = sorted(probabilities.values(), reverse=True)

        if len(sorted_probs) >= 2:
            diff = sorted_probs[0] - sorted_probs[1]

            if diff <= self.AMBIGUOUS_THRESHOLD:
                strength = min(100, (self.AMBIGUOUS_THRESHOLD - diff) * 400)

                return UpsetSignal(
                    signal_type='ambiguous',
                    strength=strength,
                    description=f'확률 분포 애매함 (1위: {sorted_probs[0]:.1%}, 2위: {sorted_probs[1]:.1%})',
                    evidence={
                        'top_prob': sorted_probs[0],
                        'second_prob': sorted_probs[1],
                        'difference': diff
                    }
                )

        return None

    def _detect_model_disagreement(
        self,
        model_predictions: List[Dict]
    ) -> Optional[UpsetSignal]:
        """모델 간 불일치 감지"""

        if not model_predictions or len(model_predictions) < 2:
            return None

        # 각 결과별 표준편차
        outcome_stds = {}
        for outcome in ['H', 'D', 'A']:
            probs = []
            for pred in model_predictions:
                p = pred.get('probabilities', {}).get(outcome, 0)
                probs.append(p)

            if len(probs) >= 2:
                outcome_stds[outcome] = statistics.stdev(probs)

        if not outcome_stds:
            return None

        max_std = max(outcome_stds.values())

        if max_std >= self.DISAGREEMENT_THRESHOLD:
            strength = min(100, (max_std / self.DISAGREEMENT_THRESHOLD) * 80)

            return UpsetSignal(
                signal_type='disagreement',
                strength=strength,
                description=f'모델 간 의견 불일치 (표준편차: {max_std:.1%})',
                evidence={
                    'max_std': max_std,
                    'outcome_stds': outcome_stds
                }
            )

        return None

    def _detect_form_conflict(
        self,
        recent_form: Dict,
        probabilities: Dict[str, float]
    ) -> Optional[UpsetSignal]:
        """최근 폼과 예측 상충 감지"""

        home_form = recent_form.get('home', [])
        away_form = recent_form.get('away', [])

        if not home_form or not away_form:
            return None

        # 최근 5경기 승률
        def win_rate(form_list):
            if not form_list:
                return 0
            wins = sum(1 for r in form_list[:5] if r == 'W')
            return wins / min(5, len(form_list))

        home_wr = win_rate(home_form)
        away_wr = win_rate(away_form)

        home_prob = probabilities.get('H', 0)
        away_prob = probabilities.get('A', 0)

        # 원정팀 폼이 더 좋은데 홈팀 승률이 높으면 상충
        if away_wr > home_wr + 0.2 and home_prob > away_prob + 0.1:
            strength = min(100, (away_wr - home_wr + home_prob - away_prob) * 100)

            return UpsetSignal(
                signal_type='form_conflict',
                strength=strength,
                description=f'폼-예측 상충 (원정 폼: {away_wr:.1%} vs 홈승 확률: {home_prob:.1%})',
                evidence={
                    'home_win_rate': home_wr,
                    'away_win_rate': away_wr,
                    'home_prob': home_prob,
                    'away_prob': away_prob
                }
            )

        return None

    def _detect_rank_mismatch(
        self,
        team_stats: Dict,
        probabilities: Dict[str, float],
        home_team: str,
        away_team: str
    ) -> Optional[UpsetSignal]:
        """팀 랭킹과 예측 불일치 감지"""

        home_stats = team_stats.get('home', {})
        away_stats = team_stats.get('away', {})

        home_rank = home_stats.get('league_rank', 999)
        away_rank = away_stats.get('league_rank', 999)

        if home_rank == 999 or away_rank == 999:
            return None

        rank_diff = abs(home_rank - away_rank)

        if rank_diff >= 5:  # 5위 이상 차이
            # 강팀이 원정인데 원정 승률이 낮으면 이상
            if away_rank < home_rank:
                away_prob = probabilities.get('A', 0)
                if away_prob < 0.45:
                    strength = min(100, rank_diff * 12)

                    return UpsetSignal(
                        signal_type='rank_mismatch',
                        strength=strength,
                        description=f'강팀({away_team}, {away_rank}위) 원정인데 낮은 승률',
                        evidence={
                            'home_rank': home_rank,
                            'away_rank': away_rank,
                            'rank_diff': rank_diff,
                            'away_prob': away_prob
                        }
                    )

        return None

    def _calculate_upset_probability(
        self,
        signals: List[UpsetSignal],
        model_agreement: float
    ) -> float:
        """이변 확률 계산 (0-100)"""

        if not signals:
            return 0

        # 신호 강도의 가중 평균
        weights = {
            'ambiguous': 0.35,
            'disagreement': 0.30,
            'form_conflict': 0.20,
            'rank_mismatch': 0.15
        }

        total_weight = sum(weights.get(s.signal_type, 0.1) for s in signals)
        weighted_sum = sum(
            s.strength * weights.get(s.signal_type, 0.1)
            for s in signals
        )

        base_upset_prob = weighted_sum / total_weight if total_weight > 0 else 0

        # 모델 합의도가 낮으면 이변 확률 증가
        disagreement_penalty = (1 - model_agreement) * 20

        return min(100, base_upset_prob + disagreement_penalty)

    def _recommend_outcomes(
        self,
        probabilities: Dict[str, float],
        is_upset_prone: bool
    ) -> List[str]:
        """베팅 결과 추천"""

        sorted_outcomes = sorted(
            probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )

        if not is_upset_prone:
            # 단일 베팅 (최고 확률)
            return [sorted_outcomes[0][0]]

        # 복수 베팅 (확률 차이가 20% 이하인 상위 2개)
        if len(sorted_outcomes) >= 2:
            top_prob = sorted_outcomes[0][1]
            second_prob = sorted_outcomes[1][1]

            if (top_prob - second_prob) <= 0.20:
                return [sorted_outcomes[0][0], sorted_outcomes[1][0]]

        # 기본: 최고 확률 1개
        return [sorted_outcomes[0][0]]

    def _generate_reasoning(
        self,
        outcome: str,
        probability: float,
        signals: List[UpsetSignal],
        agreement: float
    ) -> str:
        """분석 근거 생성"""

        outcome_labels = {'H': '홈승', 'D': '무승부', 'A': '원정승'}
        outcome_label = outcome_labels.get(outcome, outcome)

        if not signals:
            return f"{outcome_label} 예상 ({probability:.1%}), AI 합의도 {agreement:.1%}"

        signal_descs = [s.description for s in signals[:2]]  # 상위 2개
        return f"{outcome_label} 예상 ({probability:.1%}), 이변 신호: {', '.join(signal_descs)}"

    def _recommend_strategy(
        self,
        markings: List[MatchMarking],
        multiple_bet_matches: List[MatchMarking],
        game_type: str
    ) -> Tuple[str, str]:
        """전략 추천"""

        high_conf_count = sum(1 for m in markings if m.model_agreement >= 0.75)
        upset_count = len(multiple_bet_matches)

        if game_type == '승5패':
            # 승5패: 안정적 전략
            if high_conf_count >= 12:
                return ('안정형', '12개 이상 고신뢰 경기, 단일 베팅 권장')
            else:
                return ('신중형', '불확실한 경기 다수, 추가 분석 필요')

        else:  # 승무패
            if upset_count == 0:
                return ('단일 베팅', '이변 가능성 낮음, 모든 경기 단일 선택')
            elif upset_count <= 2:
                return ('소량 복수', f'{upset_count}개 경기만 복수 베팅')
            else:
                return ('복수 베팅', f'{upset_count}개 경기 복수 베팅으로 안정성 확보')

    def format_marking_list(self, result: ProtoAnalysisResult) -> str:
        """마킹 리스트 텍스트 포맷"""

        lines = []
        lines.append(f"=" * 60)
        lines.append(f"프로토 {result.game_type} {result.round_id}회 AI 분석 결과")
        lines.append(f"분석 시각: {result.analyzed_at}")
        lines.append(f"=" * 60)
        lines.append("")

        for marking in result.markings:
            multiple_mark = " [복수]" if marking.is_multiple_bet else ""

            lines.append(f"[{marking.match_number:02d}] {marking.home_team} vs {marking.away_team}{multiple_mark}")

            # 팀명을 포함한 동적 라벨 생성
            def get_outcome_label(outcome: str) -> str:
                if outcome == 'H':
                    return f"1 ({marking.home_team} 홈승)"
                elif outcome == 'D':
                    return "X (무승부)"
                elif outcome == 'A':
                    return f"2 ({marking.away_team} 원정승)"
                return outcome

            if marking.is_multiple_bet:
                outcomes_str = ", ".join(
                    get_outcome_label(o) for o in marking.recommended_outcomes
                )
                lines.append(f"     → {outcomes_str}")
            else:
                outcome_str = get_outcome_label(marking.consensus_outcome)
                lines.append(f"     → {outcome_str} ({marking.consensus_probability:.1%})")

            lines.append(f"     {marking.reasoning}")
            lines.append("")

        lines.append(f"-" * 60)
        lines.append(f"고신뢰 경기: {result.high_confidence_count}개")
        lines.append(f"복수 베팅 경기: {result.upset_prone_count}개")
        lines.append(f"평균 AI 합의도: {result.average_model_agreement:.1%}")
        lines.append(f"추천 전략: {result.recommended_strategy}")
        lines.append(f"전략 근거: {result.strategy_reasoning}")
        lines.append(f"=" * 60)

        return "\n".join(lines)

    def to_dict(self, result: ProtoAnalysisResult) -> Dict:
        """결과를 딕셔너리로 변환"""

        return {
            'round_id': result.round_id,
            'analyzed_at': result.analyzed_at,
            'game_type': result.game_type,
            'markings': [
                {
                    **asdict(m),
                    'upset_signals': [asdict(s) for s in m.upset_signals]
                }
                for m in result.markings
            ],
            'multiple_bet_matches': [
                {
                    **asdict(m),
                    'upset_signals': [asdict(s) for s in m.upset_signals]
                }
                for m in result.multiple_bet_matches
            ],
            'statistics': {
                'high_confidence_count': result.high_confidence_count,
                'upset_prone_count': result.upset_prone_count,
                'average_model_agreement': result.average_model_agreement
            },
            'strategy': {
                'recommended_strategy': result.recommended_strategy,
                'strategy_reasoning': result.strategy_reasoning
            }
        }
