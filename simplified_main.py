"""LLM 驱动的 ReAct 智能体的 CLI 入口点。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List

from dotenv import load_dotenv

# 忽略 Pydantic 的字段名冲突警告（来自第三方库）
warnings.filterwarnings("ignore", category=UserWarning)

from dm_agent import (
    LLMError,
    ReactAgent,
    Tool,
    create_llm_client,
    default_tools,
    PROVIDER_DEFAULTS,
)
from dm_agent.mcp import MCPManager, load_mcp_config
from dm_agent.mcp.static_playwright_tools import PLAYWRIGHT_STATIC_TOOLS
from dm_agent.recorders import PlaywrightRecorder
from dm_agent.logger import setup_global_logging

# 尝试导入 colorama 用于彩色输出
try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    # 如果没有 colorama，定义空的颜色常量
    class Fore:
        GREEN = ""
        YELLOW = ""
        RED = ""
        CYAN = ""
        MAGENTA = ""
        BLUE = ""

    class Style:
        BRIGHT = ""
        RESET_ALL = ""


@dataclass
class Config:
    """运行时配置"""
    api_key: str
    provider: str = "qwen"
    model: str = "qwen3.6-flash"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    max_steps: int = 100
    temperature: float = 0.7
    show_steps: bool = True
    abc_request_id: str = "12"  # ABC 自定义 API 的请求头


# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config_from_file() -> Dict[str, Any]:
    """从配置文件加载设置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠ 配置文件加载失败：{e}，使用默认设置{Style.RESET_ALL}")
    return {}


def parse_args(argv: Any) -> argparse.Namespace:

    # 先加载配置文件中的默认值
    saved_config = load_config_from_file()

    # 直接从环境变量获取默认配置
    default_api_key = os.getenv("API_KEY")
    default_provider = os.getenv("PROVIDER", saved_config.get("provider", "qwen"))
    default_model = os.getenv("MODEL_NAME", "gpt-5")
    default_base_url = os.getenv("BASE_URL", "https://api.openai.com/v1")

    parser = argparse.ArgumentParser(description="运行基于 LLM 的 ReAct 智能体来完成任务描述。")
    parser.add_argument("task", nargs="?", help="智能体要完成的自然语言任务。")

    parser.add_argument(
        "--provider",
        default=default_provider,
        help="LLM 提供商: deepseek/openai/claude/gemini/qwen/abc（默认使用 PROVIDER 环境变量或 qwen）",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=default_api_key,
        help="API 密钥（默认使用 API_KEY 环境变量）。",
    )
    parser.add_argument(
        "--model",
        default=default_model,
        help="模型标识符（默认使用 MODEL_NAME 环境变量，或 gpt-5）。",
    )
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default=default_base_url,
        help="API 基础 URL（默认使用 BASE_URL 环境变量，或 https://api.openai.com/v1）。",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=saved_config.get("max_steps", 100),
        help="放弃前的最大推理/工具步骤数（默认：100）。",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=saved_config.get("temperature", 0.7),
        help="模型的采样温度（默认：0.7）。",
    )
    parser.add_argument(
        "--show-steps",
        action="store_true",
        default=saved_config.get("show_steps", False),
        help="打印智能体执行的中间 ReAct 步骤。",
    )

    return parser.parse_args(argv)


def print_separator(char: str = "=", length: int = 70) -> None:
    """打印分隔线"""
    print(f"{Fore.CYAN}{char * length}{Style.RESET_ALL}")


def print_header(text: str) -> None:
    """打印标题"""
    print_separator()
    print(f"{Fore.GREEN}{Style.BRIGHT}{text.center(70)}{Style.RESET_ALL}")
    print_separator()


def display_result(result: Dict[str, Any], show_steps: bool = False) -> None:
    """格式化显示任务结果"""
    print_separator("-")

    if show_steps and result.get("steps"):
        print(f"{Fore.CYAN}{Style.BRIGHT}执行步骤：{Style.RESET_ALL}\n")
        for idx, step in enumerate(result.get("steps", []), start=1):
            print(f"{Fore.MAGENTA}步骤 {idx}:{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}思考：{Style.RESET_ALL}{step.get('thought')}")
            print(f"  {Fore.YELLOW}动作：{Style.RESET_ALL}{step.get('action')}")
            action_input = step.get('action_input')
            if action_input:
                print(f"  {Fore.YELLOW}输入：{Style.RESET_ALL}{json.dumps(action_input, ensure_ascii=False)}")
            print(f"  {Fore.YELLOW}观察：{Style.RESET_ALL}{step.get('observation')}")
            print()

    print(f"{Fore.GREEN}{Style.BRIGHT}最终答案：{Style.RESET_ALL}\n")
    final_answer = result.get("final_answer", "")
    print(final_answer)
    print()
    print_separator("-")


def create_step_callback(show_steps: bool, recorder: PlaywrightRecorder):
    """创建步骤回调函数，用于实时打印 agent 执行状态"""
    def callback(step_num: int, step: Any) -> None:
        # ======== Playwright Recorder 逻辑 ========
        action = getattr(step, 'action', '')
        observation = getattr(step, 'observation', '')
        action_input = getattr(step, 'action_input', {})

        # 检查是否是 playwright 相关操作
        if PlaywrightRecorder.is_playwright_action(action):
            # snapshot 操作只更新计数
            if PlaywrightRecorder.is_snapshot_tool(action):
                recorder.update_snapshot_count()
            # 其他操作记录步骤
            else:
                recorder.record_step(
                    action=action,
                    args=action_input or {},
                    raw_response=observation
                )

        # ======== 显示逻辑 ========
        if show_steps:
            print(f"\n{Fore.MAGENTA}{Style.BRIGHT}[步骤 {step_num}]{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}思考：{Style.RESET_ALL}{step.thought}")
            print(f"  {Fore.YELLOW}动作：{Style.RESET_ALL}{step.action}")
            if step.action_input:
                print(f"  {Fore.YELLOW}输入：{Style.RESET_ALL}{json.dumps(step.action_input, ensure_ascii=False)}")
            print(f"  {Fore.YELLOW}观察：{Style.RESET_ALL}{step.observation}")
        else:
            # 即使不显示详细步骤，也显示简要进度
            print(f"{Fore.CYAN}[步骤 {step_num}] {step.step_abbreviation} ({step.action}){Style.RESET_ALL}", end=" ", flush=True)
            if step.action == "finish" or step.action == "task_complete":
                print(f"{Fore.GREEN}✓{Style.RESET_ALL}")
            elif step.action == "error":
                print(f"{Fore.RED}✗{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN}✓{Style.RESET_ALL}")

    return callback


def run_single_task(config: Config, task: str) -> int:
    """运行单个任务（命令行模式）"""
    # 初始化 MCP
    mcp_config = load_mcp_config()
    mcp_manager = MCPManager(mcp_config)

    # 创建 Playwright 执行记录器
    recorder = PlaywrightRecorder(output_dir="recorded_scripts")

    try:
        # 启动 MCP 服务器
        use_static = mcp_config.use_static_tools
        started_count = mcp_manager.start_all(fetch_tools=not use_static)
        if started_count > 0:
            print(f"{Fore.GREEN}✓ 启动了 {started_count} 个 MCP 服务器{Style.RESET_ALL}")

            if use_static:
                # 从静态定义加载工具（替代 MCP tools/list）
                static_count = mcp_manager.load_static_tools("playwright", PLAYWRIGHT_STATIC_TOOLS)
                print(f"{Fore.GREEN}✓ 从静态定义加载了 {static_count} 个工具{Style.RESET_ALL}")

        # 获取工具
        mcp_tools = mcp_manager.get_tools()
        tools = default_tools(include_mcp=True, mcp_tools=mcp_tools)

        # 创建 LLM 客户端（ABC 提供商需要额外参数）
        client_kwargs = {}
        if config.provider == "abc":
            client_kwargs["request_id"] = config.abc_request_id
        client = create_llm_client(
            provider=config.provider,
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            **client_kwargs,
        )

        # 创建步骤回调函数（传入 recorder）
        step_callback = create_step_callback(config.show_steps, recorder)

        agent = ReactAgent(
            client,
            tools,
            max_steps=config.max_steps,
            temperature=config.temperature,
            step_callback=step_callback,
            enable_planning=False,
            enable_compression=True
        )

        print(f"\n{Fore.CYAN}正在执行任务：{Style.RESET_ALL}{task}\n")
        print_separator()

        result = agent.run(task)

        # 生成可回放脚本
        if len(recorder.steps) > 0:
            script_path = recorder.generate_replayable_script(task[:50])  # 用任务前50字符作为名称
            print(f"\n{Fore.GREEN}✓ 可回放脚本已生成：{script_path}{Style.RESET_ALL}")

        # 显示最终结果
        print(f"\n{Fore.GREEN}{Style.BRIGHT}最终答案：{Style.RESET_ALL}\n")
        print(result.get("final_answer", ""))
        print()
        print_separator()

        return 0

    except LLMError as e:
        print(f"{Fore.RED}{Style.BRIGHT}✗ API 错误：{Style.RESET_ALL}{e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"{Fore.RED}{Style.BRIGHT}✗ 发生错误：{Style.RESET_ALL}{e}", file=sys.stderr)
        return 1
    finally:
        # 清理 MCP 资源
        mcp_manager.stop_all()


def main(task: str, argv: Any = None) -> int:
    """主入口函数"""
    # 初始化日志系统
    setup_global_logging()

    load_dotenv()
    args = parse_args(argv if argv is not None else sys.argv[1:])

    # 如果没有提供 API 密钥，尝试根据提供商获取
    if not args.api_key:
        print(f"{Fore.YELLOW}⚠ 未提供 API 密钥，尝试从环境变量获取。{Style.RESET_ALL}")
        
    # 检查 API 密钥
    if not args.api_key:
        print(f"{Fore.RED}✗ 缺少 API 密钥。{Style.RESET_ALL}", file=sys.stderr)



    # 创建配置
    config = Config(
        api_key=args.api_key or "",
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        max_steps=args.max_steps,
        temperature=args.temperature,
        show_steps=args.show_steps,
    )


    return run_single_task(config, task)


# 1.访问路透社官网：https://www.reuters.com/
# 2.点击上方的“World”，选择“ukraine-russia-war"
# 3.获取最新的一条俄乌新闻并输出新闻标题和链接

# 1.访问中国平安银行官网（https://b.pingan.com.cn/）
# 2.点击服务价格目录
# 3.点击左侧的个人业务下面的投资理财
# 4.点击投资理财下的 理财产品
# 5.公告类型选 产品其它公告
# 6.点击查看最上面的一条公告的内容

if __name__ == "__main__":
    task = """
1.打开网站https://www.abchina.com/cn/；
2.点击页面下方的“基金”链接；
3.在产品筛选区域投资类型选择“股票型”，实践区间为：“近一年”，风险等级选择“R4中高风险”；
4.输出一共查到了多少个满足条件的基金。
    """
    raise SystemExit(main(task))
