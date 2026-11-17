# -*- coding: utf-8 -*-
"""
onsets.py —— 《黒薔薇の祈り》PV 镜头内「有机反应层」的音频事件分析
=====================================================================
为什么需要它（对照 pdoom-video 的三层时间结构）：
  粗层 切点   ：analysis/song.json 的句级时间戳 + 段落边界（不动）
  中层 巧思   ：每个镜头手工微事件表（如锁链段 拖入→绷紧→断→抽离）
  细层 乐器点 ：本脚本产物 analysis/events.json —— 真实音频分析出的
               onset（起音）+ 分频带 RMS 包络，让画面能「呼吸在音乐里」：
               rim 光随人声呼吸、断金裂石般的低频冲击微震、
               浮尘/雨雾密度跟频段能量走……这些不需要任何新素材。

设计原则：
  1. 不碰词级对齐（那是粗层的事，LLM 猜的细时间戳是假精度）；
  2. 不分轨（Demucs 要下 4GB 模型）；改用分频带能量给 onset 归属 low/mid/high；
  3. 输出 seek 安全的纯数据：离散事件表 + 固定帧率包络曲线，
     JS 侧读数据是时间的纯函数，逐帧 seek 渲染可复现；
  4. 所有曲线按全曲 P95 归一，避免个别峰值把动态压扁。

用法：
  python analysis/onsets.py
产物：
  analysis/events.json
"""

import json
import os
import numpy as np
import librosa

# —— 路径（脚本在 PV/analysis/ 下，音频在 PV/assets/audio/ 下）——
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AUDIO = os.path.join(ROOT, "assets", "audio", "黒薔薇の祈り.mp3")
BEATS_JSON = os.path.join(ROOT, "beats", "assets", "audio", "黒薔薇の祈り.mp3.json")
OUT_JSON = os.path.join(HERE, "events.json")

SR = 22050                 # 分析采样率（交响金属 11kHz 上限足够拿冲击与包络）
ENV_FPS = 50               # 包络曲线帧率（20ms/格，镜头内插值读取，体积与精度平衡）

# 频带划分（Hz）：对应哥特/交响金属里画面可反应的声源
BANDS = {
    "low":   (20,    150),     # kick / 贝斯/定音鼓：冲击、震屏、链节猛颤
    "mid":   (150,  2000),     # snare / 人声基频与大部分织体：rim 呼吸、动作启动
    "high":  (2000, 11000),    # 镲/齿音/弦乐高频与电吉他拨弦：浮尘闪烁、霜纹/光屑
    "voice": (250,  3500),     # 人声近似带（无分轨，mid 的子集）：歌唱呼吸
}


def p95_norm(x):
    """按全曲 P95 归一到 0..~1.1，截断在 1.15；静音段保持 0。"""
    x = np.asarray(x, dtype=np.float64)
    ref = np.percentile(x[x > 0], 95) if np.any(x > 0) else 1.0
    if ref <= 1e-8:
        return x
    return np.clip(x / ref, 0, 1.15)


def moving_average(x, win):
    """简单居中移动平均（端点缩小窗长），压住逐帧毛刺但不抹掉起音。"""
    if win <= 1:
        return x
    k = np.ones(win) / win
    return np.convolve(x, k, mode="same")


def band_rms(y, sr, f_lo, f_hi, hop_length):
    """分频带 RMS 曲线：STFT → 带通掩膜 → 每帧能量 → 振幅 RMS。"""
    n_fft = 2048
    stft = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    mag = np.abs(stft)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    mask = (freqs >= f_lo) & (freqs < f_hi)
    if not np.any(mask):
        return np.zeros(mag.shape[1])
    band_energy = np.sum(mag[mask, :] ** 2, axis=0)
    return np.sqrt(band_energy / max(mask.sum(), 1))


def main():
    print(f"[1/4] 读取音频：{AUDIO}")
    y, sr = librosa.load(AUDIO, sr=SR, mono=True)
    dur = float(librosa.get_duration(y=y, sr=sr))
    hop = int(round(sr / ENV_FPS))          # 让包络格点对齐 ENV_FPS
    n_frames = 1 + int(len(y) // hop)

    print(f"[2/4] 分频带 RMS 包络（{ENV_FPS}fps，{n_frames} 格）")
    env = {}
    for name, (f_lo, f_hi) in BANDS.items():
        r = band_rms(y, sr, f_lo, f_hi, hop)
        r = moving_average(r, win=3)        # 60ms 轻平滑
        env[name] = p95_norm(r)
    # 全频 RMS（整体密度/响度呼吸）
    rms = librosa.feature.rms(y=y, hop_length=hop, frame_length=2048)[0]
    env["rms"] = p95_norm(moving_average(rms, 3))

    print("[3/4] onset 起音检测 + 频带归属")
    # onset_strength 逐帧曲线也存下来（比离散点更适合做「刺点」反应）
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    # 离散 onset：后峰最大值抑制，去掉同一击弦的碎检测
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, hop_length=hop,
        onset_envelope=onset_env,
        backtrack=False,
        pre_max=3, post_max=6,             # ±60/120ms 邻域内只留最强
        pre_avg=3, post_avg=5, delta=0.07, wait=6,   # 相邻 onset 至少 120ms
    )
    onset_strengths = onset_env[onset_frames]
    # 全曲强度 P95 归一；过弱的（<0.18）直接丢弃，留给镜头的都是真事件
    if len(onset_strengths):
        ref = np.percentile(onset_strengths, 95) or 1.0
    else:
        ref = 1.0
    onsets = []
    for fr, st_v in zip(onset_frames, onset_strengths):
        s = float(np.clip(st_v / ref, 0, 1.15))
        if s < 0.18:
            continue
        # 归属：取该 onset 前 40ms~后 80ms 窗口内三带能量比较
        a = max(0, fr - 2)
        b = min(n_frames, fr + 4)
        lows = float(np.mean(env["low"][a:b]))
        mids = float(np.mean(env["mid"][a:b]))
        highs = float(np.mean(env["high"][a:b]))
        band = int(np.argmax([lows, mids, highs]))   # 0=low 1=mid 2=high
        onsets.append({"t": round(float(librosa.frames_to_time(fr, sr=sr, hop_length=hop)), 3),
                       "s": round(s, 3), "b": band})

    # onset 强度曲线同样归一后输出
    env["onset"] = p95_norm(moving_average(onset_env, 2))

    print("[4/4] 合并 hyperframes 强拍（beats/*.json）")
    beats = []
    if os.path.exists(BEATS_JSON):
        with open(BEATS_JSON, "r", encoding="utf-8") as f:
            bj = json.load(f)
        for bt in bj.get("beats", []):
            beats.append({"t": round(float(bt["time"]), 3),
                          "s": round(float(bt.get("strength", 0)), 3)})
    else:
        print(f"  警告：找不到 {BEATS_JSON}，beats 留空")

    def q3(a):
        return [round(float(v), 3) for v in np.asarray(a[:n_frames], dtype=np.float64)]

    data = {
        "version": 1,
        "audio": "assets/audio/黒薔薇の祈り.mp3",
        "note": "镜头内有机反应层数据源：onsets=起音事件(b:0low/1mid/2high)，"
                "env=50fps 包络(rms/low/mid/high/voice/onset)，全部 P95 归一",
        "fps": ENV_FPS,
        "duration": round(dur, 3),
        "beats": beats,
        "onsets": onsets,
        "env": {k: q3(v) for k, v in env.items()},
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    size_kb = os.path.getsize(OUT_JSON) / 1024

    # 同步产出镜头侧数据包（本地 <script> 引入，不走 fetch——遵守渲染铁律「禁网络请求」）
    vendor_dir = os.path.join(ROOT, "assets", "vendor")
    os.makedirs(vendor_dir, exist_ok=True)
    out_js = os.path.join(vendor_dir, "audio-events.js")
    with open(out_js, "w", encoding="utf-8") as f:
        f.write("/* 自动生成，勿手改：python analysis/onsets.py\n")
        f.write(" * 镜头内有机反应层数据源（onsets + 50fps 分频包络，全曲 P95 归一）。\n")
        f.write(" * 读取工具见 assets/vendor/audio-rig.js */\n")
        f.write("window.AUDIO_EVENTS = ")
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    print(f"完成：{OUT_JSON}")
    print(f"      {out_js}")
    print(f"  时长 {dur:.1f}s | onset {len(onsets)} 个 | 强拍 {len(beats)} 个 | "
          f"{size_kb:.0f} KB")
    # 控制台抽查：副歌锁链段 72.68-81.46 的低频 onset（应落在鼓点上）
    print("  抽查 72.6-81.5s 的 low/强 onset：")
    for o in onsets:
        if 72.6 <= o["t"] <= 81.5 and (o["b"] == 0 or o["s"] > 0.75):
            print(f"    t={o['t']:.3f} s={o['s']:.2f} band={['low','mid','high'][o['b']]}")


if __name__ == "__main__":
    main()
