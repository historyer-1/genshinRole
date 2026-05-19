import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

from dotenv import load_dotenv
import yaml

from agent.BasicRole import BasicRole
from tool.xng.langgraph_search_tool import get_xng_tools

# 加载 .env，让模型与 MCP 配置直接可用
load_dotenv()


def parse_args() -> argparse.Namespace:
    """
    解析启动参数。

    Args:
        无。
    """
    parser = argparse.ArgumentParser(description="启动任意角色智能体")
    parser.add_argument("role", help="角色名（对应 data/role/role_json 下的文件名，不含 .json）")
    return parser.parse_args()


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


def is_open(host: str, port: int) -> bool:
    """
    检查目标端口是否可连接。

    Args:
        host: 目标主机地址。
        port: 目标端口号。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.8)
        return sock.connect_ex((host, port)) == 0


def up_mcp(url: str) -> None:
    """
    在本地地址未监听时自动拉起 xng MCP 服务。

    Args:
        url: xng MCP 的 SSE 地址。
    """
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if host not in {"127.0.0.1", "localhost", "::1"}:
        return
    if is_open(host, port):
        return

    root = Path(__file__).resolve().parents[2]
    subprocess.Popen(
        [sys.executable, "-m", "tool.xng.xng_server"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 8
    while time.time() < deadline:
        if is_open(host, port):
            break
        time.sleep(0.2)


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


def main() -> None:
    """
    启动角色智能体并进入命令行多轮对话。

    Args:
        无。
    """
    args = parse_args()
    role_data = read_role(args.role)
    system_prompt = build_prompt(role_data)

    mcp_url = get_url()
    up_mcp(mcp_url)
    role_tools = get_xng_tools(mcp_url=mcp_url)

    role_agent = BasicRole(
        system_prompt=system_prompt,
        user_prompt=f"你好{role_data['role']}，我们开始聊天吧。",
        role=role_data["role"],
        tools=role_tools,
        vector_collections=["genshin_world_bg", "genshin_story"],
        user_id=f"{args.role}_default_user",
    )
    role_agent.multi_round_chat()


if __name__ == "__main__":
    main()