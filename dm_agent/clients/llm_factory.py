"""LLM 客户端工厂函数。"""

from __future__ import annotations

from typing import Optional

from .abc_client import ABCClient
from .base_client import BaseLLMClient
from .deepseek_client import DeepSeekClient
from .openai_client import OpenAIClient
from .qwen_client import QwenClient


def create_llm_client(
    provider: str,
    api_key: str,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 600,
    **kwargs,
) -> BaseLLMClient:
    """创建 LLM 客户端实例。

    Args:
        provider: 提供商名称 ("abc", "deepseek", "openai", "qwen")
        api_key: API 密钥（ABC 提供商可传空字符串）
        model: 模型名称（可选，使用默认值）
        base_url: API 基础 URL（可选，使用默认值）
        timeout: 请求超时时间（秒）
        **kwargs: 其他特定于提供商的参数（如 request_id）

    Returns:
        对应的 LLM 客户端实例

    Raises:
        ValueError: 如果提供商不支持
    """
    provider_lower = provider.lower()

    if provider_lower == "abc":
        params = {
            "api_key": api_key or "",
            "model": model or "",
            "base_url": base_url or "",
            "timeout": timeout,
        }
        if "request_id" in kwargs:
            params["request_id"] = kwargs["request_id"]
        return ABCClient(**params)

    elif provider_lower == "deepseek":
        params = {
            "api_key": api_key,
            "model": model or "deepseek-chat",
            "base_url": base_url or "https://api.deepseek.com",
            "timeout": timeout,
        }
        return DeepSeekClient(**params)

    elif provider_lower == "openai":
        params = {
            "api_key": api_key,
            "model": model or "gpt-5",
            "base_url": base_url or "",
            "timeout": timeout,
        }
        return OpenAIClient(**params)

    elif provider_lower == "qwen":
        params = {
            "api_key": api_key,
            "model": model or "qwen-turbo",
            "base_url": base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "timeout": timeout,
        }
        return QwenClient(**params)

    else:
        raise ValueError(
            f"不支持的提供商: {provider}。"
            f"支持的提供商: abc, deepseek, openai, qwen"
        )


# 提供商默认配置
PROVIDER_DEFAULTS = {
    "abc": {
        "model": "",
        "base_url": "",
        "request_id": "12",
    },
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
    },
    "openai": {
        "model": "gpt-5",
        "base_url": "",
    },
    "qwen": {
        "model": "qwen-turbo",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
}
