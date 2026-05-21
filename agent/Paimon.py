from agent.BasicRole import BasicRole
from dotenv import load_dotenv
from pathlib import Path
import os
from urllib.parse import urlparse
import yaml
from tool.xng.langgraph_search_tool import get_xng_tools
from tool.role.role_tool import (
    role_attr,
    role_base,
    role_break,
    role_con,
    role_info,
    role_skill,
    role_talent,
)

# 加载 .env，让 BasicRole 默认模型配置可直接生效
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


def start_paimon(mcp_url: str = "") -> None:
    """
    启动派蒙并进入多轮对话。

    Args:
        mcp_url: xng MCP 的 SSE 地址；为空时读取 .env。
    """
    # 从 YAML 读取派蒙系统提示词
    prompt_path = Path(__file__).with_name("PaimonPrompt.yaml")
    with prompt_path.open("r", encoding="utf-8") as f:
        prompt_config = yaml.safe_load(f)
    system_prompt = prompt_config["system_prompt"]

    # 派蒙角色的开场用户提示词
    user_prompt = "你好派蒙，我们开始聊天吧。"
    url = mcp_url if len(mcp_url) > 0 else get_url()

    # 组装工具列表
    role_tools = get_xng_tools(mcp_url=url)
    role_tools.extend(
        [
            role_base,
            role_attr,
            role_break,
            role_info,
            role_con,
            role_skill,
            role_talent,
        ]
    )

    # 构建派蒙智能体并开始聊天
    agent = BasicRole(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        role="派蒙",
        tools=role_tools,
        vector_collections=["genshin_world_bg", "genshin_story"],
        user_id="paimon_default_user",
    )
    agent.multi_round_chat()
