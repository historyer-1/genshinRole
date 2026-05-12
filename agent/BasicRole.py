from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import os
import re
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from search.hybird_search import hybird_search


class RoleState(MessagesState):
    """扩展状态：除 messages 外，额外携带检索得到的 context 文本。"""

    context: str



class BasicRole:
    """基础角色类：管理提示词、模型配置，并提供 LangGraph 多轮对话模板。"""

    def __init__(
        self,
        system_prompt: str,
        user_prompt: str,
        llm: Any | None = None,
        tools:  list[BaseTool] | None = None,
        vector_collections: list[str] | None = None,
    ) -> None:
        # 初始化系统提示词与用户提示词
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

        # 优先使用外部传入的 llm；未传入时根据 .env 创建默认 ChatOpenAI 实例
        self.llm = llm if llm is not None else self._create_default_llm()
        self.tools = tools
        self.vector_collections = vector_collections if vector_collections else []

        # 实例化时直接编译图，后续对话复用同一个编译结果
        self.graph = self.build_react_graph()

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

        # 检索节点：在进入 agent 前读取最新用户问题，执行混合检索，并把结果写入 state["context"]。
        def retrieve_context(state: RoleState) -> Dict[str, str]:
            if len(self.vector_collections) == 0:
                return {"context": ""}

            latest_user_message = next(
                msg.content for msg in reversed(state["messages"]) if msg.type == "human"
            )
            user_query = re.search(r"<user_data>(.*?)</user_data>", latest_user_message, flags=re.S).group(1).strip()
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
            model_messages: list[Any] = [SystemMessage(content=self.system_prompt)]
            if len(state["context"]) > 0:
                model_messages.append({"role": "user", "content": state["context"]})
            model_messages.extend(state["messages"])
            response = llm_with_tools.invoke(model_messages)
            return {"messages": [response]}

        graph_builder = StateGraph(RoleState)
        graph_builder.add_node("retrieve", retrieve_context)
        graph_builder.add_node("agent", call_agent)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_edge(START, "retrieve")
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
        """执行一轮对话并返回可继续复用的历史记录。"""
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
        return conversation_history

    def multi_round_chat(self) -> None:
        """命令行多轮对话：循环调用 chat，并只保留最近 5 轮记忆。"""
        history: List[Dict[str, str]] = []
        while True:
            user_message = input("你: ")
            if user_message == "exit":
                print("对话已结束。")
                break

            history = self.chat(user_message=user_message, history=history)

            assistant_message = next(msg["content"] for msg in reversed(history) if msg["role"] == "assistant")
            print(f"助手: {assistant_message}")

            # 仅保留最近 5 轮（每轮 2 条：用户 + 助手）
            history = history[-10:]

        # TODO: 后续添加对话历史持久化与长期记忆能力。

