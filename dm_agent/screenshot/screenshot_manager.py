"""截图管理模块 - 支持浏览器步骤截图、添加文字标注和生成GIF"""

from __future__ import annotations

import os
import base64
from typing import List, Optional
from datetime import datetime
from io import BytesIO


class ScreenshotManager:
    """截图管理器 - 管理浏览器自动化任务的截图"""

    def __init__(
        self,
        output_dir: str = "task_screenshots",
        enable_gif: bool = True,
        gif_duration: int = 1000
    ):
        """
        初始化截图管理器

        Args:
            output_dir: 截图保存目录
            enable_gif: 是否生成 GIF
            gif_duration: GIF 每帧显示时间（毫秒）
        """
        # 使用绝对路径
        self.output_dir = os.path.abspath(output_dir)
        self.enable_gif = enable_gif
        self.gif_duration = gif_duration
        self.screenshots: List[tuple] = []  # 存储 (step_name, image_bytes)
        self.task_id: Optional[str] = None

        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)

    def start_task(self, task_id: Optional[str] = None) -> str:
        """
        开始一个新任务

        Args:
            task_id: 任务 ID，如果为 None 则自动生成

        Returns:
            任务 ID
        """
        if task_id is None:
            task_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.task_id = task_id
        self.screenshots = []

        # 创建任务目录
        task_dir = os.path.join(self.output_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)

        return task_id

    def add_screenshot(self, step_name: str, image_bytes: bytes) -> str:
        """
        添加一张截图

        Args:
            step_name: 步骤名称
            image_bytes: 图片字节数据

        Returns:
            保存的截图路径
        """
        if self.task_id is None:
            raise RuntimeError("请先调用 start_task() 开始任务")

        # 保存原始截图
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = step_name.replace(" ", "_").replace("/", "_")
        filename = f"{timestamp}_{safe_name}.png"
        filepath = os.path.join(self.output_dir, self.task_id, filename)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        # 添加到截图列表
        self.screenshots.append((step_name, image_bytes, filepath))

        return filepath

    def add_screenshot_from_base64(self, step_name: str, base64_data: str) -> str:
        """
        从 base64 数据添加截图

        Args:
            step_name: 步骤名称
            base64_data: base64 编码的图片数据

        Returns:
            保存的截图路径
        """
        # 移除可能的数据 URI 前缀
        if base64_data.startswith("data:image/"):
            base64_data = base64_data.split(",", 1)[1]

        image_bytes = base64.b64decode(base64_data)
        return self.add_screenshot(step_name, image_bytes)

    def get_screenshot_count(self) -> int:
        """获取当前截图数量"""
        return len(self.screenshots)

    def get_task_dir(self) -> str:
        """获取当前任务目录"""
        if self.task_id is None:
            raise RuntimeError("请先调用 start_task() 开始任务")
        return os.path.join(self.output_dir, self.task_id)

    def finish_task(self) -> Optional[str]:
        """
        完成任务，生成 GIF

        Returns:
            GIF 文件路径，如果未启用 GIF 则返回 None
        """
        if self.task_id is None:
            raise RuntimeError("请先调用 start_task() 开始任务")

        if not self.enable_gif or len(self.screenshots) == 0:
            return None

        try:
            from PIL import Image, ImageDraw, ImageFont

            # 创建带标注的图片列表
            images = []

            for step_name, image_bytes, _ in self.screenshots:
                # 打开图片
                img = Image.open(BytesIO(image_bytes))

                # 添加文字标注
                draw = ImageDraw.Draw(img)

                # 计算文字位置和大小
                img_width, img_height = img.size
                font_size = max(20, int(img_height / 30))

                # 尝试加载中文字体（按优先级）
                font = None
                font_paths = [
                    "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
                    "C:/Windows/Fonts/simhei.ttf",  # 黑体
                    "C:/Windows/Fonts/simsun.ttc",  # 宋体
                    "/System/Library/Fonts/PingFang.ttc",  # macOS
                    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux
                ]
                
                for font_path in font_paths:
                    try:
                        font = ImageFont.truetype(font_path, font_size)
                        break
                    except:
                        continue
                
                if font is None:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()

                # 计算文字背景框
                text_bbox = draw.textbbox((0, 0), step_name, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                # 绘制半透明背景
                padding = 10
                box_x = img_width - text_width - padding * 2 - 10
                box_y = 10
                draw.rectangle(
                    [box_x, box_y, box_x + text_width + padding * 2, box_y + text_height + padding * 2],
                    fill=(0, 0, 0, 180)
                )

                # 绘制文字
                draw.text(
                    (box_x + padding, box_y + padding),
                    step_name,
                    font=font,
                    fill=(255, 255, 255)
                )

                images.append(img)

            # 保存 GIF
            gif_path = os.path.join(self.output_dir, self.task_id, "task_animation.gif")
            
            print(f"🎬 正在生成 GIF...")
            print(f"   截图数量: {len(images)}")
            print(f"   保存路径: {os.path.abspath(gif_path)}")
            
            images[0].save(
                gif_path,
                save_all=True,
                append_images=images[1:],
                duration=self.gif_duration,
                loop=0
            )
            
            print(f"✓ GIF 已成功保存: {os.path.abspath(gif_path)}")

            return gif_path

        except ImportError:
            print("警告: 未安装 PIL/Pillow 库，无法生成 GIF")
            print("请运行: pip install pillow")
            return None
        except Exception as e:
            print(f"生成 GIF 时出错: {e}")
            return None

    def clear(self):
        """清空当前任务的所有截图"""
        self.screenshots = []
        self.task_id = None
