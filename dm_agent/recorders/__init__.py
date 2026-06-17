"""执行记录器模块 - 用于记录和生成可回放的自动化脚本"""

from .playwright_recorder import PlaywrightStep, PlaywrightRecorder

__all__ = [
    "PlaywrightStep",
    "PlaywrightRecorder",
]
