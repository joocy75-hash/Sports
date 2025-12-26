"""
WebSocket 연결 관리자
실시간 배당 변동, 라이브 스코어 등을 브로드캐스트
"""

from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
import logging
from datetime import datetime
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 연결 관리"""

    def __init__(self):
        # 활성 연결들 {connection_id: WebSocket}
        self.active_connections: Dict[str, WebSocket] = {}

        # 채널별 구독자 {channel: set(connection_ids)}
        self.channel_subscribers: Dict[str, Set[str]] = {
            "odds": set(),      # 배당 변동
            "scores": set(),    # 라이브 스코어
            "predictions": set(),  # 새 예측
            "alerts": set(),    # 긴급 알림 (Value Bet, Sharp Money)
        }

        # Redis client (Pub/Sub용)
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, connection_id: str) -> None:
        """WebSocket 연결 수락"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f"✅ WebSocket connected: {connection_id}")

        # 연결 환영 메시지
        await self.send_personal_message(
            {
                "type": "connection",
                "status": "connected",
                "connection_id": connection_id,
                "timestamp": datetime.now().isoformat()
            },
            websocket
        )

    def disconnect(self, connection_id: str) -> None:
        """WebSocket 연결 종료"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        # 모든 채널에서 구독 해제
        for channel in self.channel_subscribers.values():
            channel.discard(connection_id)

        logger.info(f"❌ WebSocket disconnected: {connection_id}")

    async def send_personal_message(self, message: dict, websocket: WebSocket) -> None:
        """특정 클라이언트에게 메시지 전송"""
        try:
            await websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    async def broadcast(self, channel: str, message: dict) -> None:
        """특정 채널 구독자들에게 브로드캐스트"""
        if channel not in self.channel_subscribers:
            logger.warning(f"Unknown channel: {channel}")
            return

        subscribers = self.channel_subscribers[channel]
        logger.info(f"📡 Broadcasting to {len(subscribers)} subscribers on '{channel}' channel")

        # 메시지에 타입과 채널 추가
        message["channel"] = channel
        message["timestamp"] = datetime.now().isoformat()

        # 비동기로 모든 구독자에게 전송
        disconnected = []
        for connection_id in subscribers:
            if connection_id in self.active_connections:
                try:
                    websocket = self.active_connections[connection_id]
                    await websocket.send_text(json.dumps(message, ensure_ascii=False))
                except WebSocketDisconnect:
                    disconnected.append(connection_id)
                except Exception as e:
                    logger.error(f"Error sending to {connection_id}: {e}")
                    disconnected.append(connection_id)

        # 연결 끊긴 클라이언트 정리
        for connection_id in disconnected:
            self.disconnect(connection_id)

    def subscribe(self, connection_id: str, channel: str) -> bool:
        """채널 구독"""
        if channel not in self.channel_subscribers:
            logger.warning(f"Unknown channel: {channel}")
            return False

        self.channel_subscribers[channel].add(connection_id)
        logger.info(f"🔔 {connection_id} subscribed to '{channel}'")
        return True

    def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """채널 구독 해제"""
        if channel not in self.channel_subscribers:
            return False

        self.channel_subscribers[channel].discard(connection_id)
        logger.info(f"🔕 {connection_id} unsubscribed from '{channel}'")
        return True

    async def initialize_redis(self, redis_url: str = "redis://localhost:6379") -> None:
        """Redis Pub/Sub 초기화"""
        try:
            self.redis_client = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True
            )

            # Pub/Sub 리스너 시작
            self.pubsub_task = asyncio.create_task(self._redis_listener())
            logger.info("✅ Redis Pub/Sub initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")

    async def _redis_listener(self) -> None:
        """Redis Pub/Sub 메시지 리스너"""
        if not self.redis_client:
            return

        pubsub = self.redis_client.pubsub()

        # 모든 채널 구독
        await pubsub.subscribe("odds", "scores", "predictions", "alerts")

        logger.info("🎧 Redis listener started")

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    data = json.loads(message["data"])

                    # WebSocket 클라이언트들에게 브로드캐스트
                    await self.broadcast(channel, data)

        except asyncio.CancelledError:
            logger.info("Redis listener stopped")
            await pubsub.unsubscribe()
            await pubsub.close()

    async def publish_to_redis(self, channel: str, message: dict) -> None:
        """Redis로 메시지 발행 (다른 서버 인스턴스에 전파)"""
        if not self.redis_client:
            logger.warning("Redis client not initialized")
            return

        try:
            await self.redis_client.publish(
                channel,
                json.dumps(message, ensure_ascii=False)
            )
            logger.info(f"📤 Published to Redis channel '{channel}'")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

    async def shutdown(self) -> None:
        """종료 시 정리"""
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass

        if self.redis_client:
            await self.redis_client.close()

        logger.info("WebSocket manager shutdown complete")


# 전역 매니저 인스턴스
manager = ConnectionManager()
