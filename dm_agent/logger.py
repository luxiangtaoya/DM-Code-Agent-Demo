"""统一的日志配置模块"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 全局日志已初始化标记
_logging_initialized = False


def setup_logger(
    name: str = __name__,
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_to_console: bool = True
) -> logging.Logger:
    """
    设置并返回一个配置好的日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_to_file: 是否记录到文件
        log_to_console: 是否输出到控制台

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加处理器
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # 文件处理器
    if log_to_file:
        log_file = LOG_DIR / f"{name.replace('.', '_')}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def setup_global_logging(level: int = logging.DEBUG, log_to_file: bool = True):
    """
    设置全局日志配置

    这将配置根日志记录器，所有子日志记录器都会继承这个配置。

    Args:
        level: 日志级别，默认 DEBUG
        log_to_file: 是否记录到文件，默认 True
    """
    global _logging_initialized

    # 避免重复初始化
    if _logging_initialized:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除现有的处理器
    root_logger.handlers.clear()

    # 简洁的控制台格式（不显示时间和 logger 名）
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )

    # 详细的文件格式
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器（仅 INFO 及以上）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（所有级别）
    if log_to_file:
        main_log_file = LOG_DIR / "dm_agent.log"
        main_file_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_file_handler.setLevel(level)
        main_file_handler.setFormatter(file_formatter)
        root_logger.addHandler(main_file_handler)

    _logging_initialized = True
    root_logger.info("全局日志配置已初始化")


def get_logger(name: str = None) -> logging.Logger:
    """
    获取日志记录器

    Args:
        name: 日志记录器名称，如果为 None 则返回调用者的模块名

    Returns:
        Logger 实例
    """
    if name is None:
        # 获取调用者的模块名
        import inspect
        frame = inspect.currentframe()
        module = inspect.getmodule(frame.f_back)
        name = module.__name__ if module else __name__

    return logging.getLogger(name)


def is_logging_initialized() -> bool:
    """检查日志系统是否已初始化"""
    return _logging_initialized