"""ABC 公司自定义 Agent API 客户端

使用 session 初始化 + SSE 流式 chat 的调用方式，与 OpenAI 兼容 API 不同。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import requests

from .base_client import BaseLLMClient, LLMError


class ABCClientError(LLMError):
    """当 ABC API 请求失败时抛出。"""


class ABCClient(BaseLLMClient):
    """ABC 公司自定义 Agent API 的客户端。

    调用流程：
    1. POST /chatabc/init_session → 获取 session_id
    2. POST /chatabc/chat (stream=True) → SSE 流式接收回复

    回复格式为 SSE 事件流：
    - event: chunk + data: {content, additional_kwargs: {reasoning}}  → 流式片段
    - event: message + data: {...} → 汇总包（忽略，避免重复）

    Attributes:
        endpoint: API 端点基础 URL
        request_id: 请求标识头
        session_id: 初始化后获得的会话 ID
        _session: requests.Session 复用连接
    """

    def __init__(
        self,
        api_key: str = "",
        *,
        model: str = "",
        base_url: str = "",
        timeout: int = 600,
        request_id: str = "12",
    ) -> None:
        # ABC API 不需要 api_key，但基类要求传入，给空字符串即可
        super().__init__(api_key or "no-key", model=model, base_url=base_url, timeout=timeout)
        self.endpoint = base_url  # 完整的 API 端点 URL
        self.request_id = request_id
        self.session_id: Optional[str] = None
        self._session = requests.Session()
        self._session.headers.update({"requestId": self.request_id})

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------
    def _init_session(self) -> str:
        """初始化会话，获取 session_id"""
        url = f"{self.endpoint}/chatabc/init_session"
        payload = {
            "appId": "",
            "trCode": "",
            "trVersion": "",
            "timestamp": 1,
            "agent_id": "",
            "requestId": "",
            "data": {"prompt_variables": []},
        }

        try:
            resp = self._session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            self.session_id = data["data"]["session_id"]
            return self.session_id
        except Exception as e:
            raise ABCClientError(f"初始化 ABC 会话失败: {e}") from e

    # ------------------------------------------------------------------
    # 消息转换
    # ------------------------------------------------------------------
    @staticmethod
    def _messages_to_text(messages: List[Dict[str, str]]) -> str:
        """将 OpenAI 格式的消息列表转为单段文本，供 ABC API 的 txt 字段使用。

        格式：系统消息在前，对话轮次依次拼接。
        """
        parts: List[str] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "system":
                parts.append(content)
            elif role == "user":
                parts.append(f"用户：{content}")
            elif role == "assistant":
                parts.append(f"助手：{content}")
            else:
                parts.append(content)
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # 核心接口
    # ------------------------------------------------------------------
    def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        stream: bool = True,
        **extra: Any,
    ) -> Dict[str, Any]:
        """发送请求到 ABC API，返回聚合后的响应字典。

        Args:
            messages: 消息列表
            stream: 是否流式（ABC API 强制流式，忽略此参数）
            **extra: 额外参数（如 temperature）

        Returns:
            包含 content 和 reasoning 的字典:
            {"content": "...", "reasoning": "..."}
        """
        # 确保会话已初始化
        if not self.session_id:
            self._init_session()

        # 构建请求
        txt = self._messages_to_text(messages)
        url = f"{self.endpoint}/chatabc/chat"
        payload = {
            "appId": "",
            "trCode": "",
            "trVersion": "",
            "timestamp": 1,
            "requestId": "",
            "files": [],
            "data": {
                "txt": txt,
                "session_id": self.session_id,
                "stream": True,
                "files": [],
            },
        }

        # 合并额外参数（如 temperature）
        if extra:
            payload["data"].update(
                {k: v for k, v in extra.items() if k not in ("txt", "session_id", "stream", "files")}
            )

        # 发送流式请求
        try:
            resp = self._session.post(
                url, json=payload, timeout=self.timeout, stream=True
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ABCClientError(f"ABC API 请求失败: {e}") from e

        # 解析 SSE 流
        return self._parse_sse_stream(resp)

    def _parse_sse_stream(self, response: requests.Response) -> Dict[str, Any]:
        """解析 SSE 流式响应，提取 content 和 reasoning。

        只处理 event: chunk 的数据；event: message 的汇总包跳过以避免重复。
        """
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        current_event = ""
        final_message: Dict[str, Any] = {}

        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue

            # 识别事件类型
            if line.startswith("event:"):
                current_event = line.split("event:", 1)[1].strip()
                continue

            # 只处理 chunk 事件
            if current_event != "chunk":
                continue

            if not line.startswith("data:"):
                continue

            json_str = line[len("data:"):].strip()

            if not json_str or json_str == "[DONE]":
                continue

            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                continue

            # 提取 reasoning（放在 additional_kwargs 中）
            reasoning = data.get("additional_kwargs", {}).get("reasoning")
            if reasoning and isinstance(reasoning, str):
                reasoning_parts.append(reasoning)

            # 提取 content
            content = data.get("content")
            if content and isinstance(content, str):
                content_parts.append(content)

        full_content = "".join(content_parts)
        full_reasoning = "".join(reasoning_parts)

        # 构建返回值：content 为主，reasoning 可选
        result: Dict[str, Any] = {}
        if full_reasoning:
            result["reasoning"] = full_reasoning
        if full_content:
            result["content"] = full_content
        else:
            # 如果没有 content，可能有 message 类型的最终回复
            result["content"] = full_reasoning or ""

        # 也把 reasoning 合并到 content 前面（有些模型把思考放在 reasoning 中）
        if full_reasoning and full_content:
            result["content"] = full_content  # content 已经包含了最终答案

        return result

    def extract_text(self, data: Dict[str, Any]) -> str:
        """从 ABC API 响应中提取文本内容。

        Args:
            data: complete() 返回的字典

        Returns:
            提取的文本内容
        """
        if not isinstance(data, dict):
            raise ABCClientError("意外的响应负载类型。")

        content = data.get("content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()

        raise ABCClientError("无法从 ABC API 响应中提取文本。")

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def reset_session(self) -> None:
        """重置会话，下次调用 complete() 时会重新初始化"""
        self.session_id = None

    def close(self) -> None:
        """关闭会话"""
        self._session.close()
