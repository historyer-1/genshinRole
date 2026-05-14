from __future__ import annotations

import os
import re
from typing import Any

from mem0 import Memory


def _parse_postgres_host_and_port(postgres_url: str) -> tuple[str, int]:
    """
    解析 .env 中 postgres_url（示例：127.0.0.1:5432）得到 host 与 port。

    Args:
        postgres_url: PostgreSQL 地址配置字符串。
    """
    host, port = postgres_url.split(":")
    return host, int(port)


def _normalize_role_id(role_id: str) -> str:
    """
    规范化角色标识，确保可安全拼接到 PostgreSQL collection 名称中。

    Args:
        role_id: 角色唯一标识。
    """
    return re.sub(r"[^a-z0-9_]+", "_", role_id.lower())


def _build_mem0_collection_name(role_id: str) -> str:
    """
    按角色生成独立 collection 名称，实现“不同角色物理隔离存储”。

    Args:
        role_id: 角色唯一标识。
    """
    return f"genshin_agent_memory_{_normalize_role_id(role_id)}"


def _build_mem0_config(role_id: str) -> dict[str, Any]:
    """
    构建 mem0 开源版配置：
    1. llm 与 embedder 都走 .env 中 OpenAI 兼容接口；
    2. vector_store 使用 PostgreSQL(pgvector)；
    3. 每个 role_id 都绑定独立 collection，保证角色间记忆互不干扰。

    Args:
        role_id: 角色唯一标识。
    """
    postgres_host, postgres_port = _parse_postgres_host_and_port(os.getenv("postgres_url"))
    collection_name = _build_mem0_collection_name(role_id)

    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": os.getenv("model"),
                "api_key": os.getenv("api_key"),
                "openai_base_url": os.getenv("base_url"),
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": os.getenv("embedding_model"),
                "api_key": os.getenv("api_key"),
                "openai_base_url": os.getenv("base_url"),
                "embedding_dims": 1024,
            },
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "dbname": os.getenv("postgres_db"),
                "collection_name": collection_name,
                "embedding_model_dims": 1024,
                "user": os.getenv("postgres_user"),
                "password": os.getenv("postgres_password"),
                "host": postgres_host,
                "port": postgres_port,
                "diskann": False,
                "hnsw": False,
            },
        },
        "version": "v1.1",
    }


# 角色级客户端缓存：
# 第一次访问某个角色时初始化对应 mem0 客户端，后续复用该角色专属连接与 collection。
_ROLE_MEMORY_CLIENTS: dict[str, Memory] = {}


def _get_role_memory_client(role_id: str) -> Memory:
    """
    获取指定角色的 mem0 客户端；若不存在则初始化后缓存。

    Args:
        role_id: 角色唯一标识。
    """
    normalized_role_id = _normalize_role_id(role_id)
    if normalized_role_id not in _ROLE_MEMORY_CLIENTS:
        _ROLE_MEMORY_CLIENTS[normalized_role_id] = Memory.from_config(_build_mem0_config(normalized_role_id))
    return _ROLE_MEMORY_CLIENTS[normalized_role_id]


def save_long_term_memory(
    role_id: str,
    user_id: str,
    user_message: str,
    assistant_message: str,
) -> dict[str, Any]:
    """
    存记忆接口：将一轮完整对话写入“指定角色”的长期记忆集合。

    Args:
        role_id: 角色唯一标识，用于路由到角色专属 collection。
        user_id: 用户唯一标识，用于同一角色下的用户记忆隔离。
        user_message: 用户本轮输入。
        assistant_message: 助手本轮回复。
    """
    memory_client = _get_role_memory_client(role_id)
    dialogue_messages = [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_message},
    ]
    return memory_client.add(dialogue_messages, user_id=user_id)


def retrieve_long_term_memory(
    role_id: str,
    user_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    取记忆接口：从“指定角色”的记忆集合中，召回当前用户的相关长期记忆。

    Args:
        role_id: 角色唯一标识。
        user_id: 用户唯一标识。
        query: 本轮检索查询文本。
        top_k: 召回条数上限。
    """
    memory_client = _get_role_memory_client(role_id)
    search_result = memory_client.search(query=query, filters={"user_id": user_id}, top_k=top_k)
    return search_result["results"]


def format_long_term_memories(memory_items: list[dict[str, Any]]) -> str:
    """
    将 mem0 检索结果转成可直接注入 LLM 的上下文文本。

    Args:
        memory_items: retrieve_long_term_memory 返回的结果列表。
    """
    return "\n".join(
        f"[长期记忆{index}] {item['memory']}"
        for index, item in enumerate(memory_items, start=1)
    )


