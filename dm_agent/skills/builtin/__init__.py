"""内置技能注册"""

from __future__ import annotations

from typing import List

from ..base import BaseSkill
from .python_expert import PythonExpertSkill
from .db_expert import DatabaseExpertSkill
from .frontend_dev import FrontendDevSkill


def get_builtin_skills() -> List[BaseSkill]:
    """返回所有内置技能实例列表。"""
    return [
        PythonExpertSkill(),
        DatabaseExpertSkill(),
        FrontendDevSkill(),
    ]
