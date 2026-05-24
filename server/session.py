import asyncio
import time
from dataclasses import dataclass, field

from config import SESSION_TTL_SECONDS, SESSION_CLEANUP_INTERVAL
from agent.BasicRole import BasicRole


@dataclass
class Session:
    """单个用户会话，持有独立的 BasicRole 实例。"""
    user_id: str
    role_name: str
    agent: BasicRole
    history: list = field(default_factory=list)
    last_active: float = field(default_factory=time.time)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def key(self) -> tuple[str, str]:
        return (self.user_id, self.role_name)


class SessionStore:
    """
    会话池：每个用户每个角色最多一个会话。
    键为 (user_id, role_name)。
    """

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        self._sessions: dict[tuple[str, str], Session] = {}
        self._ttl = ttl_seconds

    def get(self, user_id: str, role_name: str) -> Session | None:
        """获取已有会话并刷新活跃时间。"""
        session = self._sessions.get((user_id, role_name))
        if session is not None:
            session.last_active = time.time()
        return session

    def put(self, session: Session) -> None:
        """存入会话（创建或更新）。"""
        self._sessions[session.key] = session

    def remove(self, user_id: str, role_name: str) -> None:
        """销毁会话并释放资源。"""
        session = self._sessions.pop((user_id, role_name), None)
        if session is not None:
            session.agent.close()

    def list_user_sessions(self, user_id: str) -> list[Session]:
        """列出指定用户的所有活跃会话。"""
        return [s for (uid, _), s in self._sessions.items() if uid == user_id]

    async def cleanup_loop(self) -> None:
        """后台任务：定期清理过期会话。"""
        while True:
            now = time.time()
            expired = [
                key for key, s in self._sessions.items()
                if now - s.last_active > self._ttl
            ]
            for key in expired:
                s = self._sessions.pop(key, None)
                if s is not None:
                    s.agent.close()
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)

    def shutdown(self) -> None:
        """关闭所有会话。"""
        for session in self._sessions.values():
            session.agent.close()
        self._sessions.clear()
