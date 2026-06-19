"""上下文压缩器 —— 当对话历史总字符数超过阈值时自动压缩。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..clients.base_client import BaseLLMClient


class ContextCompressor:

    """
    当对话历史总字符数超过 max_chars 时自动触发压缩。

    压缩方式：保留最近 keep_recent 轮完整消息，更早的消息截断拼接为一条摘要。

    Attributes:
        client: LLM 客户端（当前未使用，预留用于语义摘要）。
        max_chars: 总字符数阈值，超过后触发压缩（默认 10000）。
        keep_recent: 压缩时保留的最近完整对话轮数（默认 3）。
    """

    def __init__(
        self,
        client: Optional[BaseLLMClient] = None,
        max_chars: int = 10000,
        keep_recent: int = 3,
    ):
        """
        初始化上下文压缩器。

        Args:
            client: LLM 客户端（预留）。
            max_chars: 对话历史总字符数阈值，超过后触发压缩。
            keep_recent: 压缩时保留的最近对话轮数，每轮 = user + assistant 各一条。
        """
        self.client = client
        self.max_chars = max_chars
        self.keep_recent = keep_recent

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def should_compress(self, history: List[Dict[str, str]]) -> bool:
        """判断是否需要压缩 —— 当对话历史总字符数超过 max_chars 时返回 True。"""
        total_chars = sum(len(msg.get("content", "")) for msg in history)
        return total_chars > self.max_chars

    def compress(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        压缩对话历史。

        保留系统消息 + 最近 keep_recent 轮完整消息，
        更早的消息每条截取前 200 字符，拼成一条「历史对话记录」。

        Args:
            history: 原始对话历史列表。

        Returns:
            压缩后的对话历史列表。
        """
        if not history:
            return []

        # 分离系统消息和非系统消息
        system_messages = [msg for msg in history if msg.get("role") == "system"]
        non_system = [msg for msg in history if msg.get("role") != "system"]

        # 保留最近的消息（keep_recent 轮 = keep_recent * 2 条消息，user + assistant 各一条）
        keep_count = self.keep_recent * 2
        recent_messages = (
            non_system[-keep_count:] if len(non_system) > keep_count else non_system
        )

        # 需要压缩的中间消息
        middle_messages = (
            non_system[:-keep_count] if len(non_system) > keep_count else []
        )

        # 如果有中间消息，进行压缩
        compressed_middle: List[Dict[str, str]] = []
        if middle_messages:
            key_info = self._extract_key_information(middle_messages)

            # fallback：如果没有提取到结构化信息，则使用截断拼接
            if not key_info:
                compressed_parts = []
                for msg in middle_messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    truncated = content[:200] + "..." if len(content) > 200 else content
                    compressed_parts.append(f"[{role}]: {truncated}")
                key_info = "历史对话记录：\n" + "\n".join(compressed_parts)

            compressed_middle = [{"role": "user", "content": key_info}]

        # 组合：系统消息 + 压缩的中间历史 + 最近消息
        return system_messages + compressed_middle + recent_messages

    # ------------------------------------------------------------------
    # 信息提取（浏览器自动化专用）
    # ------------------------------------------------------------------

    def _extract_key_information(self, messages: List[Dict[str, str]]) -> str:
        """从中间消息中提取关键信息，生成结构化摘要。

        针对浏览器自动化场景，提取：
        - 已完成的操作步骤（browser_* 工具调用）
        - 当前访问的 URL
        - 遇到过的错误
        - 最终的完成结果
        """
        if not messages:
            return ""

        parts: List[str] = []

        # 1. 提取所有 browser_ 工具调用 —— 这是最重要的信息
        actions: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            # 匹配 agent 的 JSON 响应中的 action
            for match in re.finditer(r'"action"\s*:\s*"([^"]+)"', content):
                action = match.group(1)
                if action.startswith("browser_") or action in ("finish", "task_complete"):
                    actions.append(action)

        if actions:
            parts.append("已执行的操作：" + " → ".join(actions))

        # 2. 提取导航过的 URL
        urls: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            for match in re.finditer(r'https?://[^\s"\'，,\n]+', content):
                url = match.group(0).rstrip("。，.")
                if url not in urls:
                    urls.append(url)
        if urls:
            parts.append("访问过的页面：" + ", ".join(urls[-3:]))  # 最多保留最近 3 个

        # 3. 提取 step_abbreviation（步骤简述）
        steps: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            for match in re.finditer(r'"step_abbreviation"\s*:\s*"([^"]+)"', content):
                abbrev = match.group(1)
                if abbrev not in steps:
                    steps.append(abbrev)
        if steps:
            parts.append("步骤列表：" + " → ".join(steps))

        # 4. 提取错误
        errors = []
        for msg in messages:
            content = msg.get("content", "")
            for kw in ("错误", "error", "Error", "失败", "异常"):
                if kw in content:
                    # 取包含关键词的行
                    for line in content.split("\n"):
                        if kw in line and len(line) < 200:
                            errors.append(line.strip())
                    break  # 每条消息最多提取一次
        if errors:
            parts.append("遇到的错误：" + "；".join(errors[:3]))

        # 5. 提取 finish 的最终答案
        for msg in messages:
            content = msg.get("content", "")
            if '"action": "finish"' in content:
                m = re.search(r'"action_input"\s*:\s*"([^"]*)"', content)
                if m:
                    parts.append("之前任务结果：" + m.group(1))
                    break

        if not parts:
            return ""

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def get_compression_stats(
        self, original: List[Dict[str, str]], compressed: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """获取压缩统计信息。"""
        original_chars = sum(len(msg.get("content", "")) for msg in original)
        compressed_chars = sum(len(msg.get("content", "")) for msg in compressed)
        return {
            "original_chars": original_chars,
            "compressed_chars": compressed_chars,
            "original_messages": len(original),
            "compressed_messages": len(compressed),
            "compression_ratio": (
                1 - compressed_chars / original_chars if original_chars > 0 else 0
            ),
            "saved_chars": original_chars - compressed_chars,
        }
