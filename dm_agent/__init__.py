"""DM-Agent - 基于 ReAct 的多模型智能体系统

支持多种 LLM API (ABC、DeepSeek、OpenAI、Qwen) 的 ReAct 智能体实现。
"""

from .core import ReactAgent, Step
from .clients import (
    ABCClient,
    BaseLLMClient,
    LLMError,
    DeepSeekClient,
    OpenAIClient,
    QwenClient,
    create_llm_client,
    PROVIDER_DEFAULTS,
)
from .tools import Tool, default_tools
from .prompts import build_code_agent_prompt
from .skills import BaseSkill, ConfigSkill, SkillMetadata, SkillManager
from .screenshot import ScreenshotManager
from .runner import AgentRunner, AgentConfig

__version__ = "1.0.0"

__all__ = [
    # Core
    "ReactAgent",
    "Step",
    # Runner
    "AgentRunner",
    "AgentConfig",
    # Clients
    "ABCClient",
    "BaseLLMClient",
    "LLMError",
    "DeepSeekClient",
    "OpenAIClient",
    "QwenClient",
    "create_llm_client",
    "PROVIDER_DEFAULTS",
    # Tools
    "Tool",
    "default_tools",
    # Prompts
    "build_code_agent_prompt",
    # Skills
    "BaseSkill",
    "ConfigSkill",
    "SkillMetadata",
    "SkillManager",
    # Screenshot
    "ScreenshotManager",
]
