"""导出 MCP 工具列表到 JSON 文件

启动 Playwright MCP 服务器，获取所有可用工具的名称、描述和参数信息，
保存为结构化的 JSON 文件，方便审查和筛选常用的工具。
"""

import json
import os
import subprocess
import sys
import time
from queue import Queue, Empty
from threading import Lock, Thread
from typing import Optional

# 修复 Windows GBK 编码问题
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def fetch_mcp_tools(server_name: str, command: str, args: list) -> list:
    """启动 MCP 服务器并获取工具列表"""
    full_command = [command] + args

    # 准备环境变量
    process_env = os.environ.copy()
    is_windows = sys.platform == "win32"

    # 启动子进程
    print(f"🚀 启动 MCP 服务器 '{server_name}'...")
    print(f"   命令: {' '.join(full_command)}")

    if is_windows:
        quoted_args = []
        for arg in full_command:
            if " " in arg:
                quoted_args.append(f'"{arg}"')
            else:
                quoted_args.append(arg)
        cmd_str = " ".join(quoted_args)
        process = subprocess.Popen(
            cmd_str,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=process_env,
            shell=True,
        )
    else:
        process = subprocess.Popen(
            full_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=process_env,
        )

    # 用于线程间通信
    stdout_queue: Queue = Queue()
    lock = Lock()
    message_id = 0

    def read_stdout():
        while process.poll() is None:
            try:
                line = process.stdout.readline()
                if line:
                    stdout_queue.put(line.strip())
            except Exception:
                break

    reader_thread = Thread(target=read_stdout, daemon=True)
    reader_thread.start()

    def send_message(method: str, params: Optional[dict] = None) -> Optional[dict]:
        nonlocal message_id
        with lock:
            message_id += 1
            msg = {"jsonrpc": "2.0", "id": message_id, "method": method}
            if params:
                msg["params"] = params

            process.stdin.write(json.dumps(msg) + "\n")
            process.stdin.flush()

            # 等待响应（最多 30 秒，因为首次启动可能较慢）
            for _ in range(300):
                try:
                    line = stdout_queue.get(timeout=0.1)
                    resp = json.loads(line)
                    if resp.get("id") == message_id:
                        if "error" in resp:
                            print(f"   ❌ 错误: {resp['error']}")
                            return None
                        return resp.get("result")
                    # 不是我们的响应，放回队列
                    stdout_queue.put(line)
                except Empty:
                    continue
                except json.JSONDecodeError:
                    continue

            print("   ⚠️ 响应超时")
            return None

    try:
        # 等待 MCP 服务器启动
        print("   ⏳ 等待服务器启动...")
        time.sleep(3)

        # Step 1: 初始化
        print("   📡 发送 initialize 请求...")
        init_result = send_message(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dm-code-agent", "version": "1.1.0"},
            },
        )

        if init_result is None:
            print("   ❌ 初始化失败")
            return []

        server_info = init_result.get("serverInfo", {})
        print(f"   ✅ 服务器信息: {server_info.get('name', 'unknown')} v{server_info.get('version', 'unknown')}")

        # Step 2: 获取工具列表
        print("   🔧 获取工具列表...")
        tools_result = send_message("tools/list")

        if tools_result is None:
            print("   ❌ 获取工具列表失败")
            return []

        tools = tools_result.get("tools", [])
        print(f"   ✅ 获取到 {len(tools)} 个工具")

        return tools

    finally:
        # 清理
        print("   🛑 关闭服务器...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        print("   ✅ 服务器已关闭")


def simplify_tool(tool: dict) -> dict:
    """精简工具定义，保留关键信息"""
    input_schema = tool.get("inputSchema", {})

    params = []
    if "properties" in input_schema:
        required = input_schema.get("required", [])
        for name, info in input_schema["properties"].items():
            param = {
                "name": name,
                "type": info.get("type", "any"),
                "required": name in required,
            }
            # 只保留有意义的描述
            desc = info.get("description", "")
            if desc:
                param["description"] = desc
            # 如果是枚举类型，保留可选值
            if "enum" in info:
                param["enum"] = info["enum"]
            params.append(param)

    return {
        "name": tool.get("name", ""),
        "description": tool.get("description", ""),
        "parameters": params,
    }


def compute_tool_stats(tools: list) -> dict:
    """计算工具统计信息"""
    total_params = sum(len(t.get("parameters", [])) for t in tools)
    descriptions_chars = sum(len(t.get("description", "")) for t in tools)

    # 估算每个工具在 prompt 中占用的 tokens（粗略：1 token ≈ 2 字符中文，≈ 4 字符英文）
    token_estimate = 0
    for t in tools:
        desc = t.get("description", "")
        # 中文为主，粗略按 1 token ≈ 1.5 字符
        token_estimate += len(desc) // 2 + 10  # +10 for name and formatting
        for p in t.get("parameters", []):
            token_estimate += len(p.get("description", "")) // 2 + 5

    return {
        "total_tools": len(tools),
        "total_parameters": total_params,
        "total_description_chars": descriptions_chars,
        "estimated_tokens": token_estimate,
    }


def main():
    # 加载配置
    config_path = os.path.join(os.path.dirname(__file__), "mcp_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 只处理启用的服务器
    all_tools = {}
    for name, server_config in config.get("mcpServers", {}).items():
        if not server_config.get("enabled", False):
            print(f"⏭️ 跳过已禁用的服务器: {name}")
            continue

        print(f"\n{'='*60}")
        print(f"📦 处理服务器: {name}")
        print(f"{'='*60}")

        raw_tools = fetch_mcp_tools(
            server_name=name,
            command=server_config["command"],
            args=server_config["args"],
        )

        simplified = [simplify_tool(t) for t in raw_tools]
        stats = compute_tool_stats(simplified)
        all_tools[name] = {
            "server": name,
            "command": f"{server_config['command']} {' '.join(server_config['args'])}",
            "stats": stats,
            "tools": simplified,
        }

        print(f"\n   📊 统计: {stats['total_tools']} 个工具, "
              f"{stats['total_parameters']} 个参数, "
              f"约 {stats['estimated_tokens']} tokens")

    # 保存结果
    output_path = os.path.join(os.path.dirname(__file__), "mcp_tools_export.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_tools, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 工具列表已导出到: {output_path}")
    print(f"{'='*60}")

    # 打印简要的工具清单
    for server_name, server_data in all_tools.items():
        print(f"\n📋 [{server_name}] 工具清单:")
        for i, tool in enumerate(server_data["tools"], 1):
            params_str = ", ".join(p["name"] for p in tool["parameters"])
            print(f"   {i:2d}. {tool['name']}")
            print(f"       参数: {params_str}" if params_str else "       参数: 无")
            print(f"       描述: {tool['description'][:80]}..." if len(tool['description']) > 80 else f"       描述: {tool['description']}")


if __name__ == "__main__":
    main()
