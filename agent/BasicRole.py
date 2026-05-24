from __future__ import annotations

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional
import sys
import os
import re
from langchain_core.messages import SystemMessage, merge_message_runs
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from config import MEMORY_ROUNDS
from memory.mem import LongMem
from memory.operation import count_tokens, save_chat, save_summary
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
        role: str,
        llm: Any | None = None,
        tools: list[BaseTool] | None = None,
        vector_collections: list[str] | None = None,
        memory_rounds: int = MEMORY_ROUNDS,
        stream_output: bool = False,
        user_id: str | None = "default_user",
    ) -> None:
        """
        初始化基础角色实例，并构建可复用的对话图。

        Args:
            system_prompt: 系统角色提示词，定义助手行为边界与风格。
            user_prompt: 默认用户提示词，在未显式传入 user_message 时使用。
            role: 角色名称，用于 RAG 检索增强角色相关性。
            llm: 可选的外部语言模型实例；不传则按 .env 创建默认模型。
            tools: 可选工具列表；不传时默认仅启用时间工具。
            vector_collections: 可选检索集合列表；为空时跳过 RAG 检索。
            memory_rounds: 保留的近期对话轮数，超过后会触发历史压缩。
            stream_output: 是否启用流式输出（仅影响模型回复展示），默认关闭。
            user_id: 当前会话所属用户；传 None 时不启用长期记忆。
        """
        # 初始化系统提示词与用户提示词
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.role = role

        # 优先使用外部传入的 llm；未传入时根据 .env 创建默认 ChatOpenAI 实例
        self.llm = llm if llm is not None else self._create_default_llm()
        self.tools = tools
        self.vector_collections = vector_collections if vector_collections else []
        self.memory_rounds = memory_rounds
        self.stream_output = stream_output
        self.user_id = user_id
        # BasicRole 只依赖长期记忆端口，不依赖 mem0 的具体初始化细节。
        self.long_mem = LongMem(user_id=user_id) if user_id is not None else None

        # MCP 客户端引用（由外部注入），防止 SSE 连接被 GC 回收
        self._mcp_client = None

        # 实例化时直接编译图，后续对话复用同一个编译结果
        self.graph = self.build_react_graph()

    async def compress_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
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
        summary_result = await self.llm.ainvoke([{"role": "user", "content": summary_prompt}])
        summary_text = str(summary_result.content)

        # 压缩完成后更新摘要表
        await save_summary(self.user_id, summary_text)

        compressed_history = [
            {"role": "user", "content": f"以下是较早对话的记忆摘要：\n{summary_text}"}
        ]
        compressed_history.extend(recent_messages)
        return compressed_history

    def close(self) -> None:
        """释放长期记忆资源，避免后台线程阻塞进程退出。"""
        if self.long_mem is not None:
            self.long_mem.close()

    @classmethod
    def _create_default_llm(cls) -> Any:
        """按 .env 配置创建默认 ChatOpenAI。"""

        # 从 .env 读取模型配置，默认等价于 ChatOpenAI(model, api_key, base_url)
        return ChatOpenAI(
            model=os.getenv("model"),
            api_key=os.getenv("api_key"),
            base_url=os.getenv("base_url"),
            temperature=0.6,          # 降低随机性，减少"脑补"
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
            """
            从最新用户输入中抽取查询并生成检索上下文。

            Args:
                state: LangGraph 运行时状态，包含消息历史与上下文字段。
            """
            latest_user_message = next(
                msg.content for msg in reversed(state["messages"]) if msg.type == "human"
            )
            user_query = re.search(r"<user_data>(.*?)</user_data>", latest_user_message, flags=re.S).group(1).strip()

            # 先读用户长期记忆，补齐跨会话背景（偏好、事实、长期目标等）。
            long_context = self.long_mem.find(user_query) if self.long_mem is not None else ""

            # 再做 RAG 检索，补齐业务知识库内容。
            rag_context = ""
            if len(self.vector_collections) > 0:
                rag_query = f"{self.role} {user_query}" if self.role else user_query
                retrieved_context = hybird_search(
                    query=rag_query,
                    collection_names=self.vector_collections,
                )
                # 检索日志走 stderr，避免与回答内容混在一起
                print(f"[RAG] 命中 {len(retrieved_context)} 条", file=sys.stderr, flush=True)
                rag_context = "\n\n".join(
                    (
                        f"[检索片段{item['rank']}] "
                        f"{item['source_collection']} | {item['source_file']} | {item['heading_path']}\n"
                        f"{item['content']}"
                    )
                    for item in retrieved_context
                )

            # 长期记忆与 RAG 统一拼接到同一段 context，供 agent 节点直接注入。
            context_parts = [text for text in [long_context, rag_context] if len(text) > 0]
            context_text = "\n\n".join(context_parts)
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
            model_messages.extend(state["messages"])
            # 检索结果放在历史与当前用户输入之后
            if len(state["context"]) > 0:
                model_messages.append({"role": "user", "content": state["context"]})
            if self.stream_output:
                # 直接消费模型流式输出，并拼成完整消息供图继续处理
                chunks: list[Any] = []
                for chunk in llm_with_tools.stream(model_messages):
                    chunks.append(chunk)
                response = merge_message_runs(chunks, chunk_separator="")[-1]
            else:
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

        # 角色攻略工具直接输出，其余工具继续回到 agent
        direct_tools = {
            "role_base",
            "role_attr",
            "role_info",
            "role_con",
            "role_skill",
            "role_talent",
        }

        def route_tool(state: RoleState) -> str:
            """
            根据工具名决定是否直接结束本轮对话。

            Args:
                state: LangGraph 运行时状态，包含消息历史与检索上下文。
            """
            last_tool = next(msg for msg in reversed(state["messages"]) if msg.type == "tool")
            return "__end__" if last_tool.name in direct_tools else "agent"

        graph_builder.add_conditional_edges(
            "tools",
            route_tool,
            {"agent": "agent", "__end__": END},
        )

        return graph_builder.compile()

    async def chat_stream(
        self,
        user_message: str,
        history: list[Dict[str, str]],
    ) -> AsyncGenerator[Dict[str, str], None]:
        """
        流式执行一轮对话，逐 token 生成事件。

        Args:
            user_message: 本轮用户输入。
            history: 已有对话历史，格式为 role/content 的字典列表。
        """
        # 拷贝历史消息，避免修改调用方传入的原始列表
        messages = list(history) if history else []
        # 用 <user_data> 标签包裹用户输入，方便 retrieve_context 节点用正则提取查询
        wrapped_user_message = f"<user_data>{user_message}</user_data>"
        messages.append({"role": "user", "content": wrapped_user_message})

        # 角色攻略类工具（角色信息、属性、技能等）的返回值就是最终回答，
        # 不需要模型再加工一次，所以单独标记出来做特殊处理。
        direct_tools = {
            "role_base", "role_attr", "role_info",
            "role_con", "role_skill", "role_talent",
        }

        # 用于拼接模型逐 token 流式输出的完整文本
        accumulated_content = ""
        # 如果触发了角色攻略工具，这里会存工具返回的结果
        tool_result = None

        # astream_events 会以事件流的方式驱动整个 LangGraph 图执行，
        # 图的执行路径：retrieve(RAG检索) -> agent(模型推理) -> [tools(工具调用)] -> ...
        async for event in self.graph.astream_events({"messages": messages}, version="v2"):
            # 模型逐 token 输出事件：每收到一小段文本就立刻 yield 给前端，实现打字机效果
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    accumulated_content += chunk.content
                    yield {"type": "token", "content": chunk.content}
            # 工具执行完成事件：如果命中的是角色攻略工具，记录其返回结果
            elif event["event"] == "on_tool_end":
                tool_name = event.get("name", "")
                if tool_name in direct_tools:
                    output = event["data"].get("output")
                    if output is not None:
                        # output 是 ToolMessage 对象，需要提取 .content 获取纯文本/JSON
                        tool_result = str(getattr(output, "content", output))
                    else:
                        tool_result = ""

        # 确定最终回复文本：
        # - 如果角色攻略工具被调用过，直接用工具返回值（结构化数据，比模型复述更准确）
        # - 否则用模型流式输出拼接起来的完整文本
        if tool_result is not None:
            assistant_text = tool_result
        else:
            assistant_text = accumulated_content

        # 向前端发送完成事件，附带最终完整回复
        yield {"type": "done", "content": assistant_text}

        # 持久化本轮对话到数据库，并在后台写入长期记忆
        await save_chat(self.user_id, user_message, assistant_text)
        if self.long_mem is not None:
            self.long_mem.save_async(user_message, assistant_text)

    async def chat(
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
        current_user_message = user_message if user_message is not None else self.user_prompt
        conversation_history = list(history) if history else []
        assistant_text = ""

        async for event in self.chat_stream(current_user_message, conversation_history):
            if event["type"] == "done":
                assistant_text = event["content"]

        conversation_history.append({"role": "user", "content": current_user_message})
        conversation_history.append({"role": "assistant", "content": assistant_text})
        return await self.compress_history(conversation_history)
