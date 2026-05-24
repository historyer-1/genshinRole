from __future__ import annotations

import os

from dotenv import find_dotenv, load_dotenv


def mem0_cfg() -> dict:
    """
    读取根目录 .env 并组装 mem0 开源版配置。

    配置包含三部分：
    1. llm：mem0 在抽取/更新记忆时使用的模型配置；
    2. embedder：mem0 在检索与写入时使用的向量模型配置；
    3. vector_store：mem0 连接的 qdrant 向量库配置（这里使用 docker 暴露端口）。
    """
    # 在 memory 模块内主动加载 .env，避免调用方忘记 load_dotenv 时出现配置缺失。
    load_dotenv(find_dotenv(), override=True)

    qdrant_host = os.getenv("qdrant_host")
    qdrant_port = int(os.getenv("qdrant_port"))
    embedding_dims = int(os.getenv("embedding_dims", "1536"))

    # 这里显式指定 openai 兼容 provider，并把 base_url 指向 .env 中已有的兼容网关。
    # 对于你当前环境（DashScope OpenAI 兼容接口）可直接复用 model/api_key/base_url。
    # custom_instructions 用于控制 mem0 的记忆抽取语言与风格。
    # 这里强制要求“写入长期记忆时使用中文”，从而保证后续检索、拼接上下文时语种一致。
    cn_memory_rules = (
        "你是长期记忆抽取器。请严格使用中文输出记忆内容，不要使用英文句子。"
        "在保留专有名词（如 API 名称、模型名、函数名）时可以保留原文，但说明必须是中文。"
        "只提取可长期复用的信息：用户偏好、稳定事实、约束条件、长期目标、已确认结论。"
        "不要记录寒暄、一次性噪声、无效重复信息。"
    )

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
                "api_key": os.getenv("embedding_key"),
                "openai_base_url": os.getenv("embedding_url"),
                "embedding_dims": embedding_dims,
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                # collection_name 单独用于 mem0 长期记忆，避免与你现有知识库集合冲突。
                "collection_name": os.getenv("mem0_collection", "mem0_long_memory"),
                "host": qdrant_host,
                "port": qdrant_port,
                "embedding_model_dims": embedding_dims,
                "on_disk": True,
            },
        },
        "custom_instructions": cn_memory_rules,
    }
