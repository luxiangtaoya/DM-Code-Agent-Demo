"""Playwright 执行记录器 - 记录并生成可回放代码"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PlaywrightStep:
    """单个执行步骤"""

    def __init__(self, action: str, args: Dict[str, Any], raw_response: str = ""):
        self.action = action
        self.args = args
        self.raw_response = raw_response
        self.extracted_code = None  # 存储从 observation 中提取的完整 JS 代码

    def extract_code_from_observation(self, observation: str) -> Optional[str]:
        """从 observation 中提取完整的 JS 代码

        observation 格式示例:
        ### Ran Playwright code
        ```js
        await page.locator('span').filter({ hasText: '全部 股票型' }).click();
        ```

        Returns:
            提取的 JS 代码，如果未找到则返回 None
        """
        if not observation:
            return None

        # 提取 ```js 代码块
        code_match = re.search(r'```js\s*\n(.*?)\n```', observation, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            self.extracted_code = code
            logger.info(f"[PlaywrightStep] 提取 JS 代码成功: {code[:80]}...")
            return code

        # 尝试更宽松的匹配
        code_match = re.search(r'```js\s*\n(.*?)```', observation, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            self.extracted_code = code
            logger.info(f"[PlaywrightStep] 提取 JS 代码成功(宽松模式): {code[:80]}...")
            return code

        return None

    def to_js_code(self) -> str:
        """转换为 Playwright JavaScript 代码"""
        # 如果有从 observation 提取的完整代码，直接使用
        if self.extracted_code:
            code = self.extracted_code.rstrip(';')
            return f'  {code};\n  await page.waitForTimeout(1000);  // 停顿 1 秒'

        # 否则，根据 action 和参数生成代码
        action_name = self._extract_action_name()

        # 导航类动作
        if action_name in ["goto", "navigate", "browser_navigate", "browser_goto"]:
            url = self.args.get("url", "")
            return f'  await page.goto("{url}");\n  await page.waitForTimeout(1000);  // 等待页面稳定'

        # 切换标签页
        elif action_name in ["tabs", "browser_tabs"]:
            action_type = self.args.get("action", "")
            if action_type == "select":
                index = self.args.get("index", 0)
                return (f'  // 切换到第 {index} 个标签页\n'
                        f'  const pages = await page.context().pages();\n'
                        f'  page = pages[{index}];\n'
                        f'  await page.waitForLoadState("domcontentloaded");  // 等待页面加载\n'
                        f'  await page.waitForTimeout(1000);  // 停顿 1 秒')
            return f'  // 标签页操作: {action_type}'

        # 等待类动作（不需要额外停顿）
        elif action_name in ["wait", "browser_wait", "wait_for"]:
            time_val = self.args.get("time", self.args.get("timeout", 1))
            return f'  await page.waitForTimeout({time_val * 1000});  // 等待 {time_val} 秒'

        # 快照类动作（回放时可跳过）
        elif "snapshot" in action_name.lower():
            return f'  // snapshot (回放时跳过)'

        # 截图类动作（回放时可跳过）
        elif "screenshot" in action_name.lower():
            return f'  // screenshot (回放时跳过)'

        # 默认处理
        return f'  // Unknown action: {self.action}'

    def _extract_action_name(self) -> str:
        """从工具名称中提取实际的动作名称

        例如: mcp_playwright-local_browser_navigate -> navigate
        """
        action = self.action.lower()

        # 处理 MCP 工具名前缀: mcp_playwright-local_browser_xxx
        if "browser_" in action:
            parts = action.split("browser_")
            if len(parts) > 1:
                return parts[-1]

        return action


class PlaywrightRecorder:
    """Playwright 执行记录器"""

    def __init__(self, output_dir: str = "recorded_scripts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.steps: List[PlaywrightStep] = []
        self._snapshot_count = 0

    @staticmethod
    def is_snapshot_tool(action: str) -> bool:
        """判断是否是 snapshot 工具"""
        return 'snapshot' in action.lower()

    @staticmethod
    def is_playwright_action(action: str) -> bool:
        """判断是否是 playwright 相关动作"""
        playwright_actions = [
            'click', 'fill', 'goto', 'navigate', 'type', 'select',
            'check', 'uncheck', 'press', 'hover', 'focus', 'wait',
            'screenshot', 'snapshot', 'close', 'tabs'
        ]
        action_lower = action.lower()
        return any(a in action_lower for a in playwright_actions)

    def update_snapshot_count(self) -> None:
        """更新 snapshot 计数（当调用 snapshot 后调用）"""
        self._snapshot_count += 1
        logger.debug(f"[PlaywrightRecorder] Snapshot 计数: {self._snapshot_count}")

    def record_step(self, action: str, args: Dict[str, Any], raw_response: str = "") -> None:
        """记录一个执行步骤

        Args:
            action: 动作类型
            args: 动作参数
            raw_response: 原始响应 (observation)
        """
        step = PlaywrightStep(action, args, raw_response)

        # 尝试从 observation 中提取完整的 JS 代码
        step.extract_code_from_observation(raw_response)

        self.steps.append(step)
        logger.debug(f"[PlaywrightRecorder] 记录步骤: {action}")

    def generate_replayable_script(self, task_name: str) -> str:
        """生成可回放的 JavaScript 脚本

        Args:
            task_name: 任务名称（用于脚本内注释）

        Returns:
            生成的脚本文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_name = f"{timestamp}.js"

        # 处理任务名称：移除换行符
        clean_task_name = task_name.replace('\n', ' ').replace('\r', ' ')
        if len(clean_task_name) > 100:
            clean_task_name = clean_task_name[:100] + "..."

        code_lines = [
            "// =========================================",
            "// 自动生成的 Playwright 回放脚本",
            f"// 任务: {clean_task_name}",
            f"// 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"// 步骤数: {len(self.steps)}",
            "// =========================================",
            "//",
            "// 运行方式:",
            "//   node script.js",
            "//",
            "// 确保已安装 playwright:",
            "//   npm install playwright",
            "",
            "const { chromium } = require('playwright');",
            "",
            "(async () => {",
            "  const browser = await chromium.launch({",
            "    channel: 'chrome',",
            "    headless: false",
            "  });",
            "  let page = await browser.newPage();",
            "  page.setDefaultTimeout(60000);  // 设置默认超时为 60 秒",
            "",
        ]

        # 去除连续重复的 goto 步骤
        deduped_steps = self._deduplicate_goto_steps()

        # 生成每个步骤的代码
        for step in deduped_steps:
            code_lines.append(step.to_js_code())

        code_lines.extend([
            "",
            "  await browser.close();",
            "})();",
        ])

        script_content = "\n".join(code_lines)

        script_path = self.output_dir / script_name
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        logger.info(f"[PlaywrightRecorder] 脚本已生成: {script_path}")
        return str(script_path)

    def _deduplicate_goto_steps(self) -> List[PlaywrightStep]:
        """去除连续重复的 goto 步骤"""
        last_url = None
        deduped = []
        for step in self.steps:
            action_name = step._extract_action_name()
            if action_name in ["goto", "navigate"]:
                url = step.args.get("url", "")
                if url != last_url:
                    deduped.append(step)
                    last_url = url
                else:
                    logger.debug(f"[PlaywrightRecorder] 跳过重复的 goto: {url}")
            else:
                deduped.append(step)
        return deduped

    def clear(self) -> None:
        """清空记录"""
        self.steps.clear()
        self._snapshot_count = 0
        logger.debug("[PlaywrightRecorder] 记录已清空")
