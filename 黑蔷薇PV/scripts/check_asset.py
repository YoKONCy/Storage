# -*- coding: utf-8 -*-
"""
素材进门验收工具（hyperframes-pv-shot 技能 四之三 门禁）
用法：
    python scripts/check_asset.py 文件1.png 文件2.png ...
检查：mode / 尺寸 / alpha 范围 / 四角与边缘采样 / 白底或棋盘格假透明。
透底素材要求 RGBA 且四角 alpha 多数为 0；场景图不做透底要求。
"""
import sys
from PIL import Image


def check(path):
    im = Image.open(path)
    w, h = im.size
    mode = im.mode
    rgba = im.convert("RGBA")
    px = rgba.load()

    # 四角 + 四边中点
    pts = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3),
           (w // 2, 2), (w // 2, h - 3), (2, h // 2), (w - 3, h // 2)]
    samples = [px[x, y] for x, y in pts]
    a_vals = [c[3] for c in samples]
    rgb4 = [(c[0], c[1], c[2]) for c in samples[:4]]
    amin, amax = rgba.getchannel("A").getextrema()

    if mode != "RGBA" or amin == 255:
        grays = [sum(c[:3]) // 3 for c in samples]
        # 棋盘格：同批采样点灰白交替且跨度大；纯白底：四角都接近 255
        if min(grays) > 244:
            verdict = "拒收：纯白底无alpha（假透明）"
        elif max(grays) - min(grays) > 60:
            verdict = "拒收：疑似棋盘格假透明"
        else:
            verdict = "无alpha（仅适合场景/非透底图）"
    elif sum(1 for a in a_vals if a < 16) >= 6:
        verdict = "通过：真alpha，边缘干净"
    else:
        verdict = "存疑：RGBA但边缘alpha不为0（可能有白边/残底）"

    print(f"[{path}]")
    print(f"   {w}x{h} mode={mode} alpha=({amin},{amax}) => {verdict}")
    print(f"   四角RGB={rgb4} 采样alpha={a_vals}")
    return verdict.startswith("通过") or verdict.startswith("无alpha")


if __name__ == "__main__":
    ok = True
    for p in sys.argv[1:]:
        ok = check(p) and ok
    sys.exit(0 if ok else 1)
