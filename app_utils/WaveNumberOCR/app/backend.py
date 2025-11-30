# -*- coding: utf-8 -*-
"""
backend.py - WaveNumberOCR 后端逻辑（EasyOCR 版）

负责：
- 根据屏幕坐标截取指定区域图像
- 调用 EasyOCR 识别文字（带图像预处理）
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
    - 解析 “第X波”，返回中间数字
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
        针对游戏中“黄字黑底”的关卡提示文本做预处理，提升 OCR 成功率：

        1. 放大 2~3 倍；
        2. 根据日志中观察到的颜色 RGB(255, 214, 36) 做 “近似黄色” 颜色提取，
           把接近该颜色的像素变成白色，其他像素变成黑色，得到黑底白字二值图；
        3. 自动对比度。

        这样可以尽量把背景噪声去掉，只保留文字形状。
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

        arr = np.array(image).astype("int16")
        r = arr[:, :, 0]
        g = arr[:, :, 1]
        b = arr[:, :, 2]

        # 目标颜色：从你的调试日志中看到像素颜色约为 RGB(255, 214, 36)
        tr, tg, tb = 255, 214, 36

        # 计算每个像素与目标颜色的“距离”（L1 距离）
        diff = np.abs(r - tr) + np.abs(g - tg) + np.abs(b - tb)

        # 阈值适当放松一点以兼容抗锯齿/压缩带来的轻微色差
        mask = diff < 80

        # 如果 mask 几乎全黑或几乎全白，说明颜色提取不靠谱，退回到通用预处理
        ratio = mask.mean() if mask.size > 0 else 0.0
        if ratio < 0.0005 or ratio > 0.5:
            # 通用方案：自动对比度 + 提升对比度 / 亮度
            image = ImageOps.autocontrast(image)
            image = ImageEnhance.Contrast(image).enhance(1.6)
            image = ImageEnhance.Brightness(image).enhance(1.1)
            return image

        # 二值化：黄字位置为白色，其余黑色
        binary = np.zeros_like(r, dtype="uint8")
        binary[mask] = 255

        img = Image.fromarray(binary, "L")
        img = ImageOps.autocontrast(img)

        return img

    def ocr_text(self, image: Image.Image) -> str:
        """
        对图像执行 OCR，返回识别出的长文本。
        """
        image = self._preprocess_for_ocr(image)
        np_img = np.array(image)

        # 限制识别字符范围，强行收缩到“第/波 + 数字/中文数字”
        allowlist = "第弟波坡0123456789零一二三四五六七八九十两 　"

        try:
            results = self.reader.readtext(
                np_img,
                detail=0,
                paragraph=True,
                allowlist=allowlist,
            )
        except TypeError:
            # 兼容旧版本 easyocr（没有 allowlist 参数）
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
        - 把 O / o / 〇 视作数字 0
        """
        replacements = {
            "I": "1",
            "l": "1",
            "|": "1",
            "O": "0",
            "o": "0",
            "〇": "0",
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
        pattern_digit = re.compile(r"[第弟]\s*([0-9]{1,4})\s*[波坡]", re.DOTALL)
        match = pattern_digit.search(normalized)
        if match:
            return match.group(1)

        # 2. 兼容中文数字形式：第一波、第十二波 等
        pattern_cn = re.compile(r"[第弟]\s*([零一二三四五六七八九十两]+)\s*[波坡]", re.DOTALL)
        match = pattern_cn.search(text)
        if match:
            num = cls._chinese_numeral_to_int(match.group(1))
            if num is not None:
                return str(num)

        return None

    # ------------ 备用：只识别中间数字区域 ------------

    def _recognize_center_digits(self, image: Image.Image) -> Optional[str]:
        """
        兜底方案：
        - 只截取整体图片中间 40% 宽度的区域（基本只包含数字，不包含“第”和“波”）；
        - 只允许识别 0~9；
        - 把识别到的所有数字拼接成一个字符串作为波次。

        当 parse_wave_number 解析失败时会调用本方法。
        """
        w, h = image.size
        if w <= 0 or h <= 0:
            return None

        left = int(w * 0.3)
        right = int(w * 0.7)
        if right <= left:
            return None

        center_img = image.crop((left, 0, right, h))
        center_img = self._preprocess_for_ocr(center_img)
        np_img = np.array(center_img)

        try:
            results = self.reader.readtext(
                np_img,
                detail=0,
                paragraph=True,
                allowlist="0123456789",
            )
        except TypeError:
            results = self.reader.readtext(np_img, detail=0, paragraph=True)

        if self.debug:
            print("=== [DEBUG] 中央数字区域 OCR 结果 ===")
            for idx, txt in enumerate(results):
                print(f"  [C{idx}] {repr(txt)}")
            print("=== [DEBUG] 中央数字区域 END ===")

        text = "".join(results)
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits or None

    # ------------ 高层封装 ------------

    def capture_and_recognize(self, x1: int, y1: int, x2: int, y2: int) -> Optional[str]:
        """
        综合方法：截屏并识别 “第X波”，返回 X 或 None。
        """
        img = self.capture_region(x1, y1, x2, y2)
        text = self.ocr_text(img)
        number = self.parse_wave_number(text)

        if number is None:
            # 若常规解析失败，再试一次“只识别中间数字”的兜底逻辑
            if self.debug:
                print("=== [DEBUG] 常规解析失败，尝试仅识别中间数字区域 ===")
            number = self._recognize_center_digits(img)

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
        在指定目录中查找是否已有与 candidate 像素内容是否完全一致的图片。
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
        :param save_dir: 图片保存目录；为 None 时使用当前工作目录下的 'color_mask_exports' 子目录
        :return: 实际保存的文件路径；如果检测到完全相同的图片已存在，则返回 None
        :raises ScreenCaptureError: 截图失败时抛出
        """
        # 截取目标区域
        region_img = self.capture_region(x1, y1, x2, y2)
        # 读取指定坐标的目标颜色
        target_color = self.get_pixel_color(color_x, color_y)

        # 构造只保留目标颜色的透明图
        mask_img = self._build_color_mask_image(region_img, target_color)

        # 确定保存目录：若未指定，则使用当前工作目录下的 'color_mask_exports' 子目录
        if save_dir is None:
            save_dir = os.path.join(os.getcwd(), "color_mask_exports")
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
