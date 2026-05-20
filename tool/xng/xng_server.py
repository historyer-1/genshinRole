from pathlib import Path
import os

from dotenv import load_dotenv
from fastmcp import FastMCP
import requests


# 加载项目根目录 .env，用于读取联网搜索地址
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=False)

mcp = FastMCP("searxng")


@mcp.tool()
def search(query: str) -> str:
    """
    当本地知识或普通工具信息不足时，使用联网搜索补充信息。

    Args:
        query: 需要搜索的关键词或问题。
    """
    print(f"[联网搜索] {query}", flush=True)
    # 从 .env 读取 searxng_url，缺少协议时默认补上 http://
    base_url = str(os.getenv("searxng_url", "")).strip()
    if len(base_url) == 0:
        raise ValueError("searxng_url 未配置，请在 .env 中设置如 http://127.0.0.1:8887")
    if not (base_url.startswith("http://") or base_url.startswith("https://")):
        base_url = f"http://{base_url}"
    response = requests.get(
        f"{base_url.rstrip('/')}/search",
        params={"q": query, "format": "json"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    # 拼接标题、链接与摘要，便于模型引用与复述
    result_list = []
    for item in data["results"]:
        title = str(item["title"])
        url = str(item["url"])
        content = str(item["content"])
        result_list.append(f"{title}\n{url}\n{content}")
    return "\n\n".join(result_list)


if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=9000)