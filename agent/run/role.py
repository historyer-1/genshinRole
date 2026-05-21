import json
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import yaml

from agent.BasicRole import BasicRole
from tool.xng.langgraph_search_tool import get_xng_tools

# 加载 .env，让模型与 MCP 配置直接可用
load_dotenv()


def get_url() -> str:
    """
    读取并标准化 xng MCP 地址。

    Args:
        无。
    """
    raw = os.getenv("xng_mcp_url", "http://127.0.0.1:9000/sse").strip()
    url = raw if raw.startswith("http://") or raw.startswith("https://") else f"http://{raw}"
    if urlparse(url).path in {"", "/"}:
        return f"{url.rstrip('/')}/sse"
    return url


def fmt_data(data: dict) -> str:
    """
    将结构化字典转为可读 YAML 文本。

    Args:
        data: 角色条目里的结构化 data 字段。
    """
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()


def read_role(role: str) -> dict[str, str]:
    """
    读取角色名、角色信息、角色故事的结构化 data。

    Args:
        role: 角色文件名（不含 .json）。
    """
    role_path = Path(__file__).resolve().parents[2] / "data" / "role" / "role_json" / f"{role}.json"
    with role_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    role_name = role
    role_base_data: dict = {}
    role_info_data: dict = {}
    role_story_data: dict = {}
    for block in raw["blocks"]:
        if block["type"] != "template":
            continue
        if block["name"] == "角色":
            role_name = block["data"]["名称"]
            role_base_data = block["data"]
        elif block["name"] == "角色/信息":
            role_info_data = block["data"]
        elif block["name"] == "角色/故事":
            role_story_data = block["data"]

    return {
        "role": role_name,
        "role_base": fmt_data(role_base_data),
        "role_info": fmt_data(role_info_data),
        "role_story": fmt_data(role_story_data),
    }


def build_prompt(role_data: dict[str, str]) -> str:
    """
    将角色结构化数据注入通用系统提示词模板。

    Args:
        role_data: 包含角色名、角色信息、角色故事文本的字典。
    """
    prompt_path = Path(__file__).with_name("agent_prompt.yaml")
    with prompt_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["system_prompt"].format(**role_data)


def start_role(role: str, mcp_url: str = "") -> None:
    """
    启动指定角色智能体并进入多轮对话。

    Args:
        role: 角色文件名（不含 .json）。
        mcp_url: xng MCP 的 SSE 地址；为空时读取 .env。
    """
    # 读取角色数据并生成系统提示词
    role_data = read_role(role)
    system_prompt = build_prompt(role_data)
    url = mcp_url if len(mcp_url) > 0 else get_url()

    # 组装工具并启动智能体
    role_tools = get_xng_tools(mcp_url=url)
    role_agent = BasicRole(
        system_prompt=system_prompt,
        user_prompt=f"你好{role_data['role']}，我们开始聊天吧。",
        role=role_data["role"],
        tools=role_tools,
        vector_collections=["genshin_world_bg", "genshin_story"],
        user_id=f"{role}_default_user",
        stream_output=True,
    )
    role_agent.multi_round_chat()