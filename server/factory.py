import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from config import RAG_COLLECTIONS
from agent.BasicRole import BasicRole
from tool.role.role_tool import (
    role_attr,
    role_base,
    role_break,
    role_con,
    role_info,
    role_skill,
    role_talent,
)
from tool.xng.langgraph_search_tool import create_xng_tools_async

load_dotenv()

# 角色数据根目录
ROLE_JSON_DIR = Path(__file__).resolve().parents[1] / "data" / "role" / "role_json"
# 通用角色提示词模板
AGENT_PROMPT_PATH = Path(__file__).resolve().parents[1] / "agent" / "run" / "agent_prompt.yaml"
# 派蒙提示词
PAIMON_PROMPT_PATH = Path(__file__).resolve().parents[1] / "agent" / "PaimonPrompt.yaml"


def load_paimon_prompt() -> str:
    """加载派蒙系统提示词。"""
    with PAIMON_PROMPT_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)["system_prompt"]


def _fmt_data(data: dict) -> str:
    """将结构化字典转为可读 YAML 文本。"""
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()


def read_role_data(role_name: str) -> dict[str, str]:
    """
    读取角色全部结构化数据。
    "角色" 模板块的 data 字段会完整加载（名称、称号、稀有度、元素属性、介绍等）。

    Args:
        role_name: 角色文件名（不含 .json）。
    """
    role_path = ROLE_JSON_DIR / f"{role_name}.json"
    with role_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    display_name = role_name
    role_base_data: dict = {}
    role_info_data: dict = {}
    role_story_data: dict = {}
    for block in raw["blocks"]:
        if block["type"] != "template":
            continue
        if block["name"] == "角色":
            role_base_data = block["data"]
            display_name = role_base_data.get("名称", role_name)
        elif block["name"] == "角色/信息":
            role_info_data = block["data"]
        elif block["name"] == "角色/故事":
            role_story_data = block["data"]

    return {
        "role": display_name,
        "role_base": _fmt_data(role_base_data),
        "role_info": _fmt_data(role_info_data),
        "role_story": _fmt_data(role_story_data),
    }


def load_role_prompt(role_name: str) -> tuple[str, str]:
    """
    读取角色数据并生成系统提示词。

    Args:
        role_name: 角色文件名（不含 .json）。

    Returns:
        (system_prompt, display_name) 元组。
    """
    role_data = read_role_data(role_name)
    with AGENT_PROMPT_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    system_prompt = cfg["system_prompt"].format(**role_data)
    return system_prompt, role_data["role"]


def list_roles() -> list[str]:
    """扫描 role_json 目录，返回所有可用角色文件名列表。"""
    return [p.stem for p in ROLE_JSON_DIR.glob("*.json")]


async def create_agent(role_name: str, user_id: str) -> BasicRole:
    """
    根据角色名和用户 ID 创建 BasicRole 实例。
    每个 agent 持有独立的 MCP 客户端连接，确保连接生命周期与会话一致。

    Args:
        role_name: 角色名，"派蒙" 表示派蒙。
        user_id: 用户唯一标识。
    """
    mcp_client, tools = await create_xng_tools_async()

    if role_name == "派蒙":
        system_prompt = load_paimon_prompt()
        display_name = "派蒙"
        # 派蒙可以调用角色数据工具查询其他角色信息
        tools.extend([
            role_base, role_attr, role_break, role_info, role_con, role_skill, role_talent,
        ])
    else:
        system_prompt, display_name = load_role_prompt(role_name)

    # 内部用角色名 + user_id 组合键，确保同一用户不同角色的记忆和历史隔离
    storage_uid = f"{display_name}_{user_id}"
    agent = BasicRole(
        system_prompt=system_prompt,
        user_prompt=f"你好{display_name}，我们开始聊天吧。",
        role=display_name,
        tools=tools,
        vector_collections=RAG_COLLECTIONS,
        user_id=storage_uid,
        stream_output=False,
    )
    # 保持 MCP 客户端引用，防止 SSE 连接被回收
    agent._mcp_client = mcp_client
    return agent
