from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional
import os
import re
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from memory import (
    format_long_term_memories,
    retrieve_long_term_memory,
    save_long_term_memory,
)
from search.hybird_search import hybird_search


class RoleState(MessagesState):
    """扩展状态：除 messages 外，额外携带 RAG 与长期记忆上下文文本。"""

    context: str
    memory_context: str



class BasicRole:
    """基础角色类：管理提示词、模型配置，并提供 LangGraph 多轮对话模板。"""

    def __init__(
        self,
        system_prompt: str,
        user_prompt: str,
        role_id: str,
        llm: Any | None = None,
        tools:  list[BaseTool] | None = None,
        vector_collections: list[str] | None = None,
        memory_rounds: int = 7,
        memory_user_id: str = "default_user",
        memory_top_k: int = 5,
    ) -> None:
        """
        初始化基础角色实例，并构建可复用的对话图。

        Args:
            system_prompt: 系统角色提示词，定义助手行为边界与风格。
            user_prompt: 默认用户提示词，在未显式传入 user_message 时使用。
            role_id: 角色唯一标识，用于路由到对应角色的独立长期记忆集合。
            llm: 可选的外部语言模型实例；不传则按 .env 创建默认模型。
            tools: 可选工具列表；不传时默认仅启用时间工具。
            vector_collections: 可选检索集合列表；为空时跳过 RAG 检索。
            memory_rounds: 保留的近期对话轮数，超过后会触发历史压缩。
            memory_user_id: 长期记忆使用的用户标识。
            memory_top_k: 每轮从长期记忆召回的条数上限。
        """
        # 初始化系统提示词与用户提示词
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

        # 优先使用外部传入的 llm；未传入时根据 .env 创建默认 ChatOpenAI 实例
        self.llm = llm if llm is not None else self._create_default_llm()
        self.tools = tools
        self.vector_collections = vector_collections if vector_collections else []
        self.memory_rounds = memory_rounds
        self.role_id = role_id
        self.memory_user_id = memory_user_id
        self.memory_top_k = memory_top_k
        self._memory_save_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"{self.role_id}_memory_save",
        )

        # 实例化时直接编译图，后续对话复用同一个编译结果
        self.graph = self.build_react_graph()

    def _on_memory_saved(self, future: Future[dict[str, Any]]) -> None:
        """异步记忆写入完成后输出结果。"""
        error = future.exception()
        if error is not None:
            print(f"\n[Mem0] 长期记忆写入失败: {error}", flush=True)
            return
        add_result = future.result()
        print(f"\n[Mem0] 本轮新增长期记忆 {len(add_result['results'])} 条", flush=True)

    def _save_memory_async(self, user_message: str, assistant_message: str) -> None:
        """异步写入本轮对话，不阻塞主对话流程。"""
        future = self._memory_save_executor.submit(
            save_long_term_memory,
            role_id=self.role_id,
            user_id=self.memory_user_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )
        future.add_done_callback(self._on_memory_saved)

    def compress_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """当轮数超过阈值时，把旧对话压缩为摘要并写回历史。"""
        round_count = sum(1 for msg in history if msg["role"] == "user")
        if round_count <= self.memory_rounds:
            return history

        keep_count = self.memory_rounds * 2
        recent_messages = history[-keep_count:]
        old_messages = history[:-keep_count]

        # 将被压缩的历史格式化后交给模型总结，形成可继续复用的长期记忆。
        old_dialogue_text = "\n".join(
            f"{'用户' if msg['role'] == 'user' else '助手' if msg['role'] == 'assistant' else '系统'}：{msg['content']}"
            for msg in old_messages
        )
        summary_prompt = (
            "请把下面的历史对话压缩成简洁记忆，保留事实、偏好、约束、已完成事项和待办线索，"
            "避免寒暄与重复。输出中文摘要：\n\n"
            f"{old_dialogue_text}"
        )
        summary_result = self.llm.invoke([{"role": "user", "content": summary_prompt}])
        summary_text = str(summary_result.content)

        compressed_history = [
            {"role": "user", "content": f"以下是较早对话的记忆摘要：\n{summary_text}"}
        ]
        compressed_history.extend(recent_messages)
        return compressed_history

    @classmethod
    def _create_default_llm(cls) -> Any:
        """按 .env 配置创建默认 ChatOpenAI。"""

        # 从 .env 读取模型配置，默认等价于 ChatOpenAI(model, api_key, base_url)
        return ChatOpenAI(
            model=os.getenv("model"),
            api_key=os.getenv("api_key"),
            base_url=os.getenv("base_url"),
            temperature=0.6,          # 降低随机性，减少“脑补”  
        )

    def build_react_graph(self) -> Any:
        """构建 ReAct 图：支持多轮对话与按需工具调用。"""
        model = self.llm

        @tool
        def get_current_time() -> str:
            """当用户询问当前时间、日期时使用。"""
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        tools = self.tools if self.tools else [get_current_time]
        llm_with_tools = model.bind_tools(tools)
        tool_node = ToolNode(tools)

        def extract_user_query(state: RoleState) -> str:
            """
            从最新用户消息中提取原始问题文本。

            这里统一复用 <user_data> 标签解析逻辑，避免 RAG 与长期记忆节点重复实现。

            Args:
                state: LangGraph 运行时状态。
            """
            latest_user_message = next(
                msg.content for msg in reversed(state["messages"]) if msg.type == "human"
            )
            return re.search(r"<user_data>(.*?)</user_data>", latest_user_message, flags=re.S).group(1).strip()

        # 长期记忆检索节点：
        # 在进入 agent 前，先按角色与用户维度从 mem0 召回长期记忆，写入 state["memory_context"]。
        def retrieve_memory_context(state: RoleState) -> Dict[str, str]:
            """
            召回 mem0 长期记忆并格式化为可注入模型的上下文文本。

            Args:
                state: LangGraph 运行时状态。
            """
            user_query = extract_user_query(state)
            memory_hits = retrieve_long_term_memory(
                role_id=self.role_id,
                user_id=self.memory_user_id,
                query=user_query,
                top_k=self.memory_top_k,
            )
            print(f"[Mem0] 长期记忆召回 {len(memory_hits)} 条", flush=True)
            return {"memory_context": format_long_term_memories(memory_hits)}

        # 检索节点：在进入 agent 前读取最新用户问题，执行混合检索，并把结果写入 state["context"]。
        def retrieve_context(state: RoleState) -> Dict[str, str]:
            """
            从最新用户输入中抽取查询并生成检索上下文。

            Args:
                state: LangGraph 运行时状态，包含消息历史与上下文字段。
            """
            if len(self.vector_collections) == 0:
                return {"context": ""}

            user_query = extract_user_query(state)
            retrieved_context = hybird_search(
                query=user_query,
                collection_names=self.vector_collections,
            )
            print(f"[RAG] 命中 {len(retrieved_context)} 条", flush=True)
            context_text = "\n\n".join(
                (
                    f"[检索片段{item['rank']}] "
                    f"{item['source_collection']} | {item['source_file']} | {item['heading_path']}\n"
                    f"{item['content']}"
                )
                for item in retrieved_context
            )
            return {"context": context_text}

        # 智能体节点：始终携带系统提示词，并让模型自行决定是否调用工具。
        # 检索数据直接从 state["context"] 读取并注入模型消息。
        def call_agent(state: RoleState) -> Dict[str, List[Any]]:
            """
            调用绑定工具的模型生成当前轮回复。

            Args:
                state: LangGraph 运行时状态，包含消息历史与检索上下文。
            """
            model_messages: list[Any] = [SystemMessage(content=self.system_prompt)]
            if len(state["memory_context"]) > 0:
                model_messages.append(
                    {
                        "role": "user",
                        "content": f"以下是该用户在当前角色下的长期记忆，请用于个性化回答：\n{state['memory_context']}",
                    }
                )
            if len(state["context"]) > 0:
                model_messages.append({"role": "user", "content": state["context"]})
            model_messages.extend(state["messages"])
            response = llm_with_tools.invoke(model_messages)
            return {"messages": [response]}

        graph_builder = StateGraph(RoleState)
        graph_builder.add_node("memory_retrieve", retrieve_memory_context)
        graph_builder.add_node("retrieve", retrieve_context)
        graph_builder.add_node("agent", call_agent)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_edge(START, "memory_retrieve")
        graph_builder.add_edge("memory_retrieve", "retrieve")
        graph_builder.add_edge("retrieve", "agent")
        graph_builder.add_conditional_edges(
            "agent",
            tools_condition,
            {"tools": "tools", "__end__": END},
        )
        graph_builder.add_edge("tools", "agent")

        return graph_builder.compile()
 
    def chat(
        self,
        user_message: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """
        执行一轮对话并返回可继续复用的历史记录。

        Args:
            user_message: 本轮用户输入；为空时回退到初始化时的 user_prompt。
            history: 已有对话历史，格式为 role/content 的字典列表。
        """
        messages = list(history) if history else []
        current_user_message = user_message if user_message is not None else self.user_prompt

        # 仅将本轮用户输入包裹在 <user_data> 中传给模型，history 保持原样传递
        wrapped_user_message = f"<user_data>{current_user_message}</user_data>"
        messages.append({"role": "user", "content": wrapped_user_message})

        result = self.graph.invoke({"messages": messages})

        # 返回给业务层的历史使用原始用户输入，不暴露 <user_data> 标签
        assistant_message = next(msg.content for msg in reversed(result["messages"]) if msg.type == "ai")
        conversation_history = list(history) if history else []
        conversation_history.append({"role": "user", "content": current_user_message})
        conversation_history.append({"role": "assistant", "content": str(assistant_message)})

        # 把本轮对话异步写入 mem0 长期记忆，避免阻塞主对话线程。
        self._save_memory_async(
            user_message=current_user_message,
            assistant_message=str(assistant_message),
        )

        return self.compress_history(conversation_history)

    def multi_round_chat(self) -> None:
        """命令行多轮对话：循环调用 chat，历史由压缩记忆机制自动维护。"""
        history: List[Dict[str, str]] = []
        while True:
            user_message = input("你: ")
            if user_message == "exit":
                print("对话已结束。")
                break

            history = self.chat(user_message=user_message, history=history)

            assistant_message = next(msg["content"] for msg in reversed(history) if msg["role"] == "assistant")
            print(f"助手: {assistant_message}")
