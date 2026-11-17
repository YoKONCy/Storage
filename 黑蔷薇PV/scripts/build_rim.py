# -*- coding: utf-8 -*-
"""
build_rim.py — 为真 alpha 素材烘焙方向性 rim 光贴图（全片剪影语言的基础设施）

输入：assets/images/*.png（必须是真 RGBA 抠图）
输出：assets/rim/<名>-rimL.png / <名>-rimR.png
      冷白色 (214,228,255) 光带，alpha 通道储存强度：
        rimL = 左侧受光（轮廓的左缘），rimR = 右侧受光
      轮廓带 = alpha 内边缘（实体表面一侧）+ 外扩辉光（分离黑底用）

用法：python scripts/build_rim.py
新增素材后重跑即可，确定性输出。
"""
import os
import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "assets", "images")
OUT_DIR = os.path.join(ROOT, "assets", "rim")

# 无 alpha 的氛围/场景图不做剪影演员，不参与 rim 烘焙
SKIP = {
    "style-keyvisual.png",   # R0 画风基准/Intro 临时世界层
    "church-interior.png",   # S8 教堂内景
    "tower.png",             # S2 无钟之塔
    "garden.png",            # S5 毁灭之庭
}

RIM_RGB = (214, 228, 255)  # 冷白偏蓝，后续由全局染色层改色温

def dilate(a, passes):
    """二值/软 alpha 的膨胀：重复 3x3 MaxFilter"""
    out = a
    for _ in range(passes):
        out = out.filter(ImageFilter.MaxFilter(3))
    return out

def erode(a, passes):
    out = a
    for _ in range(passes):
        out = out.filter(ImageFilter.MinFilter(3))
    return out

def soft_mask_from_grad(grad, sign, dilate_passes):
    """从 alpha 梯度提取朝某方向的轮廓软掩码，再膨胀成带状"""
    if sign > 0:
        m = np.clip(grad, 0, 1)      # 向右进入实体 → 左缘（左侧受光）
    else:
        m = np.clip(-grad, 0, 1)     # 向右离开实体 → 右缘（右侧受光）
    m_img = Image.fromarray((m * 255).astype(np.uint8), "L")
    m_img = dilate(m_img, dilate_passes)
    return np.array(m_img).astype(np.float32) / 255.0

def build_one(path):
    im = Image.open(path).convert("RGBA")
    a = im.getchannel("A")
    arr = np.array(a).astype(np.float32) / 255.0
    if arr.min() > 0.99:
        print(f"  跳过（无透明区域，疑似假透明）：{os.path.basename(path)}")
        return

    # 外扩辉光半径略大，内边缘半径小而实
    dil = np.array(dilate(a, 5)).astype(np.float32) / 255.0
    ero = np.array(erode(a, 3)).astype(np.float32) / 255.0
    outer = np.clip(dil - arr, 0, 1)
    inner = np.clip(arr - ero, 0, 1)
    band = np.maximum(inner, outer * 0.65)

    # 方向掩码：水平梯度定位左右缘，竖直轮廓（头顶/肩线）按 35% 分给两侧
    # 侧逆光会扫到这些横向边界
    gx = np.zeros_like(arr)
    gx[:, 1:-1] = arr[:, 2:] - arr[:, :-2]
    gy = np.zeros_like(arr)
    gy[1:-1, :] = arr[2:, :] - arr[:-2, :]
    wL = soft_mask_from_grad(gx, +1, 4)
    wR = soft_mask_from_grad(gx, -1, 4)
    wY = soft_mask_from_grad(gy, +1, 3) + soft_mask_from_grad(gy, -1, 3)
    wY = np.clip(wY, 0, 1) * 0.35
    wL = np.clip(wL + wY, 0, 1)
    wR = np.clip(wR + wY, 0, 1)

    h, w = arr.shape
    rgb = np.zeros((h, w, 4), dtype=np.uint8)
    rgb[..., 0] = RIM_RGB[0]
    rgb[..., 1] = RIM_RGB[1]
    rgb[..., 2] = RIM_RGB[2]

    name = os.path.splitext(os.path.basename(path))[0]
    for side, wm in (("L", wL), ("R", wR)):
        alpha = np.clip(band * np.maximum(wm, 0.15 * (band > 0)), 0, 1)
        rgb[..., 3] = (alpha * 255).astype(np.uint8)
        out = Image.fromarray(rgb, "RGBA")
        out_path = os.path.join(OUT_DIR, f"{name}-rim{side}.png")
        out.save(out_path)
    print(f"  ok: {name} -> {name}-rimL.png / {name}-rimR.png")

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(f for f in os.listdir(SRC_DIR)
                   if f.lower().endswith(".png") and f not in SKIP)
    print(f"发现 {len(files)} 张候选素材")
    for f in files:
        build_one(os.path.join(SRC_DIR, f))
    print("rim 烘焙完成 →", os.path.relpath(OUT_DIR, ROOT))

if __name__ == "__main__":
    main()
