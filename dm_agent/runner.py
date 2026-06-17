"""Agent 运行器 —— 封装 MCP 初始化、LLM 客户端创建、Agent 执行与清理的完整生命周期。

将 simplified_main.py 中的核心逻辑抽取到此模块，去掉命令行交互相关代码，
只保留编程式调用接口。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from . import (
    LLMError,
    ReactAgent,
    Tool,
    create_llm_client,
    default_tools,
)
from .mcp import MCPManager, load_mcp_config
from .mcp.static_playwright_tools import PLAYWRIGHT_STATIC_TOOLS
from .recorders import PlaywrightRecorder

logger = logging.getLogger(__name__)


# ============================================================
# 配置
# ============================================================

@dataclass
class AgentConfig:
    """Agent 运行时配置（全部可通过 env / 代码设置，不需要命令行参数）。"""

    # LLM
    provider: str = "qwen"
    api_key: str = ""
    model: str = "qwen3.6-flash"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Agent 行为
    max_steps: int = 100
    temperature: float = 0.7

    # ABC 专属
    abc_request_id: str = "12"

    # MCP
    mcp_config_path: str = "mcp_config.json"

    # 输出
    output_dir: str = "recorded_scripts"


# ============================================================
# 步骤回调
# ============================================================

def _create_step_callback(recorder: PlaywrightRecorder, verbose: bool = False) -> Callable:
    """创建步骤回调函数。

    每个步骤到来时：
    1. 记录 Playwright 操作 到 recorder
    2. 打印简要进度
    """
    def callback(step_num: int, step: Any) -> None:
        action = getattr(step, "action", "")
        observation = getattr(step, "observation", "")
        action_input = getattr(step, "action_input", {})

        # ---- Playwright 记录 ----
        if PlaywrightRecorder.is_playwright_action(action):
            if PlaywrightRecorder.is_snapshot_tool(action):
                recorder.update_snapshot_count()
            else:
                recorder.record_step(
                    action=action,
                    args=action_input or {},
                    raw_response=observation,
                )

        # ---- 进度输出 ----
        if verbose:
            import json
            print(f"\n[步骤 {step_num}]")
            print(f"  思考：{step.thought}")
            print(f"  动作：{step.action}")
            if step.action_input:
                print(f"  输入：{json.dumps(step.action_input, ensure_ascii=False)}")
            print(f"  观察：{step.observation}")
        else:
            status = "✓" if step.action in ("finish", "task_complete") else ("✗" if step.action == "error" else "✓")
            print(f"[步骤 {step_num}] {step.step_abbreviation} ({step.action}) {status}", flush=True)

    return callback


# ============================================================
# 运行器
# ============================================================

class AgentRunner:
    """封装 Agent 的完整运行生命周期。

    使用方式::

        config = AgentConfig(provider="abc", base_url="http://...")
        runner = AgentRunner(config)
        result = runner.run("你的任务描述")
        print(result["final_answer"])
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._mcp_manager: Optional[MCPManager] = None
        self._recorder: Optional[PlaywrightRecorder] = None

    def run(self, task: str, *, verbose: bool = False) -> Dict[str, Any]:
        """执行一个任务，返回 result 字典。

        Args:
            task: 自然语言任务描述。
            verbose: 是否打印详细的每一步思考/动作/观察。

        Returns:
            dict 包含 ``final_answer``、``steps`` 等字段。

        Raises:
            LLMError: LLM API 调用失败。
            RuntimeError: MCP 初始化失败或其它运行期错误。
        """
        # ---- MCP ----
        mcp_config = load_mcp_config(self.config.mcp_config_path)
        self._mcp_manager = MCPManager(mcp_config)

        # ---- Recorder ----
        self._recorder = PlaywrightRecorder(output_dir=self.config.output_dir)

        try:
            # 启动 MCP 服务器
            use_static = mcp_config.use_static_tools
            started_count = self._mcp_manager.start_all(fetch_tools=not use_static)

            if started_count > 0:
                logger.info("启动了 %d 个 MCP 服务器", started_count)

                if use_static:
                    static_count = self._mcp_manager.load_static_tools(
                        "playwright", PLAYWRIGHT_STATIC_TOOLS
                    )
                    logger.info("从静态定义加载了 %d 个工具", static_count)

            # 获取工具
            mcp_tools = self._mcp_manager.get_tools()
            tools = default_tools(include_mcp=True, mcp_tools=mcp_tools)

            # 创建 LLM 客户端
            client_kwargs: Dict[str, Any] = {}
            if self.config.provider == "abc":
                client_kwargs["request_id"] = self.config.abc_request_id

            client = create_llm_client(
                provider=self.config.provider,
                api_key=self.config.api_key,
                model=self.config.model,
                base_url=self.config.base_url,
                **client_kwargs,
            )

            # 步骤回调
            step_callback = _create_step_callback(self._recorder, verbose=verbose)

            # 创建 Agent
            agent = ReactAgent(
                client,
                tools,
                max_steps=self.config.max_steps,
                temperature=self.config.temperature,
                step_callback=step_callback,
                enable_planning=False,
                enable_compression=True,
            )

            print(f"\n执行任务：{task}\n")

            result = agent.run(task)

            # 生成可回放脚本
            if len(self._recorder.steps) > 0:
                script_path = self._recorder.generate_replayable_script(task[:50])
                print(f"\n可回放脚本：{script_path}")

            # 打印最终答案
            print(f"\n最终答案：\n")
            print(result.get("final_answer", ""))
            print()

            return result

        except LLMError:
            raise
        except Exception:
            raise
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """清理资源（MCP 服务器等）。"""
        if self._mcp_manager:
            try:
                self._mcp_manager.stop_all()
            except Exception as e:
                logger.warning("MCP 清理异常: %s", e)
            self._mcp_manager = None
