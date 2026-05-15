from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Protocol

from mem0 import Memory
from memory.config import mem0_cfg


class MemPort(Protocol):
    """长期记忆端口协议：BasicRole 只依赖这个协议，不依赖 mem0 细节。"""

    def find(self, query: str) -> str:
        """按当前问题检索可注入提示词的长期记忆文本。"""

    def save_async(self, user: str, assistant: str) -> None:
        """异步把当前轮对话写入长期记忆。"""


class LongMem:
    """mem0 开源框架的长期记忆实现。"""

    def __init__(
        self,
        user_id: str,
        mem: Memory | None = None,
        top_k: int = 4,
        workers: int = 1,
    ) -> None:
        # user_id 是长期记忆的隔离主键：不同用户会命中不同记忆空间。
        self.user_id = user_id
        # top_k 控制每次检索最多返回几条记忆，数值越大上下文越丰富、token 成本也越高。
        self.top_k = top_k
        # mem0 的核心对象，负责记忆提取、向量检索和存储读写。
        # 未显式传入时，默认使用 memory\config.py 中从 .env 组装的开源版配置。
        self.mem = mem if mem is not None else Memory.from_config(mem0_cfg())
        # 写入线程池：把耗时的 add 调用放到后台执行，不阻塞主对话链路。
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="long-mem")

    def find(self, query: str) -> str:
        """
        从 mem0 检索与当前问题相关的用户长期记忆，并拼接成提示词片段。

        返回空字符串表示当前没有可用记忆；返回非空字符串可直接注入模型上下文。
        """
        # 使用 filters 指定 user_id，实现“同一应用多用户记忆隔离”。
        result = self.mem.search(
            query=query,
            filters={"user_id": self.user_id},
            top_k=self.top_k,
        )
        rows: List[Dict[str, Any]] = result["results"]
        if len(rows) == 0:
            return ""

        # mem0 返回的每条结果都包含 memory 字段，这里统一整理成可读列表供模型参考。
        memory_text = "\n".join(f"- {item['memory']}" for item in rows)
        return f"[长期记忆]\n{memory_text}"

    def save(self, user: str, assistant: str) -> None:
        """
        将当前轮对话写入 mem0。

        mem0 会从消息中自动抽取可长期保留的信息（偏好、事实、约束、长期目标等）。
        """
        messages = [
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
        self.mem.add(messages, user_id=self.user_id)

    def save_async(self, user: str, assistant: str) -> None:
        """异步提交写入任务，避免主线程等待长期记忆落库。"""
        self.pool.submit(self.save, user, assistant)