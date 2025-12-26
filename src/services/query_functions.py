"""
DB 쿼리 함수들 - OpenAI Function Calling용
각 함수는 GPT-4가 자동으로 호출할 수 있는 도구입니다.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload, aliased
import logging

from src.db.models import Match, Team, League, PredictionLog, OddsHistory, TeamStats
from src.db.session import get_session

logger = logging.getLogger(__name__)


async def get_today_matches(session: AsyncSession) -> List[Dict]:
    """
    오늘 예정된 모든 경기를 조회합니다.

    Returns:
        List[Dict]: 경기 목록 (홈팀, 원정팀, 시간, 리그 정보)
    """
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        stmt = (
            select(Match)
            .options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league)
            )
            .where(
                and_(
                    Match.start_time >= today_start,
                    Match.start_time < today_end
                )
            )
            .order_by(Match.start_time)
            .limit(50)
        )

        result = await session.execute(stmt)
        matches = result.unique().scalars().all()

        return [
            {
                "id": match.id,
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "start_time": match.start_time.isoformat() if match.start_time else None,
                "league": match.league.name if match.league else "Unknown",
                "status": match.status
            }
            for match in matches
        ]
    except Exception as e:
        logger.error(f"Error fetching today's matches: {e}", exc_info=True)
        return []


async def get_match_by_teams(
    home_team: str,
    away_team: str,
    session: AsyncSession,
    days_ahead: int = 7
) -> Optional[Dict]:
    """
    특정 팀의 경기를 조회합니다.

    Args:
        home_team: 홈팀 이름 (부분 일치 가능)
        away_team: 원정팀 이름 (부분 일치 가능)
        days_ahead: 앞으로 조회할 일수

    Returns:
        Dict: 경기 정보 또는 None
    """
    try:
        future_date = datetime.now() + timedelta(days=days_ahead)

        # 모든 upcoming 경기를 가져온 후 메모리에서 필터링
        stmt = (
            select(Match)
            .options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league)
            )
            .where(
                and_(
                    Match.start_time >= datetime.now(),
                    Match.start_time <= future_date
                )
            )
            .order_by(Match.start_time)
            .limit(100)  # 성능을 위해 최대 100경기만 조회
        )

        result = await session.execute(stmt)
        matches = result.unique().scalars().all()

        # 메모리에서 팀 이름으로 필터링
        for match in matches:
            home_name = match.home_team.name.lower() if match.home_team else ""
            away_name = match.away_team.name.lower() if match.away_team else ""
            search_home = home_team.lower()
            search_away = away_team.lower()

            # 홈팀과 원정팀이 일치하는지 확인 (양방향)
            if ((search_home in home_name or search_home in away_name) and
                (search_away in away_name or search_away in home_name)):
                return {
                    "id": match.id,
                    "home_team": match.home_team.name if match.home_team else "Unknown",
                    "away_team": match.away_team.name if match.away_team else "Unknown",
                    "start_time": match.start_time.isoformat() if match.start_time else None,
                    "league": match.league.name if match.league else "Unknown",
                    "status": match.status
                }

        return None
    except Exception as e:
        logger.error(f"Error fetching match by teams: {e}", exc_info=True)
        return None


async def get_predictions(
    session: AsyncSession,
    confidence_min: float = 0.6,
    limit: int = 10
) -> List[Dict]:
    """
    AI 예측 결과를 조회합니다.

    Args:
        confidence_min: 최소 신뢰도 (0.0 ~ 1.0)
        limit: 최대 반환 개수

    Returns:
        List[Dict]: 예측 목록
    """
    try:
        # Match와 Team을 join하여 eager loading
        stmt = (
            select(PredictionLog, Match)
            .join(Match, PredictionLog.match_id == Match.id)
            .options(
                joinedload(PredictionLog.match).joinedload(Match.home_team),
                joinedload(PredictionLog.match).joinedload(Match.away_team),
                joinedload(PredictionLog.match).joinedload(Match.league)
            )
            .order_by(desc(PredictionLog.created_at))
            .limit(limit * 2)  # 필터링을 위해 더 많이 가져옴
        )

        result = await session.execute(stmt)
        rows = result.unique().all()

        predictions = []
        for pred, match in rows:
            # 신뢰도 계산 (가장 높은 확률)
            probs = {
                "home": pred.prob_home,
                "draw": pred.prob_draw,
                "away": pred.prob_away
            }
            predicted_outcome = max(probs, key=probs.get)
            confidence = probs[predicted_outcome]

            # 최소 신뢰도 필터링
            if confidence < confidence_min:
                continue

            # Edge 계산 (value가 있으면)
            values = {
                "home": pred.value_home or 0.0,
                "draw": pred.value_draw or 0.0,
                "away": pred.value_away or 0.0
            }
            edge = values.get(predicted_outcome, 0.0)

            predictions.append({
                "match_id": pred.match_id,
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "league": match.league.name if match.league else "Unknown",
                "predicted_outcome": predicted_outcome,
                "confidence": float(confidence),
                "probabilities": {
                    "home": float(pred.prob_home),
                    "draw": float(pred.prob_draw),
                    "away": float(pred.prob_away)
                },
                "edge": float(edge),
                "expected_scores": {
                    "home": float(pred.expected_score_home) if pred.expected_score_home else None,
                    "away": float(pred.expected_score_away) if pred.expected_score_away else None
                },
                "timestamp": pred.created_at.isoformat() if pred.created_at else None
            })

            if len(predictions) >= limit:
                break

        return predictions
    except Exception as e:
        logger.error(f"Error fetching predictions: {e}", exc_info=True)
        return []


async def get_team_stats(team_name: str, session: AsyncSession) -> Optional[Dict]:
    """
    팀의 최근 통계를 조회합니다.

    Args:
        team_name: 팀 이름 (부분 일치)

    Returns:
        Dict: 팀 통계 또는 None
    """
    try:
        stmt = (
            select(TeamStats)
            .join(Team, TeamStats.team_id == Team.id)
            .where(Team.name.ilike(f"%{team_name}%"))
            .order_by(desc(TeamStats.updated_at))
        )

        result = await session.execute(stmt)
        stats = result.scalar_one_or_none()

        if not stats:
            return None

        return {
            "team_name": team_name,
            "games_played": stats.games_played,
            "wins": stats.wins,
            "draws": stats.draws,
            "losses": stats.losses,
            "goals_for": stats.goals_for,
            "goals_against": stats.goals_against,
            "avg_xg": float(stats.avg_xg) if stats.avg_xg else None,
            "avg_xga": float(stats.avg_xga) if stats.avg_xga else None,
            "form": stats.recent_form
        }
    except Exception as e:
        logger.error(f"Error fetching team stats: {e}")
        return None


async def get_value_bets(
    session: AsyncSession,
    edge_min: float = 0.05,
    limit: int = 10
) -> List[Dict]:
    """
    Value Bet(시장 대비 저평가된 베팅)을 조회합니다.

    Args:
        edge_min: 최소 Edge (기댓값)
        limit: 최대 반환 개수

    Returns:
        List[Dict]: Value Bet 목록
    """
    try:
        # 최근 24시간 예측 조회
        cutoff_time = datetime.now() - timedelta(hours=24)

        stmt = (
            select(PredictionLog, Match)
            .join(Match, PredictionLog.match_id == Match.id)
            .options(
                joinedload(PredictionLog.match).joinedload(Match.home_team),
                joinedload(PredictionLog.match).joinedload(Match.away_team),
                joinedload(PredictionLog.match).joinedload(Match.league)
            )
            .where(PredictionLog.created_at >= cutoff_time)
            .order_by(desc(PredictionLog.created_at))
            .limit(limit * 3)  # 필터링을 위해 더 많이 가져옴
        )

        result = await session.execute(stmt)
        rows = result.unique().all()

        value_bets = []
        for pred, match in rows:
            # 각 결과에 대한 edge 계산
            values = {
                "home": pred.value_home or 0.0,
                "draw": pred.value_draw or 0.0,
                "away": pred.value_away or 0.0
            }

            # 가장 높은 edge 찾기
            best_outcome = max(values, key=values.get)
            best_edge = values[best_outcome]

            if best_edge < edge_min:
                continue

            # 해당 결과의 확률과 배당
            probs = {
                "home": pred.prob_home,
                "draw": pred.prob_draw,
                "away": pred.prob_away
            }
            odds_map = {
                "home": match.odds_home or 0.0,
                "draw": match.odds_draw or 0.0,
                "away": match.odds_away or 0.0
            }

            value_bets.append({
                "match_id": pred.match_id,
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "league": match.league.name if match.league else "Unknown",
                "bet_on": best_outcome,
                "ai_probability": float(probs[best_outcome]),
                "market_odds": float(odds_map[best_outcome]),
                "edge": float(best_edge),
                "value_score": float(best_edge * probs[best_outcome])
            })

            if len(value_bets) >= limit:
                break

        return value_bets
    except Exception as e:
        logger.error(f"Error fetching value bets: {e}", exc_info=True)
        return []


async def get_live_matches(session: AsyncSession) -> List[Dict]:
    """
    현재 진행 중인 라이브 경기를 조회합니다.

    Returns:
        List[Dict]: 라이브 경기 목록
    """
    try:
        stmt = (
            select(Match)
            .options(
                joinedload(Match.home_team),
                joinedload(Match.away_team),
                joinedload(Match.league)
            )
            .where(Match.status.in_(['LIVE', 'IN_PLAY', 'HT']))  # 라이브 상태
            .order_by(Match.start_time)
            .limit(20)
        )

        result = await session.execute(stmt)
        matches = result.unique().scalars().all()

        return [
            {
                "id": match.id,
                "home_team": match.home_team.name if match.home_team else "Unknown",
                "away_team": match.away_team.name if match.away_team else "Unknown",
                "score": f"{match.score_home}-{match.score_away}" if match.score_home is not None else "0-0",
                "status": match.status,
                "league": match.league.name if match.league else "Unknown"
            }
            for match in matches
        ]
    except Exception as e:
        logger.error(f"Error fetching live matches: {e}", exc_info=True)
        return []


# Function Calling용 함수 스키마 정의
FUNCTION_SCHEMAS = [
    {
        "name": "get_today_matches",
        "description": "오늘 예정된 모든 경기를 조회합니다. 사용자가 '오늘 경기', '오늘 일정', 'today matches' 등을 물을 때 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_match_by_teams",
        "description": "특정 팀의 경기를 조회합니다. 사용자가 '맨시티 경기', 'Liverpool vs Chelsea', '토트넘 언제 해?' 등을 물을 때 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {
                "home_team": {
                    "type": "string",
                    "description": "홈팀 이름 (예: 'Manchester City', '맨시티', 'Liverpool')"
                },
                "away_team": {
                    "type": "string",
                    "description": "원정팀 이름 (예: 'Arsenal', '아스날', 'Chelsea')"
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "앞으로 조회할 일수 (기본값: 7일)",
                    "default": 7
                }
            },
            "required": ["home_team", "away_team"]
        }
    },
    {
        "name": "get_predictions",
        "description": "AI 예측 결과를 조회합니다. 사용자가 '추천 픽', '예측', 'predictions', '베팅 추천' 등을 물을 때 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {
                "confidence_min": {
                    "type": "number",
                    "description": "최소 신뢰도 (0.0~1.0, 기본값: 0.6)",
                    "default": 0.6
                },
                "limit": {
                    "type": "integer",
                    "description": "최대 반환 개수 (기본값: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "name": "get_team_stats",
        "description": "팀의 최근 통계를 조회합니다. 사용자가 '맨시티 성적', 'Liverpool stats', '토트넘 폼' 등을 물을 때 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "팀 이름 (예: 'Manchester City', 'Liverpool', '토트넘')"
                }
            },
            "required": ["team_name"]
        }
    },
    {
        "name": "get_value_bets",
        "description": "Value Bet(저평가된 베팅 기회)을 조회합니다. 사용자가 'value bet', '가치 베팅', '저평가 경기' 등을 물을 때 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {
                "edge_min": {
                    "type": "number",
                    "description": "최소 Edge (기댓값, 기본값: 0.05 = 5%)",
                    "default": 0.05
                },
                "limit": {
                    "type": "integer",
                    "description": "최대 반환 개수 (기본값: 10)",
                    "default": 10
                }
            },
            "required": []
        }
    },
    {
        "name": "get_live_matches",
        "description": "현재 진행 중인 라이브 경기를 조회합니다. 사용자가 '라이브 경기', '지금 하는 경기', 'live matches' 등을 물을 때 사용하세요.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]


# 함수 이름과 실제 함수 매핑
FUNCTION_MAP = {
    "get_today_matches": get_today_matches,
    "get_match_by_teams": get_match_by_teams,
    "get_predictions": get_predictions,
    "get_team_stats": get_team_stats,
    "get_value_bets": get_value_bets,
    "get_live_matches": get_live_matches
}
