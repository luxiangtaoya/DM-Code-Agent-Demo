"""MCP 配置管理"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """
    表示单个MCP服务器的配置信息，包括启动命令、参数、环境变量等
    
    Attributes:
        name (str): MCP服务器名称，用作唯一标识符
        command (str): 启动MCP服务器的命令（如'npx'、'python'等）
        args (List[str]): 命令行参数列表
        env (Optional[Dict[str, str]]): 环境变量字典，None表示使用默认环境
        enabled (bool): 服务器是否启用，默认为True
    """
    # MCP服务器启动名称
    name: str
    # 启动命令  
    command: str
    # 命令行参数
    args: List[str] = field(default_factory=list)
    # 环境变量
    env: Optional[Dict[str, str]] = None
    # 服务器是否启用
    enabled: bool = True

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "MCPServerConfig":
        """
        从字典数据创建MCPServerConfig实例
        
        Args:
            name (str): 服务器名称
            data (Dict[str, Any]): 包含配置信息的字典
            
        Returns:
            MCPServerConfig: 创建的配置实例
            
        Examples:
            >>> data = {"command": "npx", "args": ["@playwright/mcp@latest"], "enabled": True}
            >>> config = MCPServerConfig.from_dict("playwright", data)
            >>> config.command
            'npx'
        """
        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env"),
            enabled=data.get("enabled", True)
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        将配置转换为字典格式，便于序列化存储
        
        Returns:
            result (Dict[str, Any]): 包含配置信息的字典
            
        Examples:
            >>> config = MCPServerConfig("test", "npx", ["tool"], {"DEBUG": "1"}, True)
            >>> data = config.to_dict()
            >>> "command" in data and "args" in data
            True
        """
        result = {
            "command": self.command,
            "args": self.args,
        }
        if self.env:
            result["env"] = self.env
        if not self.enabled:
            result["enabled"] = self.enabled
        return result


@dataclass
class MCPConfig:
    """
    管理所有MCP服务器的配置集合，提供对多个MCP服务器配置的统一管理接口

    Attributes:
        servers (Dict[str, MCPServerConfig]): 服务器名称到配置的映射字典
        use_static_tools (bool): 是否使用静态工具定义替代 MCP tools/list
                                设为 True 可跳过 tools/list 调用，节省上下文窗口
    """

    servers: Dict[str, MCPServerConfig] = field(default_factory=dict)
    use_static_tools: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPConfig":
        """
        从字典数据创建MCPConfig实例
        
        Args:
            data (Dict[str, Any]): 包含MCP配置信息的字典，应包含'mcpServers'键
            
        Returns:
            MCPConfig: 创建的总配置实例
            
        Examples:
            >>> data = {
            ...     "mcpServers": {
            ...         "playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]}
            ...     }
            ... }
            >>> config = MCPConfig.from_dict(data)
            >>> len(config.servers)
            1
        """
        mcp_servers = data.get("mcpServers", {})
        servers = {
            name: MCPServerConfig.from_dict(name, config)
            for name, config in mcp_servers.items()
        }
        return cls(
            servers=servers,
            use_static_tools=data.get("use_static_tools", False),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        将总配置转换为字典格式
        
        Returns:
            Dict[str, Any]: 包含所有服务器配置的字典
            
        Examples:
            >>> server_config = MCPServerConfig("test", "npx", ["tool"])
            >>> config = MCPConfig()
            >>> config.add_server(server_config)
            >>> data = config.to_dict()
            >>> "mcpServers" in data
            True
        """
        return {
            "mcpServers": {
                name: config.to_dict()
                for name, config in self.servers.items()
            }
        }

    def add_server(self, config: MCPServerConfig) -> None:
        """
        添加MCP服务器配置到总配置中
        
        Args:
            config (MCPServerConfig): 要添加的服务器配置
            
        Examples:
            >>> config = MCPConfig()
            >>> server_config = MCPServerConfig("test", "npx", ["tool"])
            >>> config.add_server(server_config)
            >>> "test" in config.servers
            True
        """
        self.servers[config.name] = config

    def remove_server(self, name: str) -> None:
        """
        从总配置中移除指定的MCP服务器配置
        
        Args:
            name (str): 要移除的服务器名称
            
        Examples:
            >>> config = MCPConfig()
            >>> server_config = MCPServerConfig("test", "npx", ["tool"])
            >>> config.add_server(server_config)
            >>> config.remove_server("test")
            >>> "test" in config.servers
            False
        """
        if name in self.servers:
            del self.servers[name]

    def get_enabled_servers(self) -> Dict[str, MCPServerConfig]:
        """
        获取所有启用的服务器配置
        
        Returns:
            enabled_servers (Dict[str, MCPServerConfig]): 包含所有启用服务器配置的字典
            
        Examples:
            >>> config = MCPConfig()
            >>> server1 = MCPServerConfig("enabled_server", "npx", ["tool"], enabled=True)
            >>> server2 = MCPServerConfig("disabled_server", "npm", ["tool"], enabled=False)
            >>> config.add_server(server1)
            >>> config.add_server(server2)
            >>> enabled_servers = config.get_enabled_servers()
            >>> enabled_servers
            {"enabled_server" : {"command": "npx", "args": ["tool"] , "enabled": True}}
            >>> "enabled_server" in enabled_servers
            True
        """
        return {
            name: config
            for name, config in self.servers.items()
            if config.enabled
        }


def load_mcp_config(config_path: str = "mcp_config.json") -> MCPConfig:
    """
    从文件加载MCP配置

    如果配置文件不存在，则返回空的MCPConfig实例。如果文件存在但解析失败，则打印警告并返回空配置。

    Args:
        config_path (str, optional): 配置文件路径，默认为"mcp_config.json"

    Returns:
        MCPConfig: 加载的配置实例或空配置实例

    Examples:
        >>> config = load_mcp_config("nonexistent.json")
        >>> isinstance(config, MCPConfig)
        True
    """
    # 如果是相对路径，尝试相对于 backend 目录
    if not os.path.isabs(config_path):
        # 获取 dm_agent 的父目录（即 backend）
        backend_dir = Path(__file__).parent.parent.parent
        abs_path = backend_dir / config_path
        logger.debug(f"[MCP Config] 查找配置文件: {config_path} -> {abs_path}")
    else:
        abs_path = Path(config_path)

    if not abs_path.exists():
        logger.warning(f"[MCP Config] 配置文件不存在: {abs_path}，返回空配置")
        return MCPConfig()

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        config = MCPConfig.from_dict(data)
        enabled_count = len(config.get_enabled_servers())
        total_count = len(config.servers)
        logger.info(f"[MCP Config] 成功加载配置: {abs_path}，共 {total_count} 个服务器，其中 {enabled_count} 个已启用")
        return config
    except Exception as e:
        logger.error(f"[MCP Config] 加载 MCP 配置失败: {e}，使用空配置")
        return MCPConfig()


def save_mcp_config(config: MCPConfig, config_path: str = "mcp_config.json") -> bool:
    """
    保存MCP配置到文件
    
    将MCP配置以JSON格式保存到指定文件中，使用2个空格缩进以提高可读性。

    Args:
        config (MCPConfig): 要保存的MCP配置对象
        config_path (str, optional): 配置文件路径，默认为"mcp_config.json"

    Returns:
        bool: 保存成功返回True，失败返回False
        
    Examples:
        >>> config = MCPConfig()
        >>> success = save_mcp_config(config, "test_config.json")
        >>> success
        True
        >>> import os
        >>> os.path.exists("test_config.json")
        True
        >>> os.remove("test_config.json")  # 清理测试文件
    """
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ 保存 MCP 配置失败: {e}")
        return False
