"""DM-Code-Agent 启动入口。

使用方式：直接修改本文件中的 TASK 和 CONFIG，然后 ``python main.py``。

所有配置项也可以通过在项目根目录的 ``.env`` 文件中设置环境变量来覆盖。
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 确保项目根目录在 path 中
sys.path.insert(0, str(Path(__file__).parent))

from dm_agent.runner import AgentRunner, AgentConfig

# ============================================================
# 1. 加载 .env
# ============================================================
load_dotenv()


def _env(key: str, default: str = "") -> str:
    """读取环境变量，不存在时返回默认值。"""
    return os.getenv(key, default)


# ============================================================
# 2. 配置 —— 优先使用环境变量，没有则使用这里的默认值
# ============================================================
CONFIG = AgentConfig(
    provider=_env("PROVIDER", "qwen"),
    api_key=_env("API_KEY", ""),
    model=_env("MODEL_NAME", "qwen3.6-flash"),
    base_url=_env("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    max_steps=int(_env("MAX_STEPS", "100")),
    temperature=float(_env("TEMPERATURE", "0.7")),
    abc_request_id=_env("ABC_REQUEST_ID", "12"),
    mcp_config_path=_env("MCP_CONFIG_PATH", "mcp_config.json"),
    output_dir=_env("OUTPUT_DIR", "recorded_scripts"),
)

# ============================================================
# 3. 任务描述 —— 在此处编写你要执行的任务
# ============================================================
TASK = """
1.打开网站https://www.abchina.com/cn/；
2.点击页面下方的"基金"链接；
3.在产品筛选区域投资类型选择"股票型"，时间区间为："近一年"，风险等级选择"R4中高风险"；
4.输出一共查到了多少个满足条件的基金。
"""

# ============================================================
# 4. 启动
# ============================================================
if __name__ == "__main__":
    runner = AgentRunner(CONFIG)
    try:
        result = runner.run(TASK.strip())
    except Exception as e:
        print(f"执行失败: {e}", file=sys.stderr)
        sys.exit(1)
