# -*- coding: utf-8 -*-
"""
backend.py - WaveNumberOCR 后端逻辑（EasyOCR 版）

负责：
- 根据屏幕坐标截取指定区域图像
- 调用 EasyOCR 识别文字（带简单图像预处理）
- 从识别结果中解析出 “第…波” 中间的波次数字（支持阿拉伯数字 + 中文数字）
- 提供读取单个屏幕像素颜色的工具方法
"""

from typing import Optional, Tuple, List
import re
import os
import time

import mss
from PIL import Image, ImageEnhance, ImageOps, ImageChops
import numpy as np
import easyocr


class ScreenCaptureError(Exception):
    """自定义异常：截屏相关错误。"""
    pass


class ScreenTextRecognizer:
    """
    屏幕文字识别器：
    - 截取屏幕指定区域
    - OCR 识别
    - 解析 “第X波” 中的 X（阿拉伯数字 / 中文）
    - 读取任意屏幕像素的 RGB 颜色
    """

    def __init__(
        self,
        languages: Optional[List[str]] = None,
        gpu: bool = False,
        debug: bool = False,
    ) -> None:
        """
        :param languages: OCR 语言列表，默认 ['ch_sim', 'en']（简体中文 + 英文）
        :param gpu: 是否使用 GPU，默认 False
        :param debug: 是否输出调试信息（打印 EasyOCR 原始结果等）
        """
        if languages is None:
            languages = ["ch_sim", "en"]

        # easyocr 的初始化比较耗时，整个应用只创建一个 reader 实例
        self.reader = easyocr.Reader(languages, gpu=gpu)
        self.debug = debug

    # ------------ 截屏相关 ------------

    @staticmethod
    def normalize_box(x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int, int]:
        """
        将任意两个对角坐标标准化为 (left, top, right, bottom).
        """
        left = int(min(x1, x2))
        top = int(min(y1, y2))
        right = int(max(x1, x2))
        bottom = int(max(y1, y2))
        return left, top, right, bottom

    def capture_region(self, x1: int, y1: int, x2: int, y2: int) -> Image.Image:
        """
        截取屏幕指定区域并返回为 PIL Image 对象。

        :raises ScreenCaptureError: 坐标不合法或截屏失败时抛出。
        """
        left, top, right, bottom = self.normalize_box(x1, y1, x2, y2)
        width = right - left
        height = bottom - top

        if width <= 0 or height <= 0:
            raise ScreenCaptureError(
                f"截屏区域宽高必须为正数，目前 width={width}, height={height}"
            )

        try:
            with mss.mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                sct_img = sct.grab(monitor)
        except Exception as exc:  # pylint: disable=broad-except
            raise ScreenCaptureError(f"执行截屏时出现错误: {exc}") from exc

        img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
        return img

    # ------------ 图像预处理 + OCR ------------

    @staticmethod
    def _preprocess_for_ocr(image: Image.Image) -> Image.Image:
        """
        针对游戏 UI 做一些简单预处理，提升 OCR 成功率：
        - 放大 2~3 倍
        - 自动对比度
        - 略微增强对比度和亮度
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        w, h = image.size
        # 选区一般不算太大，可以适当放大
        if w < 400:
            scale = 3
        else:
            scale = 2
        image = image.resize((w * scale, h * scale), Image.BICUBIC)

        # 自动对比度 + 提升对比度 / 亮度
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.6)
        image = ImageEnhance.Brightness(image).enhance(1.1)

        return image

    def ocr_text(self, image: Image.Image) -> str:
        """
        对图像执行 OCR，返回识别出的长文本。
        """
        image = self._preprocess_for_ocr(image)
        np_img = np.array(image)

        # detail=0 只返回文字列表；paragraph=True 尝试合并成段落
        results = self.reader.readtext(np_img, detail=0, paragraph=True)

        if self.debug:
            print("=== [DEBUG] EasyOCR 识别结果列表 ===")
            for idx, txt in enumerate(results):
                print(f"  [{idx}] {repr(txt)}")
            print("=== [DEBUG] =======================")

        text = "\n".join(results)
        if self.debug:
            print("=== [DEBUG] 拼接后的文本 ===")
            print(text)
            print("=== [DEBUG END] ===")

        return text

    # ------------ 文本解析：从 OCR 文本中提取波次 ------------

    @staticmethod
    def _normalize_common_misread(text: str) -> str:
        """
        处理一些 OCR 常见误识别：
        - 把 I / l / | 视作数字 1
        """
        replacements = {
            "I": "1",
            "l": "1",
            "|": "1",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    @staticmethod
    def _chinese_numeral_to_int(s: str) -> Optional[int]:
        """
        将简单的中文数字（零一二三四五六七八九十两）转换成整数。
        只覆盖波次数常见范围（1~99）即可。
        """
        s = s.replace("两", "二")  # “两”按 2 处理

        digits = {
            "零": 0,
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
        }

        if not s:
            return None

        # 纯数字型，如 “二三” -> 23
        if all(ch in digits for ch in s):
            return int("".join(str(digits[ch]) for ch in s))

        # 含“十”的情况
        if "十" in s:
            parts = s.split("十")
            # “十” -> 10
            if len(parts) == 2 and parts[0] == "" and parts[1] == "":
                return 10

            # “十X” -> 10 + X
            if parts[0] == "":
                tens = 1
            else:
                if parts[0] not in digits:
                    return None
                tens = digits[parts[0]]

            ones = 0
            if len(parts) > 1 and parts[1]:
                if parts[1] not in digits:
                    return None
                ones = digits[parts[1]]

            return tens * 10 + ones

        return None

    @classmethod
    def parse_wave_number(cls, text: str) -> Optional[str]:
        """
        从文本中解析 “第X波”，返回 X（阿拉伯数字字符串）。
        若未找到则返回 None。
        """
        # 先做一次常见误识别归一化
        normalized = cls._normalize_common_misread(text)

        # 1. 优先匹配阿拉伯数字形式：第 1 波
        pattern_digit = re.compile(r"第\s*([0-9]{1,4})\s*波", re.DOTALL)
        match = pattern_digit.search(normalized)
        if match:
            return match.group(1)

        # 2. 兼容中文数字形式：第一波、第十二波 等
        pattern_cn = re.compile(r"第\s*([零一二三四五六七八九十两]+)\s*波", re.DOTALL)
        match = pattern_cn.search(text)
        if match:
            num = cls._chinese_numeral_to_int(match.group(1))
            if num is not None:
                return str(num)

        # 3. 宽松一点的回退规则：
        #    例如 OCR 把 “波” 识别成 “坡”等
        pattern_loose = re.compile(r"[第弟]\s*([0-9]{1,4})\s*[波坡]", re.DOTALL)
        match = pattern_loose.search(normalized)
        if match:
            return match.group(1)

        return None

    # ------------ 高层封装 ------------

    def capture_and_recognize(self, x1: int, y1: int, x2: int, y2: int) -> Optional[str]:
        """
        综合方法：截屏并识别 “第X波”，返回 X 或 None。
        """
        img = self.capture_region(x1, y1, x2, y2)
        text = self.ocr_text(img)
        number = self.parse_wave_number(text)
        return number

    def get_pixel_color(self, x: int, y: int) -> Tuple[int, int, int]:
        """
        读取屏幕上单个像素的颜色。

        :param x: 像素的 X 坐标（屏幕像素）
        :param y: 像素的 Y 坐标（屏幕像素）
        :return: (R, G, B)
        :raises ScreenCaptureError: 截屏失败时抛出
        """
        # 截取一个 1x1 的小区域即可
        img = self.capture_region(x, y, x + 1, y + 1)
        r, g, b = img.getpixel((0, 0))
        return int(r), int(g), int(b)

    # ------------ 颜色过滤并保存图片 ------------

    @staticmethod
    def _build_color_mask_image(
        region_img: Image.Image, target_color: Tuple[int, int, int]
    ) -> Image.Image:
        """
        从区域图像中只保留与目标 RGB 完全一致的像素，其他像素全部变为透明。
        返回带 Alpha 通道的 RGBA 图像。
        """
        if region_img.mode != "RGBA":
            region_img = region_img.convert("RGBA")

        arr = np.array(region_img)
        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]

        tr, tg, tb = target_color
        mask = (r == tr) & (g == tg) & (b == tb)

        # 所有像素先置为全透明，再把匹配的像素设为不透明
        arr[:, :, 3] = 0
        arr[mask, 3] = 255

        # 非匹配像素 RGB 也清零，避免残留颜色
        arr[~mask, 0] = 0
        arr[~mask, 1] = 0
        arr[~mask, 2] = 0

        return Image.fromarray(arr, "RGBA")

    @staticmethod
    def _is_same_image(img1: Image.Image, img2: Image.Image) -> bool:
        """
        判断两张图片内容是否完全一致（尺寸、模式一致且逐像素相同）。
        """
        if img1.size != img2.size:
            return False

        if img1.mode != img2.mode:
            img2 = img2.convert(img1.mode)

        diff = ImageChops.difference(img1, img2)
        # 如果没有任何非零像素，getbbox() 返回 None，说明完全一致
        return diff.getbbox() is None

    def _image_already_exists(self, candidate: Image.Image, directory: str) -> bool:
        """
        在指定目录中查找是否已有与 candidate 像素内容完全一致的图片。
        """
        exts = (".png", ".jpg", ".jpeg")

        try:
            file_names = os.listdir(directory)
        except OSError:
            return False

        candidate_rgba = candidate.convert("RGBA")

        for name in file_names:
            if not name.lower().endswith(exts):
                continue
            path = os.path.join(directory, name)
            try:
                with Image.open(path) as existing:
                    existing_rgba = existing.convert("RGBA")
                    if self._is_same_image(candidate_rgba, existing_rgba):
                        return True
            except Exception:
                # 忽略无法打开的文件
                continue

        return False

    def save_region_color_mask(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color_x: int,
        color_y: int,
        save_dir: Optional[str] = None,
    ) -> Optional[str]:
        """
        截取指定区域，获取指定屏幕坐标的像素颜色，在区域内只保留与该颜色完全一致的像素，
        其他像素全部变为透明，并将结果图片以当前时间戳命名保存。

        :param x1: 选区左上或右下 X 坐标（屏幕像素）
        :param y1: 选区左上或右下 Y 坐标（屏幕像素）
        :param x2: 选区左上或右下 X 坐标（屏幕像素）
        :param y2: 选区左上或右下 Y 坐标（屏幕像素）
        :param color_x: 用于取样颜色的屏幕 X 坐标
        :param color_y: 用于取样颜色的屏幕 Y 坐标
        :param save_dir: 图片保存目录；为 None 时使用当前工作目录
        :return: 实际保存的文件路径；如果检测到完全相同的图片已存在，则返回 None
        :raises ScreenCaptureError: 截图失败时抛出
        """
        # 截取目标区域
        region_img = self.capture_region(x1, y1, x2, y2)
        # 读取指定坐标的目标颜色
        target_color = self.get_pixel_color(color_x, color_y)

        # 构造只保留目标颜色的透明图
        mask_img = self._build_color_mask_image(region_img, target_color)

        # 确定保存目录
        if save_dir is None:
            save_dir = os.getcwd()
        else:
            os.makedirs(save_dir, exist_ok=True)

        # 检查是否已有内容完全一致的图片
        if self._image_already_exists(mask_img, save_dir):
            return None

        # 以时间戳命名文件，例如 1764495345.png
        timestamp = str(int(time.time()))
        filename = f"{timestamp}.png"
        save_path = os.path.join(save_dir, filename)

        mask_img.save(save_path)
        return save_path
