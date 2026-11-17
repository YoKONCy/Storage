# -*- coding: utf-8 -*-
"""
透底素材双底抽检（技能 四之三 门禁第3条）：
把每张透底图分别合成到纯黑底 / 暗红底，拼成一张对比图，
供肉眼检查发丝蕾丝赤足白边、主体破洞。
用法：python scripts/qa_dualbg.py 输出图.png 素材1.png 素材2.png ...
"""
import sys
from PIL import Image

DARK_RED = (38, 6, 10, 255)
CELL = 760   # 每张单底缩略图长边


def fit(im, long_side):
    w, h = im.size
    s = long_side / max(w, h)
    return im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)


def composite_on(rgba, bg_color):
    bg = Image.new("RGBA", rgba.size, bg_color)
    return Image.alpha_composite(bg, rgba)


def main(out, paths):
    rows = []
    for p in paths:
        im = Image.open(p).convert("RGBA")
        on_black = fit(composite_on(im, (0, 0, 0, 255)), CELL)
        on_red = fit(composite_on(im, DARK_RED), CELL)
        row = Image.new("RGBA", (CELL * 2 + 20, CELL + 10), (20, 20, 22, 255))
        row.paste(on_black, (0, 5))
        row.paste(on_red, (CELL + 20, 5))
        rows.append(row)
    W = CELL * 2 + 20
    H = sum(r.size[1] for r in rows)
    sheet = Image.new("RGBA", (W, H), (20, 20, 22, 255))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.size[1]
    sheet.convert("RGB").save(out)
    print("saved:", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
