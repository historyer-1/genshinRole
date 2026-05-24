import multiprocessing
from tool.xng import xng_server


def run_mcp(host: str, port: int) -> None:
    """
    启动 xng FastMCP 服务。

    Args:
        host: FastMCP 监听地址。
        port: FastMCP 监听端口。
    """
    # 启动 fastmcp 服务
    xng_server.mcp.run(transport="sse", host=host, port=port)


def start_mcp(host: str = "127.0.0.1", port: int = 9000) -> multiprocessing.Process:
    """
    在独立进程启动 xng FastMCP 服务。

    Args:
        host: FastMCP 监听地址。
        port: FastMCP 监听端口。
    """
    # 独立进程启动 fastmcp，避免服务线程阻塞进程退出
    ctx = multiprocessing.get_context("spawn")
    process = ctx.Process(target=run_mcp, args=(host, port), daemon=True)
    process.start()
    return process


def stop_mcp(process: multiprocessing.Process | None) -> None:
    """停止 MCP 子进程，避免退出后仍有后台服务存活。"""
    if process is None:
        return
    if process.is_alive():
        process.terminate()
        process.join(timeout=3)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(timeout=3)



def main() -> None:
    """
    统一启动入口。

    Args:
        无。
    """
    # 先启动 fastmcp 服务
    mcp_process = start_mcp()
    try:
        from agent.Paimon import start_paimon
        from agent.run.role import start_role

        choice = input("选择 1=派蒙，2=角色：").strip()
        if choice == "1":
            start_paimon()
        else:
            role_name = input("输入角色名：").strip()
            start_role(role_name)
    finally:
        stop_mcp(mcp_process)
    return


if __name__ == "__main__":
    main()