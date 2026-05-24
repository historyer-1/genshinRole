from __future__ import annotations

import re
from mem0 import Memory
from memory.config import mem0_cfg
from memory.pgcon_pool import get_pool


def count_tokens(text: str) -> int:
    """
    统计文本 token 数。

    Args:
        text: 需要统计的文本内容。
    """
    tokens = re.findall(r"[一-鿿]|[a-zA-Z0-9_]+", text)
    return len(tokens)


async def save_chat(user_id: str, user_text: str, assistant_text: str) -> None:
    """
    持久化一轮聊天记录。

    Args:
        user_id: 用户唯一标识（已包含角色信息，格式如 "user123_派蒙"）。
        user_text: 用户输入文本。
        assistant_text: 助手回复文本。
    """
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.executemany(
                """
                INSERT INTO chat_history (user_id, message_role, dialog_text, token_count)
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (user_id, "user", user_text, count_tokens(user_text)),
                    (user_id, "assistant", assistant_text, count_tokens(assistant_text)),
                ],
            )
        await conn.commit()


async def save_summary(user_id: str, summary_text: str) -> None:
    """
    持久化聊天摘要（无则新增，有则更新）。

    Args:
        user_id: 用户唯一标识。
        summary_text: 摘要内容。
    """
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO chat_summary (user_id, summary_content, token_count, created_at, updated_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET summary_content = EXCLUDED.summary_content,
                    token_count = EXCLUDED.token_count,
                    updated_at = NOW()
                """,
                (user_id, summary_text, count_tokens(summary_text)),
            )
        await conn.commit()


async def del_chat(user_id: str) -> None:
    """
    删除 user_id 对应的 PostgreSQL 中的对话历史和摘要。

    Args:
        user_id: 用户唯一标识。
    """
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM chat_history WHERE user_id = %s", (user_id,))
            await cur.execute("DELETE FROM chat_summary WHERE user_id = %s", (user_id,))
        await conn.commit()


async def load_recent_chats(user_id: str, limit: int = 5, offset: int = 0) -> list[dict[str, str]]:
    """
    从 PostgreSQL 加载最近的聊天记录，按时间正序返回。

    Args:
        user_id: 用户唯一标识（已包含角色信息）。
        limit: 返回的最大消息条数（每条为一轮中的一方，即 user 或 assistant 各算一条）。
        offset: 跳过的消息条数，用于分页（offset=0 表示从最新记录开始）。
    """
    async with get_pool().connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT message_role, dialog_text
                FROM chat_history
                WHERE user_id = %s
                ORDER BY record_id DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, limit, offset),
            )
            rows = await cur.fetchall()
    # 反转为时间正序
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


def del_memory(user_id: str) -> None:
    """
    删除 user_id 对应的 mem0 长期记忆。

    Args:
        user_id: 用户唯一标识。
    """
    mem = Memory.from_config(mem0_cfg())
    mem.delete_all(user_id=user_id)
