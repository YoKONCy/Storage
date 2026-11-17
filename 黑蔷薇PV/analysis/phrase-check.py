# -*- coding: utf-8 -*-
"""
phrase-check.py —— 46-107s 中层织体事件声学核查（人耳六点的精确帧校准）
=====================================================================
不做全曲细时间戳，只回答主人六个时间段里「画面该跟什么」：
  47.5-51.5  钢琴琶音高频 onset（红光呼吸次数/时刻）
  54-63      塔段织体（军鼓 rimshot、人声八度爬升的能量变化）
  67-72.7    build-up：低频鼓点列（玫瑰阶梯放大用）+ 真空急停的精确谷底
  72.68-85.8 副歌低鼓网格、81.46 前后中频能量台阶（唱诗班铺底）
  85.8-107.3 落底冲击、长音/吉他 solo 的高频持续能量、结尾悬置抽空
产物：
  analysis/phrase-map.png  多轨包络图（歌词行 + 人耳六点标注）
  控制台打印精确到 0.001s / 30fps 帧号的事件表
"""
import os
import numpy as np
import librosa
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 中文字体（Windows 自带雅黑/黑体），避免方块
for _f in ("Microsoft YaHei", "SimHei", "SimSun"):
    try:
        plt.rcParams["font.sans-serif"] = [_f]
        break
    except Exception:
        continue
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUDIO = os.path.join(ROOT, "assets", "audio", "黒薔薇の祈り.mp3")
OUT_PNG = os.path.join(HERE, "phrase-map.png")

SR = 22050
FPS = 50
HOP = int(round(SR / FPS))
VIDEO_FPS = 30

# 核查窗口（留边）
T0, T1 = 46.0, 107.3

# 歌词行（这一段）
LINES = [
    (46.11, "名前 封じて"),
    (51.22, "リボン 棺に結ぶ"),
    (53.93, "鐘のない塔に"),
    (63.51, "凍る誓いを"),
    (68.37, "咲いて 黒薔薇よ"),
    (72.68, "胸の檻を 砕いて"),
    (81.46, "最後の祈り"),
    (85.77, "滅びの庭で 歌う"),
]
# 主人人耳六点（估计值，待声学核实）
HUMAN = [
    (48.0, 51.0, "①琶音红光呼吸"),
    (54.0, 63.0, "②塔下缓推"),
    (67.0, 72.4, "③build-up玫瑰+A6b"),
    (72.0, 85.8, "④红色浸染"),
    (86.0, 90.0, "⑤艰难睁眼"),
    (90.0, 107.3, "⑥眼皮呼吸+虚影"),
]


def band_rms(y, f_lo, f_hi):
    n_fft = 2048
    stft = librosa.stft(y, n_fft=n_fft, hop_length=HOP)
    mag = np.abs(stft)
    freqs = librosa.fft_frequencies(sr=SR, n_fft=n_fft)
    mask = (freqs >= f_lo) & (freqs < f_hi)
    e = np.sum(mag[mask, :] ** 2, axis=0)
    return np.sqrt(e / max(mask.sum(), 1))


def p95(x):
    x = np.asarray(x, dtype=np.float64)
    ref = np.percentile(x[x > 0], 95) if np.any(x > 0) else 1.0
    return np.clip(x / ref, 0, 1.15)


def frame(t):
    """全局秒 -> 30fps 帧号。"""
    return int(round(t * VIDEO_FPS))


def list_onsets(onsets, a, b, band=None, min_s=0.0):
    out = []
    for t, s, bn in onsets:
        if a <= t <= b and s >= min_s and (band is None or bn == band):
            out.append((t, s, bn))
    return out


def main():
    print(f"读取音频 {AUDIO}")
    y, _ = librosa.load(AUDIO, sr=SR, mono=True)
    f0 = int(T0 * FPS)
    f1 = int(T1 * FPS)

    low = p95(band_rms(y, 20, 150))[f0:f1]
    mid = p95(band_rms(y, 150, 2000))[f0:f1]
    high = p95(band_rms(y, 2000, 11000))[f0:f1]
    rms = p95(librosa.feature.rms(y=y, hop_length=HOP, frame_length=2048)[0])[f0:f1]
    tt = np.arange(len(rms)) / FPS + T0

    onset_env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    of = librosa.onset.onset_detect(
        y=y, sr=SR, hop_length=HOP, onset_envelope=onset_env,
        pre_max=3, post_max=6, pre_avg=3, post_avg=5, delta=0.07, wait=6)
    ref = np.percentile(onset_env[of], 95) or 1.0
    onsets = []
    for fr in of:
        t = float(librosa.frames_to_time(fr, sr=SR, hop_length=HOP))
        if not (T0 <= t <= T1):
            continue
        s = float(np.clip(onset_env[fr] / ref, 0, 1.15))
        if s < 0.18:
            continue
        a, b = max(0, fr - 2), min(len(rms) + f0, fr + 4)
        bn = int(np.argmax([np.mean(low[a - f0:b - f0]) if b - f0 <= len(low) else 0,
                            np.mean(mid[a - f0:b - f0]) if b - f0 <= len(mid) else 0,
                            np.mean(high[a - f0:b - f0]) if b - f0 <= len(high) else 0]))
        onsets.append((t, s, bn))

    print("=" * 64)
    print("① 47.5-51.5 高频 onset（钢琴琶音候选，红光呼吸点）")
    for t, s, bn in list_onsets(onsets, 47.4, 51.6, band=2, min_s=.15):
        print(f"   t={t:6.3f}s  帧{frame(t):4d}  强度{s:.2f}")

    print("② 53.9-63.6 全部 onset（军鼓/人声事件参考）")
    for t, s, bn in list_onsets(onsets, 53.9, 63.6, min_s=.25):
        print(f"   t={t:6.3f}s  帧{frame(t):4d}  强度{s:.2f}  带{['低','中','高'][bn]}")

    print("③ 66.8-72.7 低频 onset（build-up 鼓点，玫瑰阶梯跟随）")
    boom = list_onsets(onsets, 66.8, 72.7, min_s=.2)
    for t, s, bn in boom:
        tag = "低鼓" if bn == 0 else ["", "中", "高"][bn]
        print(f"   t={t:6.3f}s  帧{frame(t):4d}  强度{s:.2f}  {tag}")

    # 真空谷底：71.5-72.8 内 rms 最低且持续的位置
    seg = rms[(tt >= 71.5) & (tt <= 72.8)]
    segt = tt[(tt >= 71.5) & (tt <= 72.8)]
    gap_i = int(np.argmin(seg))
    print(f"   真空谷底（rms 最低）≈ t={segt[gap_i]:.3f}s  帧{frame(segt[gap_i])}  rms={seg[gap_i]:.2f}")

    print("④ 72.68-85.8 低频 onset（浸染段参考，只列强度>.45）")
    for t, s, bn in list_onsets(onsets, 72.68, 85.8, min_s=.45):
        print(f"   t={t:6.3f}s  帧{frame(t):4d}  强度{s:.2f}  带{['低','中','高'][bn]}")

    # 唱诗班：80.5-81.4 vs 81.5-83.0 中频能量均值台阶
    m_before = np.mean(mid[(tt >= 80.5) & (tt < 81.4)])
    m_choir = np.mean(mid[(tt >= 81.5) & (tt <= 83.2)])
    print(f"   唱诗班台阶：81.4 前 mid 均值 {m_before:.2f} → 81.5-83.2 {m_choir:.2f}（×{m_choir / max(m_before, 1e-6):.2f}）")

    print("⑤ 85.4-86.2 最强 onset（落底冲击精确定位）")
    for t, s, bn in list_onsets(onsets, 85.4, 86.2, min_s=.3):
        print(f"   t={t:6.3f}s  帧{frame(t):4d}  强度{s:.2f}  带{['低','中','高'][bn]}")

    print("⑥ 86-107 段落能量曲线关键值（眨眼/虚影段）")
    for a, b, name in [(86.0, 90.0, "睁眼段"),
                       (90.0, 98.3, "眼皮呼吸段"),
                       (98.3, 103.0, "吉他solo/视角漂移"),
                       (103.0, 105.2, "solo 尾"),
                       (105.2, 107.3, "悬置收尾")]:
        r = np.mean(rms[(tt >= a) & (tt < b)])
        h = np.mean(high[(tt >= a) & (tt < b)])
        print(f"   {name:12s} {a:6.1f}-{b:6.1f}  rms均值{r:.2f}  高频均值{h:.2f}")
    # 结尾悬置抽空点：103-107.3 rms 最后一次骤降
    tail_r = rms[(tt >= 103.0)]
    tail_t = tt[(tt >= 103.0)]
    if len(tail_r) > 4:
        d = np.diff(tail_r)
        dip = int(np.argmin(d))
        print(f"   结尾能量骤降点 ≈ t={tail_t[dip]:.3f}s  帧{frame(tail_t[dip])}")

    # ---------- 出图 ----------
    fig, axes = plt.subplots(5, 1, figsize=(20, 11), sharex=True)
    bands = [(rms, "rms 总响度", "#cfd6e6"),
             (low, "low 低鼓", "#e05a5a"),
             (mid, "mid 人声/织体", "#8ac06a"),
             (high, "high 镲/琶音/弦", "#5aa0e0")]
    for ax, (curve, name, color) in zip(axes, bands):
        ax.fill_between(tt, 0, curve, color=color, alpha=.55, lw=0)
        ax.set_ylabel(name, fontsize=11)
        ax.set_ylim(0, 1.2)
        ax.grid(alpha=.18)
        # 歌词行
        for lt, txt in LINES:
            ax.axvline(lt, color="#888", lw=.8, ls="--", alpha=.6)
        # 人耳六点色带
        for a, b, _ in HUMAN:
            ax.axvspan(a, b, color="#e0b040", alpha=.05)
    # 第五轨：onsets 火柴棍
    ax = axes[4]
    colors = {0: "#e05a5a", 1: "#8ac06a", 2: "#5aa0e0"}
    for t, s, bn in onsets:
        ax.vlines(t, 0, s, color=colors[bn], lw=1.1, alpha=.8)
    ax.set_ylabel("onsets", fontsize=11)
    ax.set_ylim(0, 1.2)
    ax.grid(alpha=.18)
    for lt, txt in LINES:
        ax.axvline(lt, color="#888", lw=.8, ls="--", alpha=.6)
        ax.text(lt + .04, 1.12, txt, rotation=0, fontsize=8, color="#bbb")
    for a, b, name in HUMAN:
        ax.axvspan(a, b, color="#e0b040", alpha=.07)
        ax.text((a + b) / 2, .92, name, ha="center", fontsize=8.5, color="#e0b040")
    axes[0].set_xlim(T0, T1)
    axes[0].set_xticks(np.arange(46, 108, 1))
    axes[-1].set_xlabel("时间 (s)")
    fig.suptitle("Phrase check 46-107s — 灰线=歌词行 / 黄带=人耳六点", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, .98])
    fig.savefig(OUT_PNG, dpi=110)
    print(f"图已保存：{OUT_PNG}")


if __name__ == "__main__":
    main()
