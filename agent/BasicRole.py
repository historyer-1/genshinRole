from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import os
from pydantic import SecretStr
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition


class BasicRole:
    """基础角色类：管理提示词、模型配置，并提供 LangGraph 多轮对话模板。"""

    def __init__(
        self,
        system_prompt: str,
        user_prompt: str,
        llm: Any | None = None,
        tools:  list[BaseTool] | None = None,
    ) -> None:
        # 初始化系统提示词与用户提示词（创建实例时必须传入）
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

        # 优先使用外部传入的 llm；未传入时根据 .env 创建默认 ChatOpenAI 实例
        self.llm = llm if llm is not None else self._create_default_llm()
        self.tools = tools

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

        # 智能体节点：始终携带系统提示词，并让模型自行决定是否调用工具
        def call_agent(state: MessagesState) -> Dict[str, List[Any]]:
            response = llm_with_tools.invoke([SystemMessage(content=self.system_prompt), *state["messages"]])
            return {"messages": [response]}

        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("agent", call_agent)
        graph_builder.add_node("tools", tool_node)

        graph_builder.add_edge(START, "agent")
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
        if user_message is None:
            user_message = self.user_prompt
        messages.append({"role": "user", "content": user_message})

        result = self.graph.invoke({"messages": messages})

        # 将图状态中的消息转换为可传入下一轮的简洁历史，仅保留用户与助手消息
        conversation_history: List[Dict[str, str]] = []
        for msg in result["messages"]:
            if msg.type == "human":
                conversation_history.append({"role": "user", "content": str(msg.content)})
            elif msg.type == "ai":
                conversation_history.append({"role": "assistant", "content": str(msg.content)})
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

