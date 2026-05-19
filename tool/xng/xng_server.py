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
    # 从 .env 读取 searxng_url，拼接搜索接口地址
    base_url = os.getenv("searxng_url")
    response = requests.get(
        f"{base_url.rstrip('/')}/search",
        params={"q": query, "format": "json"},
        timeout=15,
    )
    data = response.json()

    # 提取每条结果的 content 并按行拼接返回
    result_list = []
    for item in data["results"]:
        result_list.append(str(item["content"]))
    return "\n".join(result_list)


if __name__ == "__main__":
    mcp.run(transport="sse", host="127.0.0.1", port=9000)