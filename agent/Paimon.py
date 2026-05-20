from agent.BasicRole import BasicRole
from dotenv import load_dotenv
from pathlib import Path
import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
import yaml
from tool.xng.langgraph_search_tool import get_xng_tools

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

    # 仅处理本地 fastmcp，避免误拉远端服务
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

    # 等待服务就绪，确保联网搜索工具可用
    deadline = time.time() + 8
    while time.time() < deadline:
        if is_open(host, port):
            break
        time.sleep(0.2)

# 从 YAML 读取派蒙系统提示词（包含人设、风格与安全约束）
prompt_path = Path(__file__).with_name("PaimonPrompt.yaml")
with prompt_path.open("r", encoding="utf-8") as f:
    prompt_config = yaml.safe_load(f)
system_prompt = prompt_config["system_prompt"]

# 派蒙角色的开场用户提示词：作为首次对话的默认输入
user_prompt = "你好派蒙，我们开始聊天吧。"
role_data_dir = Path(__file__).resolve().parent.parent / "data" / "role" / "role_json"
mcp_url = get_url()
up_mcp(mcp_url)
role_tools = get_xng_tools(mcp_url=mcp_url)

Paimon = BasicRole(
    system_prompt=system_prompt,
    user_prompt=user_prompt,
    role="派蒙",
    tools=role_tools,
    vector_collections=["genshin_world_bg","genshin_story"],
    user_id="paimon_default_user",
)


Paimon.multi_round_chat()
