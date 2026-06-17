"""Playwright MCP 静态工具定义

只包含项目实际使用的工具，使用精简的中文描述以节省上下文窗口。
原版 34 个工具完整描述约占 ~4670 tokens，精简后 17 个工具约占 ~1500 tokens，
节省约 68% 的上下文空间。
"""

from typing import Any, Dict, List

# 项目实际使用的 Playwright 工具（17/34）
# 每个工具包含: name (MCP原始名称), description (精简描述), inputSchema (参数定义)
PLAYWRIGHT_STATIC_TOOLS: List[Dict[str, Any]] = [
    # ========== 页面导航 ==========
    {
        "name": "browser_navigate",
        "description": "导航到指定URL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "目标URL"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "browser_navigate_back",
        "description": "返回上一页",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "browser_close",
        "description": "关闭当前页面",
        "inputSchema": {"type": "object", "properties": {}},
    },

    # ========== 元素交互 ==========
    {
        "name": "browser_click",
        "description": "点击页面元素",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "元素的可读描述"},
                "target": {"type": "string", "description": "页面快照中的元素引用或唯一选择器"},
                "doubleClick": {"type": "boolean", "description": "是否双击"},
                "button": {"type": "string", "description": "鼠标按键: left/right/middle"},
                "modifiers": {"type": "array", "description": "修饰键"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "browser_hover",
        "description": "悬停在元素上",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "元素的可读描述"},
                "target": {"type": "string", "description": "页面快照中的元素引用或唯一选择器"},
            },
            "required": ["target"],
        },
    },
    {
        "name": "browser_type",
        "description": "在可编辑元素中输入文本",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "元素的可读描述"},
                "target": {"type": "string", "description": "页面快照中的元素引用或唯一选择器"},
                "text": {"type": "string", "description": "要输入的文本"},
                "submit": {"type": "boolean", "description": "输入后是否按回车提交"},
                "slowly": {"type": "boolean", "description": "是否逐字符输入"},
            },
            "required": ["target", "text"],
        },
    },
    {
        "name": "browser_press_key",
        "description": "按下键盘按键",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "按键名称，如 ArrowLeft 或 a"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "browser_select_option",
        "description": "在下拉菜单中选择选项",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "元素的可读描述"},
                "target": {"type": "string", "description": "页面快照中的元素引用或唯一选择器"},
                "values": {"type": "array", "description": "要选择的值数组"},
            },
            "required": ["target", "values"],
        },
    },
    {
        "name": "browser_drag",
        "description": "拖拽元素到另一个位置",
        "inputSchema": {
            "type": "object",
            "properties": {
                "startElement": {"type": "string", "description": "源元素的可读描述"},
                "startTarget": {"type": "string", "description": "源元素的页面引用"},
                "endElement": {"type": "string", "description": "目标元素的可读描述"},
                "endTarget": {"type": "string", "description": "目标元素的页面引用"},
            },
            "required": ["startTarget", "endTarget"],
        },
    },
    {
        "name": "browser_drop",
        "description": "将文件或数据拖放到元素上",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "元素的可读描述"},
                "target": {"type": "string", "description": "页面快照中的元素引用"},
                "paths": {"type": "array", "description": "要拖放的文件绝对路径"},
                "data": {"type": "object", "description": "MIME类型到数据的映射"},
            },
            "required": ["target"],
        },
    },

    # ========== 表单 ==========
    {
        "name": "browser_fill_form",
        "description": "批量填写表单字段",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fields": {"type": "array", "description": "要填写的字段列表"},
            },
            "required": ["fields"],
        },
    },

    # ========== 页面信息获取 ==========
    {
        "name": "browser_snapshot",
        "description": "获取页面无障碍快照（推荐代替截图用于分析页面结构）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "元素引用，不传则获取整页"},
                "filename": {"type": "string", "description": "保存到文件"},
                "depth": {"type": "number", "description": "快照树深度限制"},
                "boxes": {"type": "boolean", "description": "是否包含元素边界框坐标"},
            },
        },
    },
    {
        "name": "browser_take_screenshot",
        "description": "截取页面截图（不能基于截图执行操作，请用 browser_snapshot）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "元素的可读描述"},
                "target": {"type": "string", "description": "元素引用，不传则截取整页"},
                "type": {"type": "string", "description": "图片格式: png/jpeg"},
                "filename": {"type": "string", "description": "保存文件名"},
                "fullPage": {"type": "boolean", "description": "是否截取完整页面"},
            },
            "required": ["type"],
        },
    },

    # ========== 弹窗 ==========
    {
        "name": "browser_handle_dialog",
        "description": "处理浏览器弹窗（alert/confirm/prompt）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "accept": {"type": "boolean", "description": "是否接受弹窗"},
                "promptText": {"type": "string", "description": "prompt弹窗的输入文本"},
            },
            "required": ["accept"],
        },
    },

    # ========== 标签页 ==========
    {
        "name": "browser_tabs",
        "description": "管理浏览器标签页（列出/新建/关闭/切换）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作: list/new/close/select"},
                "index": {"type": "number", "description": "标签页索引（close/select时使用）"},
                "url": {"type": "string", "description": "新建标签页的URL"},
            },
            "required": ["action"],
        },
    },

    # ========== JS 执行 ==========
    {
        "name": "browser_evaluate",
        "description": "在页面或元素上执行JavaScript表达式",
        "inputSchema": {
            "type": "object",
            "properties": {
                "element": {"type": "string", "description": "元素的可读描述"},
                "target": {"type": "string", "description": "元素引用"},
                "function": {"type": "string", "description": "JS函数: () => { ... } 或 (element) => { ... }"},
                "filename": {"type": "string", "description": "保存结果到文件"},
            },
            "required": ["function"],
        },
    },
    {
        "name": "browser_run_code_unsafe",
        "description": "执行Playwright代码片段（可操作page对象，功能最强大但需谨慎使用）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Playwright代码: async (page) => { ... }"},
                "filename": {"type": "string", "description": "从文件加载代码"},
            },
        },
    },
]
