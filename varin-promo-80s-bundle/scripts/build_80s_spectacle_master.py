import math
import os
import shutil
import subprocess
import time
import wave
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.signal import butter, lfilter

BASE = Path("/working_dir/c_060eff669e9961d5")
INTER_DIR = BASE / "artifacts/file_generation/ttl=63d/intermediate"
WORK_ROOT = INTER_DIR / "varin-promo-workspace"
OUT_DIR = BASE / "artifacts/file_generation/ttl=63d/output"
CACHE_DIR = INTER_DIR / "cached_assets"
CAP_DIR = INTER_DIR / "stage_captures"

dir_existing = WORK_ROOT / "01_项目里可取_已有素材"
BUNDLE80 = INTER_DIR / "varin-promo-80s-bundle"
AUDIO80 = BUNDLE80 / "audio"
KF80 = INTER_DIR / "full80_keyframes"
for d in [BUNDLE80, AUDIO80, KF80, OUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

FPS = 30
DURATION = 80.0
TOTAL_FRAMES = int(FPS * DURATION)  # 2400 frames = exact 176.000 beats (44 bars) @ 132 BPM!
BPM = 132.0
BEAT_SEC = 60.0 / BPM  # 0.45454545s
OUT_W, OUT_H = 1920, 1080

PM_W, PM_H = 3000, 1900
WIN_OX, WIN_OY = (PM_W - 2220) // 2, (PM_H - 1410) // 2  # (390, 245)

FONT_REG_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_BOLD_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

FONT_CACHE = {}
def get_font(path, px):
    px = max(10, int(round(px)))
    key = (path, px)
    if key in FONT_CACHE:
        return FONT_CACHE[key]
    for idx in [2, 3, 0]:
        try:
            f = ImageFont.truetype(path, size=px, index=idx)
            FONT_CACHE[key] = f
            return f
        except Exception:
            pass
    f = ImageFont.truetype(path, size=px)
    FONT_CACHE[key] = f
    return f

def hex_rgba(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

def clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)

def ease_whip(x):
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 5

def ease_in_quad(x):
    x = clamp01(x)
    return x * x

def ease_out_cubic(x):
    x = clamp01(x)
    return 1.0 - (1.0 - x) ** 3

def ease_in_out_whip(x):
    x = clamp01(x)
    return 16 * (x ** 5) if x < 0.5 else 1.0 - ((-2.0 * x + 2.0) ** 5) / 2.0

def ease_spring(x):
    x = clamp01(x)
    if x <= 0.0 or x >= 1.0:
        return x
    return 1.0 - math.exp(-7.8 * x) * math.cos(10.0 * x)


# =========================================================================
# PART 1: 80.0s (176 Beats / 44 Bars @ 132 BPM) Electronic Groove + Riser + Impact Finale
# =========================================================================
def save_wav_stereo(path: Path, left: np.ndarray, right: np.ndarray, sr: int = 44100):
    stereo = np.stack([left, right], axis=1)
    pcm16 = np.clip(stereo * 32767.0, -32767, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm16.tobytes())

def build_80s_audio_stems():
    sr = 44100
    n_samples = int(sr * DURATION)
    t = np.arange(n_samples, dtype=np.float64) / sr

    mus_l = np.zeros(n_samples, dtype=np.float64)
    mus_r = np.zeros(n_samples, dtype=np.float64)
    sfx_l = np.zeros(n_samples, dtype=np.float64)
    sfx_r = np.zeros(n_samples, dtype=np.float64)

    step_sec = BEAT_SEC / 4.0
    rng = np.random.default_rng(202680)

    def midi_to_freq(m):
        return 440.0 * (2.0 ** ((m - 69.0) / 12.0))

    def add_buf(buf_l, buf_r, sig_l, sig_r, start_sec):
        i0 = int(round(start_sec * sr))
        if i0 >= n_samples or i0 < 0:
            return
        length = min(len(sig_l), n_samples - i0)
        if length <= 0:
            return
        buf_l[i0:i0 + length] += sig_l[:length]
        buf_r[i0:i0 + length] += sig_r[:length]

    # Opening blade collision + riser to Beat 2 (0.91s)
    ns_hit = int(0.55 * sr)
    lt = np.arange(ns_hit) / sr
    imp = (np.sin(2 * np.pi * (66.0 + 145.0 * np.exp(-lt * 38.0)) * lt) * np.exp(-lt * 8.2) * 0.28 +
           np.sin(2 * np.pi * 880.0 * lt) * np.exp(-lt * 22.0) * 0.10)
    add_buf(mus_l, mus_r, imp, imp, 0.08)

    nr = int(0.50 * sr)
    rt = np.arange(nr) / sr
    rf = 220.0 * (2.0 ** (rt / 0.50 * 1.6))
    riser0 = np.sin(2 * np.pi * np.cumsum(rf) / sr) * ((rt / 0.50) ** 2) * 0.12
    add_buf(mus_l, mus_r, riser0 * 0.85, riser0 * 1.15, 0.38)

    b_clap, a_clap = butter(2, [1100.0 / (sr / 2.0), 4800.0 / (sr / 2.0)], btype="band")
    b_hat, a_hat = butter(2, [6500.0 / (sr / 2.0), 14500.0 / (sr / 2.0)], btype="band")
    b_bass, a_bass = butter(2, 780.0 / (sr / 2.0), btype="low")
    b_lead, a_lead = butter(2, 4300.0 / (sr / 2.0), btype="low")
    b_pad, a_pad = butter(2, 1300.0 / (sr / 2.0), btype="low")

    nk = int(0.19 * sr)
    kt = np.arange(nk) / sr
    kick_one = (np.sin(2 * np.pi * np.cumsum(52.0 + 140.0 * np.exp(-kt * 48.0)) / sr) * np.exp(-kt * 16.5) +
                np.sin(2 * np.pi * 1900.0 * kt) * np.exp(-kt * 140.0) * 0.26) * np.minimum(kt / 0.002, 1.0) * 0.25

    nc = int(0.14 * sr)
    ct = np.arange(nc) / sr
    burst = (np.exp(-ct * 120) * 0.5 + np.exp(-np.maximum(0, ct - 0.009) * 120) * 0.6 + np.exp(-np.maximum(0, ct - 0.018) * 32))
    clap_one = lfilter(b_clap, a_clap, rng.standard_normal(nc)) * burst * 0.13 + np.sin(2 * np.pi * 215.0 * ct) * np.exp(-ct * 35.0) * 0.08

    def in_typewriter_break(sec):
        # Short rhythmic breath during the two fast typewriter questions (45.45..46.35s and 52.73..54.25s)
        return (45.45 <= sec < 46.30) or (52.73 <= sec < 54.25)

    prog_roots = [45, 41, 48, 43]
    dark_roots = [40, 41, 45, 43]
    arp_bright = [
        [69, 72, 76, 81, 79, 76, 72, 76, 69, 72, 76, 84, 81, 79, 76, 72],
        [65, 69, 72, 77, 76, 72, 69, 72, 65, 69, 72, 81, 79, 76, 72, 69],
        [67, 72, 76, 79, 84, 79, 76, 72, 67, 72, 76, 83, 79, 76, 74, 72],
        [67, 71, 74, 79, 83, 79, 74, 71, 67, 71, 74, 81, 79, 74, 71, 69],
    ]
    arp_climax = [
        [72, 76, 81, 84, 88, 84, 81, 76, 72, 76, 81, 88, 86, 84, 81, 76],
        [69, 72, 77, 81, 84, 81, 77, 72, 69, 72, 77, 86, 84, 81, 77, 72],
        [72, 76, 79, 84, 88, 84, 79, 76, 72, 76, 79, 86, 84, 79, 76, 74],
        [71, 74, 79, 83, 86, 83, 79, 74, 71, 74, 79, 88, 86, 83, 79, 74],
    ]

    pad_voicings = [[57, 60, 64, 69], [53, 57, 60, 64], [55, 60, 64, 67], [55, 59, 62, 67]]
    for bar in range(0, 42):
        st_bar = bar * 4 * BEAT_SEC
        if st_bar >= 76.10:
            break
        notes = pad_voicings[bar % 4]
        dur_p = min(4 * BEAT_SEC + 0.25, 76.14 - st_bar)
        if dur_p <= 0.1:
            break
        ns_p = int(dur_p * sr)
        lt = np.arange(ns_p) / sr
        env = np.minimum(lt / 0.18, 1.0) * np.clip((dur_p - lt) / 0.20, 0.0, 1.0)
        pl = np.zeros(ns_p)
        pr = np.zeros(ns_p)
        for m in notes:
            f = midi_to_freq(m)
            pl += np.sin(2 * np.pi * (f * 0.9985) * lt) + 0.34 * np.sin(2 * np.pi * (f * 2.0) * lt)
            pr += np.sin(2 * np.pi * (f * 1.0015) * lt) + 0.34 * np.sin(2 * np.pi * (f * 2.002) * lt)
        vol_p = 0.050 if (st_bar >= 46.3) else 0.035
        add_buf(mus_l, mus_r, lfilter(b_pad, a_pad, pl) * env * vol_p, lfilter(b_pad, a_pad, pr) * env * vol_p, st_bar)

    # Full driving groove Beats 2..167 (0.91s .. 76.14s, stopping 0.22s before Beat 168 Final Impact Drop!)
    for beat in range(2, 168):
        bt = beat * BEAT_SEC
        if bt >= 76.12:
            break
        bar_idx = beat // 4
        is_dark = (46.36 <= bt < 61.82)
        is_climax = (bt >= 61.82)
        in_riser = (bt >= 72.73)  # Beats 160..167: Final 8-Beat Rapid Montage Build-up!
        brk = in_typewriter_break(bt)

        if not brk:
            add_buf(mus_l, mus_r, kick_one * (1.12 if is_climax else 1.0), kick_one * (1.12 if is_climax else 1.0), bt)
            if beat % 2 == 1 and not in_riser:
                add_buf(mus_l, mus_r, clap_one * 0.96, clap_one * 1.04, bt)

        # Accelerating Snare Roll during Beats 160..167.5 (72.73s .. 76.14s)!
        if in_riser:
            riser_u = clamp01((bt - 72.73) / (76.14 - 72.73))
            n_div = 2 if beat < 164 else 4  # 8th notes -> 16th notes!
            for r_sub in range(n_div):
                rst = bt + r_sub * (BEAT_SEC / n_div)
                if rst >= 76.14:
                    break
                sn_gain = 0.55 + 0.75 * riser_u
                add_buf(mus_l, mus_r, clap_one * sn_gain * 0.95, clap_one * sn_gain * 1.05, rst)

        for sub in range(4):
            hst = bt + sub * step_sec
            if hst >= 76.14:
                break
            if brk and sub % 2 == 1:
                continue
            decay = 26.0 if sub == 2 else 72.0
            amp = (0.060 if sub == 2 else 0.025) * (0.45 if brk else (1.22 if is_climax else 1.0))
            nh = int(0.075 * sr)
            ht = np.arange(nh) / sr
            hat = lfilter(b_hat, a_hat, rng.standard_normal(nh)) * np.exp(-ht * decay) * amp
            pan = 0.35 if sub % 2 == 0 else 0.65
            add_buf(mus_l, mus_r, hat * (1.0 - pan * 0.35), hat * (0.65 + pan * 0.35), hst)

        if not brk:
            roots = dark_roots if is_dark else prog_roots
            root_m = roots[bar_idx % 4]
            for eighth in range(2):
                bst = bt + eighth * (BEAT_SEC * 0.5)
                if bst >= 76.14:
                    break
                nb = int(0.23 * sr)
                lt = np.arange(nb) / sr
                bf = midi_to_freq(root_m + (12 if eighth == 1 else 0))
                saw = np.sin(2 * np.pi * bf * lt) + 0.58 * np.sin(2 * np.pi * bf * 2 * lt) + 0.28 * np.sin(2 * np.pi * bf * 3 * lt)
                benv = np.minimum(lt / 0.005, 1.0) * np.exp(-lt * 10.5)
                b_gain = 0.16 if (is_dark or is_climax) else 0.132
                bsig = lfilter(b_bass, a_bass, saw * benv) * (b_gain if eighth == 1 else b_gain * 0.85)
                add_buf(mus_l, mus_r, bsig, bsig, bst)

        arp_bank = arp_climax if is_climax else arp_bright
        arp = arp_bank[bar_idx % 4]
        beat_in_bar = beat % 4
        for sub in range(4):
            sst = bt + sub * step_sec
            if sst >= 76.14:
                break
            if brk and sub % 2 == 1:
                continue
            note_m = arp[beat_in_bar * 4 + sub] - (12 if is_dark and sub % 2 == 0 else 0)
            nf = midi_to_freq(note_m)
            nl = int(0.20 * sr)
            lt = np.arange(nl) / sr
            mod = np.exp(-lt * 34.0) * (1.95 if is_climax else 1.62)
            plk = np.sin(2 * np.pi * nf * lt + mod * np.sin(2 * np.pi * nf * 2.0 * lt))
            penv = np.minimum(lt / 0.003, 1.0) * np.exp(-lt * 14.0)
            vel = (0.098 if sub == 0 else 0.066) * (0.48 if brk else (1.20 if is_climax else 0.96))
            psig = lfilter(b_lead, a_lead, plk * penv) * vel
            pan = 0.28 if ((beat * 4 + sub) % 2 == 0) else 0.72
            add_buf(mus_l, mus_r, psig * (1.0 - pan * 0.45), psig * (0.55 + pan * 0.45), sst)

    # Synth Pitch + White-Noise Sweep Riser across Beats 160..167.5 (72.73s -> 76.14s)!
    r_dur = 76.14 - 72.73
    nr_c = int(r_dur * sr)
    rt_c = np.arange(nr_c) / sr
    ru = rt_c / r_dur
    f_sweep = 196.0 * (2.0 ** (ru * 2.4))
    sweep_tone = (np.sin(2 * np.pi * np.cumsum(f_sweep) / sr) +
                  0.45 * np.sin(2 * np.pi * np.cumsum(f_sweep * 1.5) / sr)) * (ru ** 2.2) * 0.14
    b_wn, a_wn = butter(2, [1800.0 / (sr / 2.0), 11000.0 / (sr / 2.0)], btype="band")
    sweep_noise = lfilter(b_wn, a_wn, rng.standard_normal(nr_c)) * (ru ** 2.6) * 0.11
    add_buf(mus_l, mus_r, sweep_tone * 0.9 + sweep_noise * 0.85, sweep_tone * 1.1 + sweep_noise * 1.15, 72.73)

    # MASSIVE FINAL IMPACT HIT at Beat 168 (76.364s) + Lush Major-9th Ring-Out (76.364s -> 80.00s)!
    impact_t = 168 * BEAT_SEC  # 76.3636s
    tail_dur = DURATION - impact_t  # 3.6364s
    nt = int(tail_dur * sr)
    lt_f = np.arange(nt) / sr

    # 1) Cinema Sub-Bass Boom + Punch Kick at 76.364s
    f_boom = 43.65 + 130.0 * np.exp(-lt_f * 26.0)  # F1 -> C1/F1 warm sub
    sub_boom = np.sin(2 * np.pi * np.cumsum(f_boom) / sr) * np.exp(-lt_f * 2.4) * 0.34
    add_buf(mus_l, mus_r, sub_boom, sub_boom, impact_t)

    # 2) Stereo Shimmer Cymbal Wash
    b_cym, a_cym = butter(2, [4200.0 / (sr / 2.0), 15000.0 / (sr / 2.0)], btype="band")
    cym_l = lfilter(b_cym, a_cym, rng.standard_normal(nt)) * np.exp(-lt_f * 1.85) * 0.085
    cym_r = lfilter(b_cym, a_cym, rng.standard_normal(nt)) * np.exp(-lt_f * 1.85) * 0.085
    add_buf(mus_l, mus_r, cym_l, cym_r, impact_t)

    # 3) Heroic Lush C-Major-9 Synth Stack + Sparkling Bell Arpeggio
    b_end, a_end = butter(2, 4200.0 / (sr / 2.0), btype="low")
    hero_notes = [48, 55, 60, 64, 67, 71, 74, 79, 84]  # C2 G2 C3 E3 G3 B3 D4 G4 C5
    for idx, m in enumerate(hero_notes):
        f = midi_to_freq(m)
        sig_l = np.sin(2 * np.pi * (f * 0.9985) * lt_f) + 0.42 * np.sin(2 * np.pi * (f * 2.0) * lt_f)
        sig_r = np.sin(2 * np.pi * (f * 1.0015) * lt_f) + 0.42 * np.sin(2 * np.pi * (f * 2.002) * lt_f)
        env = np.minimum(lt_f / 0.010, 1.0) * np.exp(-lt_f * 0.68)
        pan = 0.2 + 0.6 * (idx / (len(hero_notes) - 1))
        add_buf(mus_l, mus_r, lfilter(b_end, a_end, sig_l * env) * 0.052 * (1.1 - pan * 0.3),
                lfilter(b_end, a_end, sig_r * env) * 0.052 * (0.8 + pan * 0.3), impact_t + idx * 0.016)

    # Sparkling crystalline bell notes across the finale (76.45 -> 79.10s)
    bell_seq = [(76.42, 84), (76.65, 88), (76.88, 91), (77.58, 86), (78.85, 96)]
    for bt_b, bm in bell_seq:
        nb_l = int(1.05 * sr)
        tb = np.arange(nb_l) / sr
        fb = midi_to_freq(bm)
        bell = (np.sin(2 * np.pi * fb * tb) + 0.35 * np.sin(2 * np.pi * fb * 3.0 * tb) * np.exp(-tb * 14.0)) * np.exp(-tb * 3.2) * 0.055
        add_buf(mus_l, mus_r, bell * 0.9, bell * 1.1, bt_b)

    # --- UI & SPECTACLE SFX STEM (sfx_ui.wav) ---
    b_key, a_key = butter(2, [1600.0 / (sr / 2.0), 6500.0 / (sr / 2.0)], btype="band")
    def add_typing_burst(t0, t1, step=0.055, vol=0.056):
        ct_k = t0
        while ct_k < t1:
            nk_s = int(0.022 * sr)
            kt_s = np.arange(nk_s) / sr
            kn = lfilter(b_key, a_key, rng.standard_normal(nk_s)) * np.exp(-kt_s * 210.0)
            kth = np.sin(2 * np.pi * (440.0 + rng.random() * 90.0) * kt_s) * np.exp(-kt_s * 160.0) * 0.55
            ks = (kn + kth) * vol
            add_buf(sfx_l, sfx_r, ks * 0.95, ks * 1.05, ct_k)
            ct_k += step * (0.85 + 0.3 * rng.random())

    def add_click(sec, pitch=84, vol=0.11):
        nc_s = int(0.24 * sr)
        lt = np.arange(nc_s) / sr
        clk = np.sin(2 * np.pi * 2450.0 * lt) * np.exp(-lt * 260.0) * vol
        ping = (np.sin(2 * np.pi * midi_to_freq(pitch) * lt) * np.exp(-lt * 17.0) * 0.075 +
                np.sin(2 * np.pi * midi_to_freq(pitch + 7) * lt) * np.exp(-lt * 14.0) * 0.055)
        add_buf(sfx_l, sfx_r, clk + ping * 0.9, clk + ping * 1.1, sec)

    def add_whoosh(sec, dur=0.19, vol=0.062):
        nw = int(dur * sr)
        lt = np.arange(nw) / sr
        bw, aw = butter(2, [700.0 / (sr / 2.0), 3900.0 / (sr / 2.0)], btype="band")
        sh = lfilter(bw, aw, rng.standard_normal(nw)) * (np.sin(np.pi * lt / dur) ** 2.0) * vol
        pan = np.linspace(0.18, 0.82, nw)
        add_buf(sfx_l, sfx_r, sh * (1.0 - pan * 0.5), sh * (0.5 + pan * 0.5), sec)

    def add_laser_zap(sec, dur=0.42, vol=0.095):
        nz = int(dur * sr)
        lt = np.arange(nz) / sr
        fz = 520.0 + 1850.0 * np.sin(np.pi * lt / dur)
        zap = np.sin(2 * np.pi * np.cumsum(fz) / sr) * (np.sin(np.pi * lt / dur) ** 1.4) * vol * 0.48
        add_buf(sfx_l, sfx_r, zap * 0.85, zap * 1.15, sec)
        add_whoosh(sec, dur=dur, vol=vol * 0.8)

    def add_sub_drop(sec, vol=0.22):
        nd = int(0.52 * sr)
        lt = np.arange(nd) / sr
        f_sw = 44.0 + 98.0 * np.exp(-lt * 15.0)
        drp = np.sin(2 * np.pi * np.cumsum(f_sw) / sr) * np.exp(-lt * 5.6) * vol
        add_buf(sfx_l, sfx_r, drp, drp, sec)

    # Act 1 SFX
    for wi in range(10):
        add_click(0.95 + wi * 0.14, pitch=70 + wi, vol=0.042)
    add_whoosh(2.68, 0.25, 0.075)
    add_sub_drop(2.73, vol=0.19)
    add_whoosh(4.82, 0.26, 0.068)

    # Act 2 SFX: Typing -> Send + Bezier Particle Zap -> Live Stage Card Throws -> Radio -> Chart -> Choices -> Live Slider!
    add_typing_burst(5.90, 7.85, step=0.052, vol=0.056)
    add_click(8.18, pitch=84)
    add_laser_zap(8.22, dur=0.55, vol=0.088)  # Bezier particle comet!
    add_click(9.45, pitch=79, vol=0.072)      # Card throw 1
    add_click(10.05, pitch=83, vol=0.072)     # Card throw 2
    add_whoosh(12.65, 0.22, 0.060)
    add_click(15.00, pitch=86)
    add_whoosh(16.25, 0.24, 0.058)
    add_whoosh(19.88, 0.22, 0.056)
    add_click(21.36, pitch=83)
    add_click(22.50, pitch=86)
    add_whoosh(23.52, 0.22, 0.058)
    # Slider drag ticks (24.80 -> 26.35s)
    for si in range(7):
        add_click(24.85 + si * 0.21, pitch=76 + si * 2, vol=0.045)

    # Act 3 SFX: 3D Multi-Window Spatial Array + Bezier Streams -> Workbench -> Step-in -> IDE Build -> Dual-View!
    add_whoosh(27.18, 0.28, 0.072)
    add_laser_zap(28.10, dur=0.50, vol=0.078)
    add_whoosh(31.68, 0.24, 0.065)
    add_typing_burst(35.80, 37.65, step=0.056, vol=0.054)
    add_click(38.18, pitch=84)
    add_click(39.32, pitch=83)
    add_whoosh(39.48, 0.24, 0.060)
    add_typing_burst(40.25, 41.15, step=0.060, vol=0.058)
    add_click(41.59, pitch=88, vol=0.12)
    add_whoosh(42.62, 0.24, 0.058)

    # Act 4 SFX: Typewriter 1 -> Diagonal Laser Light-to-Dark Wipe -> 2.5D Codex -> Typewriter 2 -> 2.5D Office!
    add_typing_burst(45.52, 46.22, step=0.062, vol=0.068)
    add_laser_zap(46.28, dur=0.48, vol=0.115)  # Diagonal Laser Wipe!
    add_sub_drop(46.45, vol=0.23)
    add_click(48.30, pitch=81, vol=0.07)
    add_click(51.40, pitch=85)
    add_typing_burst(52.82, 54.15, step=0.064, vol=0.068)
    add_whoosh(54.42, 0.25, 0.074)
    add_sub_drop(54.55, vol=0.22)
    for oi in range(3):
        add_click(56.05 + oi * 0.30, pitch=82 + oi * 3, vol=0.07)

    # Act 5 SFX: 16-Agent Storm Envelope Flutters -> 3D Flywheel -> 8-Beat Rapid Montage Cuts -> Final Impact + Wink!
    add_whoosh(61.70, 0.26, 0.072)
    for ei in range(10):
        add_click(62.20 + ei * 0.24, pitch=79 + (ei % 4) * 2, vol=0.038)
    add_click(65.10, pitch=88, vol=0.095)
    add_whoosh(67.15, 0.26, 0.068)
    for mi in range(8):
        cut_t = 72.73 + mi * BEAT_SEC
        add_whoosh(cut_t - 0.04, 0.14, 0.062)
        add_click(cut_t, pitch=76 + mi * 2, vol=0.065)
    add_sub_drop(impact_t, vol=0.28)
    add_whoosh(impact_t - 0.06, 0.32, 0.085)
    add_click(78.88, pitch=96, vol=0.09)  # Wink sparkle!

    fade_env = np.clip(t / 0.05, 0.0, 1.0) * np.clip((DURATION - t) / 0.45, 0.0, 1.0)
    mus_l *= fade_env
    mus_r *= fade_env
    sfx_l *= fade_env
    sfx_r *= fade_env

    m_peak = max(np.max(np.abs(mus_l)), np.max(np.abs(mus_r)), 1e-6)
    mus_l_out, mus_r_out = mus_l * (0.78 / m_peak), mus_r * (0.78 / m_peak)

    s_peak = max(np.max(np.abs(sfx_l)), np.max(np.abs(sfx_r)), 1e-6)
    sfx_gain = min(1.0, 0.74 / s_peak)
    sfx_l_out, sfx_r_out = sfx_l * sfx_gain, sfx_r * sfx_gain

    mix_l = mus_l_out + sfx_l_out * 0.80
    mix_r = mus_r_out + sfx_l_out * 0.80
    mix_peak = max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r)), 1e-6)
    if mix_peak > 0.91:
        mix_l *= (0.91 / mix_peak)
        mix_r *= (0.91 / mix_peak)

    p_music = AUDIO80 / "music_132bpm.wav"
    p_sfx = AUDIO80 / "sfx_ui.wav"
    p_mix = AUDIO80 / "master_mix.wav"
    save_wav_stereo(p_music, mus_l_out, mus_r_out, sr)
    save_wav_stereo(p_sfx, sfx_l_out, sfx_r_out, sr)
    save_wav_stereo(p_mix, mix_l, mix_r, sr)
    # Also copy standalone WAVs to OUT_DIR for direct delivery
    shutil.copy2(p_music, OUT_DIR / "music_132bpm_80s.wav")
    shutil.copy2(p_sfx, OUT_DIR / "sfx_ui_80s.wav")
    print("Saved 80s audio stems:", p_music.name, p_sfx.name, p_mix.name)
    return p_mix


# =========================================================================
# PART 2: Next-Level Visual Spectacle Engines
# =========================================================================
def make_chaotic_mini_windows():
    specs = [
        ("Terminal — zsh", "#1e222a", "#e06c75", "$ npm run release\nERR! Port 3000 in use", True),
        ("Docs — 发布说明_最终版3.md", "#ffffff", "#4b6fac", "## 待确认读者对象\n[TODO] 还没对齐反馈数据...", False),
        ("Chat — 单个对话窗口 #4", "#f7f8fa", "#68707a", "上下文太长已被截断，请重开会话", False),
        ("Logs — CI Runner", "#191c22", "#e5c07b", "WARN: Accessibility check skipped", True),
        ("Browser — 16 个标签页", "#ffffff", "#528bff", "ArXiv / 竞品反馈 / 官网文案草稿...", False),
        ("Terminal — codex-cli", "#1b1f27", "#98c379", "Waiting for manual file copy...", True),
        ("Issues — 反馈收集表", "#fbfcfe", "#c678dd", "● 38% 用户问第一次打开能做什么", False),
        ("Git — Merge Conflict", "#21252b", "#e06c75", "CONFLICT: ReleaseSummary.tsx", True),
        ("Slides — 周五汇报.pptx", "#ffffff", "#d19a66", "第 4 页图表数据尚未同步更新", False),
        ("Chat — 另一个窗口 #9", "#f6f8fb", "#56b6c2", "刚才改过的文件版本找不到了...", False),
    ]
    f_hdr = get_font(FONT_BOLD_PATH, 14)
    f_bdy = get_font(FONT_REG_PATH, 13)
    sprites = []
    for title, bg_h, acc_h, body_txt, is_dark in specs:
        w, h = 320, 148
        im = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
        sh = Image.new("L", (w + 24, h + 24), 0)
        ImageDraw.Draw(sh).rounded_rectangle((12, 16, 12 + w, 16 + h), radius=14, fill=55)
        sh = sh.filter(ImageFilter.GaussianBlur(radius=6))
        sh_rgba = Image.new("RGBA", (w + 24, h + 24), (15, 20, 30, 0))
        sh_rgba.putalpha(sh)
        im = Image.alpha_composite(im, sh_rgba)

        fg = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
        dr = ImageDraw.Draw(fg)
        b_col = (58, 66, 80, 255) if is_dark else (208, 215, 226, 255)
        dr.rounded_rectangle((12, 12, 12 + w, 12 + h), radius=14, fill=hex_rgba(bg_h, 246), outline=b_col, width=2)
        dr.rounded_rectangle((12, 12, 12 + w, 44), radius=14, fill=hex_rgba("#282c34" if is_dark else "#eef1f6", 255))
        for di, dc in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
            dr.ellipse((24 + di * 14, 23, 33 + di * 14, 32), fill=hex_rgba(dc))
        dr.text((72, 19), title, font=f_hdr, fill=(225, 230, 238, 255) if is_dark else (45, 52, 62, 255))
        for li, line in enumerate(body_txt.split("\n")):
            col = hex_rgba(acc_h) if li == 1 else ((190, 198, 210, 255) if is_dark else (85, 94, 106, 255))
            dr.text((26, 58 + li * 26), line, font=f_bdy, fill=col)
        sprites.append(np.asarray(Image.alpha_composite(im, fg)))
    return sprites

def zoom_scale_frame(rgb: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1.0) < 0.003:
        return rgb
    M = np.array([[scale, 0.0, OUT_W * 0.5 * (1.0 - scale)],
                  [0.0, scale, OUT_H * 0.5 * (1.0 - scale)]], dtype=np.float64)
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    return cv2.warpAffine(rgb, M, (OUT_W, OUT_H), flags=interp, borderMode=cv2.BORDER_REPLICATE)

def zoom_through_blend(frame_a: np.ndarray, frame_b: np.ndarray, p: float) -> np.ndarray:
    p = clamp01(p)
    ea = ease_in_quad(p)
    eb = ease_out_cubic(p)
    za = zoom_scale_frame(frame_a, 1.0 + 0.85 * ea).astype(np.float32)
    zb = zoom_scale_frame(frame_b, 0.72 + 0.28 * eb).astype(np.float32)
    w_b = ease_in_out_whip(p)
    return np.clip(za * (1.0 - w_b) + zb * w_b, 0, 255).astype(np.uint8)

def diagonal_laser_wipe(light_rgb: np.ndarray, dark_rgb: np.ndarray, p: float) -> np.ndarray:
    """
    SPECTACLE UPGRADE #4: Diagonal Electric-Cyan Laser Split-Screen Wipe!
    Sweeps a 17-degree tilted glowing neon beam across 1920x1080 morphing Light Space into 3D Dark Cyber Space!
    """
    p = clamp01(p)
    ep = ease_in_out_whip(p)
    yy, xx = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)
    diag = xx + yy * 0.32  # 0 .. 2265
    edge = -160.0 + ep * 2580.0
    dist = diag - edge
    mask_dark = np.clip(0.5 - dist / 18.0, 0.0, 1.0)[..., None]

    base = light_rgb.astype(np.float32) * (1.0 - mask_dark) + dark_rgb.astype(np.float32) * mask_dark
    # Blazing dual-core laser glow along |dist| < 65px
    core = np.exp(-(dist ** 2) / (2.0 * (5.5 ** 2)))[..., None]
    halo = np.exp(-(dist ** 2) / (2.0 * (34.0 ** 2)))[..., None]
    laser_col = np.array([110.0, 195.0, 255.0], dtype=np.float32)[None, None, :]
    white_col = np.array([250.0, 253.0, 255.0], dtype=np.float32)[None, None, :]
    out = base + halo * laser_col * 0.85 + core * white_col * 0.95
    return np.clip(out, 0, 255).astype(np.uint8)

def draw_glowing_bezier_stream(canvas_rgb: np.ndarray, p0, p1, ctrl, head_u: float,
                               tail_len: float = 0.42, color_rgb=(95, 175, 255), thickness: int = 4):
    """
    SPECTACLE UPGRADE #3: Glowing Bezier Particle Data Stream + Comet Head + Trailing Sparks!
    """
    if head_u <= 0.01 or head_u - tail_len >= 1.0:
        return
    u0 = max(0.0, head_u - tail_len)
    u1 = min(1.0, head_u)
    if u1 <= u0 + 0.005:
        return

    n_seg = 36
    us = np.linspace(u0, u1, n_seg)
    pts = []
    for u in us:
        bx = (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * ctrl[0] + u ** 2 * p1[0]
        by = (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * ctrl[1] + u ** 2 * p1[1]
        pts.append((int(round(bx)), int(round(by))))

    overlay = canvas_rgb.copy()
    for i in range(len(pts) - 1):
        seg_frac = (i + 1) / float(len(pts))
        w = max(1, int(round(thickness * (0.3 + 0.9 * seg_frac))))
        c = tuple(int(min(255, ch * (0.55 + 0.55 * seg_frac))) for ch in color_rgb)
        cv2.line(overlay, pts[i], pts[i + 1], c, w + 6, cv2.LINE_AA)
    canvas_rgb[:] = cv2.addWeighted(overlay, 0.35, canvas_rgb, 0.65, 0)

    for i in range(len(pts) - 1):
        seg_frac = (i + 1) / float(len(pts))
        w = max(1, int(round(thickness * (0.25 + 0.85 * seg_frac))))
        c = tuple(int(min(255, ch + (255 - ch) * (seg_frac ** 2) * 0.65)) for ch in color_rgb)
        cv2.line(canvas_rgb, pts[i], pts[i + 1], c, w, cv2.LINE_AA)

    # Bright Comet Head + Orbiting Micro-Sparks
    hx, hy = pts[-1]
    if 0 <= hx < OUT_W * 2 and 0 <= hy < OUT_H * 2:
        cv2.circle(canvas_rgb, (hx, hy), thickness * 3 + 4, color_rgb, -1, cv2.LINE_AA)
        cv2.circle(canvas_rgb, (hx, hy), thickness + 2, (252, 254, 255), -1, cv2.LINE_AA)
        for sp_i in range(4):
            idx_s = max(0, len(pts) - 3 - sp_i * 6)
            sx, sy = pts[idx_s]
            ox = int(math.sin(head_u * 28.0 + sp_i * 2.1) * 14.0)
            oy = int(math.cos(head_u * 24.0 + sp_i * 1.7) * 14.0)
            cv2.circle(canvas_rgb, (sx + ox, sy + oy), 3, (220, 240, 255), -1, cv2.LINE_AA)

def make_gradient_bg(w, h, dark=False):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = (xx - w * 0.5) / (w * 0.65)
    ny = (yy - h * 0.45) / (h * 0.68)
    dist = np.clip(np.sqrt(nx * nx + ny * ny), 0.0, 1.25) / 1.25
    sm = dist * dist * (3.0 - 2.0 * dist)
    if not dark:
        c0 = np.array([249.0, 250.0, 252.0], dtype=np.float32)
        c1 = np.array([234.0, 238.0, 244.0], dtype=np.float32)
    else:
        c0 = np.array([25.0, 33.0, 50.0], dtype=np.float32)
        c1 = np.array([10.0, 13.0, 20.0], dtype=np.float32)
    rgb = c0[None, None, :] * (1.0 - sm[..., None]) + c1[None, None, :] * sm[..., None]
    return np.clip(rgb, 0, 255).astype(np.uint8)

def render_dynamic_dark_backdrop(base_dark_1080: np.ndarray, sec: float, boost: float = 0.0) -> np.ndarray:
    bg = base_dark_1080.copy()
    pulse = 0.5 + 0.5 * math.sin(sec * (BPM / 60.0) * math.pi * 2.0)
    k_b = 1.0 + boost * 0.65
    grid_col = (min(255, int((38 + 16 * pulse) * k_b)),
                min(255, int((56 + 24 * pulse) * k_b)),
                min(255, int((88 + 34 * pulse) * k_b)))

    horizon = 540
    for i in range(-8, 9):
        x_end = int(960 + i * 240 + (sec * 52.0) % 240 - 120)
        cv2.line(bg, (960 + i * 45, horizon), (x_end, OUT_H), grid_col, 1, cv2.LINE_AA)
        cv2.line(bg, (960 + i * 45, horizon), (x_end, 0), grid_col, 1, cv2.LINE_AA)

    phase = (sec * 0.95) % 1.0
    for k in range(1, 7):
        d = ((k + phase) / 7.0) ** 2.2
        yb = int(horizon + d * (OUT_H - horizon))
        yt = int(horizon - d * horizon)
        cv2.line(bg, (0, yb), (OUT_W, yb), grid_col, 1)
        cv2.line(bg, (0, yt), (OUT_W, yt), grid_col, 1)

    orbs = [(320, 240, 145, (38, 70, 124)), (1620, 820, 185, (34, 76, 110)), (1480, 210, 115, (54, 68, 122))]
    for ox, oy, rad, col in orbs:
        px = int(ox + math.sin(sec * 1.4 + ox) * 48)
        py = int(oy + math.cos(sec * 1.2 + oy) * 32)
        c_orb = tuple(min(255, int(v * k_b)) for v in col)
        cv2.circle(bg, (px, py), rad, c_orb, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(bg, (21, 21), 0)

def elevate_25d_card(st_rgb: np.ndarray, src_plate_rgb: np.ndarray,
                     x0: int, y0: int, x1: int, y1: int,
                     lift_prog: float, yaw_deg: float, glow_rgb=(122, 167, 239)):
    lp = ease_spring(lift_prog)
    if lp <= 0.02:
        return
    cw, ch = x1 - x0, y1 - y0
    card = src_plate_rgb[WIN_OY + y0:WIN_OY + y1, WIN_OX + x0:WIN_OX + x1].copy()

    ax0, ay0, ax1, ay1 = WIN_OX + x0, WIN_OY + y0, WIN_OX + x1, WIN_OY + y1
    st_rgb[ay0:ay1, ax0:ax1] = (st_rgb[ay0:ay1, ax0:ax1].astype(np.float32) * (1.0 - 0.55 * clamp01(lift_prog))).astype(np.uint8)

    scale = 1.0 + 0.095 * lp
    nw, nh = int(cw * scale), int(ch * scale)
    card_up = cv2.resize(card, (nw, nh), interpolation=cv2.INTER_CUBIC)

    par_x = int(-yaw_deg * 2.5 * clamp01(lift_prog))
    par_y = int(-20 * lp)
    dx0 = ax0 - (nw - cw) // 2 + par_x
    dy0 = ay0 - (nh - ch) // 2 + par_y

    sh_pad = 18
    sx0, sy0 = max(0, dx0 - sh_pad + 8), max(0, dy0 - sh_pad + 22)
    sx1, sy1 = min(PM_W, dx0 + nw + sh_pad + 8), min(PM_H, dy0 + nh + sh_pad + 22)
    st_rgb[sy0:sy1, sx0:sx1] = (st_rgb[sy0:sy1, sx0:sx1].astype(np.float32) * (1.0 - 0.50 * clamp01(lift_prog))).astype(np.uint8)

    cx0, cy0 = max(0, dx0), max(0, dy0)
    cx1, cy1 = min(PM_W, dx0 + nw), min(PM_H, dy0 + nh)
    st_rgb[cy0:cy1, cx0:cx1] = card_up[:cy1 - cy0, :cx1 - cx0]
    cv2.rectangle(st_rgb, (cx0, cy0), (cx1 - 1, cy1 - 1), glow_rgb, thickness=3, lineType=cv2.LINE_AA)

def place_window_on_stage_np(ui_rgba: Image.Image, base_stage_np: np.ndarray, dark=False, transparent_bg=False) -> np.ndarray:
    if transparent_bg:
        stage = Image.new("RGBA", (PM_W, PM_H), (0, 0, 0, 0))
    else:
        stage = Image.fromarray(base_stage_np).convert("RGBA")
    w, h = ui_rgba.size
    sh_mask = Image.new("L", (PM_W, PM_H), 0)
    ImageDraw.Draw(sh_mask).rounded_rectangle(
        (WIN_OX, WIN_OY + 26, WIN_OX + w, WIN_OY + h + 26), radius=24, fill=(165 if dark else 58)
    )
    sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(radius=(46 if dark else 34)))
    sh_layer = Image.new("RGBA", (PM_W, PM_H), (0, 0, 0, 0) if dark else (18, 24, 34, 0))
    sh_layer.putalpha(sh_mask)
    stage = Image.alpha_composite(stage, sh_layer)

    wmask = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(wmask).rounded_rectangle((0, 0, w * 2 - 1, h * 2 - 1), radius=44, fill=255)
    wmask = wmask.resize((w, h), Image.Resampling.LANCZOS)

    win_layer = Image.new("RGBA", (PM_W, PM_H), (0, 0, 0, 0))
    win_layer.paste(ui_rgba, (WIN_OX, WIN_OY), wmask)
    b_col = (88, 106, 138, 255) if dark else (196, 204, 216, 255)
    ImageDraw.Draw(win_layer).rounded_rectangle(
        (WIN_OX, WIN_OY, WIN_OX + w, WIN_OY + h), radius=22, outline=b_col, width=3
    )
    comp = Image.alpha_composite(stage, win_layer)
    return np.asarray(comp if transparent_bg else comp.convert("RGB"))

def project_3d(stage_arr: np.ndarray, win_fx: float, win_fy: float, zoom: float,
               yaw_deg: float = 0.0, pitch_deg: float = 0.0, roll_deg: float = 0.0,
               border_rgb=(236, 240, 245), custom_bg_1080: np.ndarray = None,
               screen_cx: float = OUT_W * 0.5, screen_cy: float = OUT_H * 0.5) -> np.ndarray:
    fx = WIN_OX + win_fx
    fy = WIN_OY + win_fy
    base_scale = (1332.0 / 2220.0) * zoom

    corners = np.array([[0.0, 0.0], [float(PM_W), 0.0], [float(PM_W), float(PM_H)], [0.0, float(PM_H)]], dtype=np.float64)
    dx = corners[:, 0] - fx
    dy = corners[:, 1] - fy
    pts3 = np.stack([dx, dy, np.zeros(4, dtype=np.float64)], axis=1)

    yr, pr, rr = math.radians(yaw_deg), math.radians(pitch_deg), math.radians(roll_deg)
    Ry = np.array([[math.cos(yr), 0, math.sin(yr)], [0, 1, 0], [-math.sin(yr), 0, math.cos(yr)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(pr), -math.sin(pr)], [0, math.sin(pr), math.cos(pr)]])
    Rz = np.array([[math.cos(rr), -math.sin(rr), 0], [math.sin(rr), math.cos(rr), 0], [0, 0, 1]])
    rot = pts3 @ (Rz @ Rx @ Ry).T

    cam_d = 2450.0
    z_denom = np.maximum(cam_d + rot[:, 2], 250.0)
    proj_x = screen_cx + (rot[:, 0] * cam_d / z_denom) * base_scale
    proj_y = screen_cy + (rot[:, 1] * cam_d / z_denom) * base_scale

    H = cv2.getPerspectiveTransform(corners.astype(np.float32), np.stack([proj_x, proj_y], axis=1).astype(np.float32))
    interp = cv2.INTER_AREA if base_scale < 0.95 else cv2.INTER_CUBIC

    if custom_bg_1080 is not None and stage_arr.shape[2] == 4:
        warped_rgba = cv2.warpPerspective(stage_arr, H, (OUT_W, OUT_H), flags=interp,
                                          borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        a = warped_rgba[..., 3:4].astype(np.float32) / 255.0
        return np.clip(custom_bg_1080.astype(np.float32) * (1.0 - a) + warped_rgba[..., :3].astype(np.float32) * a, 0, 255).astype(np.uint8)

    return cv2.warpPerspective(stage_arr, H, (OUT_W, OUT_H), flags=interp,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=border_rgb)

def make_cursor_rgba(scale=1.35):
    sz = int(64 * scale)
    im = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    pts_base = [(4, 4), (4, 38), (13, 30), (20, 45), (26, 42), (19, 27), (30, 27)]
    pts = [(px * scale, py * scale) for px, py in pts_base]
    pts_sh = [(px + 2 * scale, py + 3 * scale) for px, py in pts]
    dr.polygon(pts_sh, fill=(0, 0, 0, 80))
    dr.polygon(pts, fill=(24, 28, 34, 255), outline=(255, 255, 255, 255), width=max(2, int(2.5 * scale)))
    return np.asarray(im)

CURSOR_SPRITE = make_cursor_rgba(1.35)

def blit_rgba_np(dst_rgb: np.ndarray, src_rgba: np.ndarray, x: int, y: int, opacity: float = 1.0):
    if opacity <= 0.01:
        return
    h, w = src_rgba.shape[:2]
    dh, dw = dst_rgb.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dw, x + w), min(dh, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    sx0, sy0 = x0 - x, y0 - y
    sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)
    sub_src = src_rgba[sy0:sy1, sx0:sx1]
    alpha = (sub_src[..., 3:4].astype(np.float32) / 255.0) * clamp01(opacity)
    dst_slice = dst_rgb[y0:y1, x0:x1].astype(np.float32)
    dst_rgb[y0:y1, x0:x1] = np.clip(dst_slice * (1.0 - alpha) + sub_src[..., :3].astype(np.float32) * alpha, 0, 255).astype(np.uint8)

PILL_CACHE = {}
def get_pill_np(text: str, dot_hex: str) -> np.ndarray:
    key = (text, dot_hex)
    if key in PILL_CACHE:
        return PILL_CACHE[key]
    f_tag = get_font(FONT_BOLD_PATH, 20)
    tw = ImageDraw.Draw(Image.new("RGBA", (10, 10))).textbbox((0, 0), text, font=f_tag)[2]
    pw, ph = tw + 58, 48
    sh_mask = Image.new("L", (pw + 24, ph + 24), 0)
    ImageDraw.Draw(sh_mask).rounded_rectangle((12, 16, 12 + pw, 16 + ph), radius=24, fill=52)
    sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(radius=5))
    pill = Image.new("RGBA", (pw + 24, ph + 24), (15, 20, 28, 0))
    pill.putalpha(sh_mask)
    fg = Image.new("RGBA", (pw + 24, ph + 24), (0, 0, 0, 0))
    pd = ImageDraw.Draw(fg)
    pd.rounded_rectangle((12, 12, 12 + pw, 12 + ph), radius=24, fill=(24, 30, 36, 236), outline=(255, 255, 255, 45), width=1)
    pd.ellipse((30, 29, 44, 43), fill=hex_rgba(dot_hex))
    pd.text((54, 21), text, font=f_tag, fill=(248, 250, 252, 255))
    arr = np.asarray(Image.alpha_composite(pill, fg))
    PILL_CACHE[key] = arr
    return arr

def add_corner_pill(frame_rgb: np.ndarray, text: str, dot_hex: str, prog: float, pos=("left", "top")) -> np.ndarray:
    p = clamp01(prog)
    if p <= 0.01:
        return frame_rgb
    arr = get_pill_np(text, dot_hex)
    nh, nw = arr.shape[:2]
    x = (OUT_W - nw - 42) if pos[0] == "right" else 42
    y = int(36 - (1.0 - ease_out_cubic(p)) * 12)
    blit_rgba_np(frame_rgb, arr, x, y, opacity=p)
    return frame_rgb

def spring_slide_block(st_rgb: np.ndarray, src_rgb: np.ndarray, x0: int, x1: int, y0: int, y1: int, prog: float, bg_rgb=(243, 243, 243)):
    if prog >= 0.999:
        return
    ax0, ax1 = WIN_OX + x0, WIN_OX + x1
    ay0, ay1 = WIN_OY + y0, WIN_OY + y1
    st_rgb[ay0:ay1, ax0:ax1] = bg_rgb
    if prog <= 0.005:
        return
    ep = ease_out_cubic(prog)
    dy = int((1.0 - ep) * 24)
    src_patch = src_rgb[ay0:ay1, ax0:ax1].astype(np.float32)
    dst_y0 = min(PM_H, ay0 + dy)
    dst_y1 = min(PM_H, ay1 + dy)
    valid_h = dst_y1 - dst_y0
    if valid_h > 0:
        cur_bg = st_rgb[dst_y0:dst_y1, ax0:ax1].astype(np.float32)
        alpha = clamp01(prog * 1.6)
        st_rgb[dst_y0:dst_y1, ax0:ax1] = np.clip(cur_bg * (1.0 - alpha) + src_patch[:valid_h] * alpha, 0, 255).astype(np.uint8)


# =========================================================================
# PART 3: 80.0s Flagship Spectacle Master Renderer (All 7 UIs + All 3 Live Stages + 5 Upgrades)
# =========================================================================
def render_80s_master(mix_wav_path: Path, mp4_out_path: Path):
    t_start = time.time()
    light_stage_bg = make_gradient_bg(PM_W, PM_H, dark=False)
    dark_stage_bg = make_gradient_bg(PM_W, PM_H, dark=True)
    out_light_bg = make_gradient_bg(OUT_W, OUT_H, dark=False)
    out_dark_bg = make_gradient_bg(OUT_W, OUT_H, dark=True)

    chaos_windows = make_chaotic_mini_windows()

    # Load ALL 7 Official Retina Chinese UI Plates + 2 Dark Plates
    ui_dir = dir_existing / "ui_readme_zh"
    im_varin_raw = Image.open(ui_dir / "varin-zh-CN.png").convert("RGBA")
    im_chart_raw = Image.open(ui_dir / "conversation-chart-zh-CN.png").convert("RGBA")
    im_choices_raw = Image.open(ui_dir / "conversation-choices-zh-CN.png").convert("RGBA")
    im_calc_raw = Image.open(ui_dir / "conversation-zh-CN.png").convert("RGBA")
    im_wb_raw = Image.open(ui_dir / "workbench-zh-CN.png").convert("RGBA")
    im_ide_raw = Image.open(ui_dir / "ide-zh-CN.png").convert("RGBA")
    im_reading_raw = Image.open(ui_dir / "conversation-reading-zh-CN.png").convert("RGBA")

    im_dark_4a = Image.open(CACHE_DIR / "dark_codex_workbench.png").convert("RGBA")
    im_dark_4b = Image.open(CACHE_DIR / "dark_research_office.png").convert("RGBA")

    # Pre-load ALL 3 Real 30FPS Vector Stage Sequences into RAM!
    print("Loading 345 live vector stage frames into memory...")
    seq_dispatch_light = [
        np.asarray(Image.open(CAP_DIR / f"dispatch_light/f_{i:04d}.png").convert("RGB").resize((504, 409), Image.Resampling.LANCZOS))
        for i in range(105)
    ]
    seq_storm_dark_rgba = []
    # Pre-build rounded mask for 1440x728 dark storm stage card
    storm_w, storm_h = 1440, 728
    storm_mask = Image.new("L", (storm_w, storm_h), 0)
    ImageDraw.Draw(storm_mask).rounded_rectangle((0, 0, storm_w - 1, storm_h - 1), radius=36, fill=255)
    for i in range(120):
        im_s = Image.open(CAP_DIR / f"storm_dark/f_{i:04d}.png").convert("RGBA")
        im_s.putalpha(storm_mask)
        seq_storm_dark_rgba.append(im_s)

    seq_finale_rgba = [
        np.asarray(Image.open(CAP_DIR / f"finale_rgba/f_{i:04d}.png").convert("RGBA").resize((590, 372), Image.Resampling.LANCZOS))
        for i in range(120)
    ]

    # Seamless Pre-send Varin Window
    im_presend = im_varin_raw.copy()
    arr_pre = np.array(im_presend)
    arr_pre[75:1215, 4:1710, :3] = 243
    clean_col = arr_pre[1233:1281, 1050:1051, :3]
    arr_pre[1233:1281, 186:1020, :3] = clean_col
    arr_pre[1274:1304, 1330:1422, :3] = clean_col[0:1, 0:1, :]
    rpanel_bg = arr_pre[645, 1745, :3].copy()
    arr_pre[646:912, 1720:2212, :3] = rpanel_bg
    stage_presend = place_window_on_stage_np(Image.fromarray(arr_pre), light_stage_bg, dark=False)

    # Post-send Varin Window + Spotless Radio Circle Patch (x=182..218)
    arr_varin_post = np.array(im_varin_raw)
    unselected_radio_exact = arr_varin_post[941:975, 182:218, :3].copy()
    stage_varin_post = place_window_on_stage_np(im_varin_raw, light_stage_bg, dark=False)
    stage_varin_rgba = place_window_on_stage_np(im_varin_raw, light_stage_bg, dark=False, transparent_bg=True)

    stage_chart = place_window_on_stage_np(im_chart_raw, light_stage_bg, dark=False)

    arr_choices = np.array(im_choices_raw)
    unchecked_box_exact = arr_choices[844:878, 438:475, :3].copy()
    stage_choices = place_window_on_stage_np(im_choices_raw, light_stage_bg, dark=False)

    # Interactive Dual-Slider Calculator Stage (`conversation-zh-CN.png`)
    stage_calc = place_window_on_stage_np(im_calc_raw, light_stage_bg, dark=False)

    # Seamless Workbench + Transparent RGBA stages for 3D Multi-Window Spatial Array!
    im_wb_clean = im_wb_raw.copy()
    arr_wb = np.array(im_wb_clean)
    wb_comp_col = arr_wb[1246:1286, 1980:1981, :3]
    arr_wb[1246:1286, 1630:1960, :3] = wb_comp_col
    stage_wb_clean = place_window_on_stage_np(Image.fromarray(arr_wb), light_stage_bg, dark=False)
    stage_wb_raw = place_window_on_stage_np(im_wb_raw, light_stage_bg, dark=False)
    stage_wb_rgba = place_window_on_stage_np(im_wb_raw, light_stage_bg, dark=False, transparent_bg=True)

    stage_ide = place_window_on_stage_np(im_ide_raw, light_stage_bg, dark=False)
    stage_ide_rgba = place_window_on_stage_np(im_ide_raw, light_stage_bg, dark=False, transparent_bg=True)

    stage_reading = place_window_on_stage_np(im_reading_raw, light_stage_bg, dark=False)

    stage_dark_4a_rgba = place_window_on_stage_np(im_dark_4a, dark_stage_bg, dark=True, transparent_bg=True)
    stage_dark_4a_rgb_ref = place_window_on_stage_np(im_dark_4a, dark_stage_bg, dark=True, transparent_bg=False)
    stage_dark_4b_rgba = place_window_on_stage_np(im_dark_4b, dark_stage_bg, dark=True, transparent_bg=True)
    stage_dark_4b_rgb_ref = place_window_on_stage_np(im_dark_4b, dark_stage_bg, dark=True, transparent_bg=False)

    # Pre-rendered typing strips
    PROMPT_1 = "一起准备周五的发布吧。帮我把用户反馈、版本说明和官网的工作统筹起来。"
    f_comp = get_font(FONT_REG_PATH, 28)
    p1_im = Image.new("RGB", (1280, 48), tuple(int(v) for v in clean_col[10, 0]))
    dr_p1 = ImageDraw.Draw(p1_im)
    dr_p1.text((0, 4), PROMPT_1, font=f_comp, fill=(44, 48, 54))
    prompt1_np = np.asarray(p1_im)
    prompt1_cx = [dr_p1.textbbox((0, 0), PROMPT_1[:i], font=f_comp)[2] for i in range(len(PROMPT_1) + 1)]

    STEPIN_TXT = "暗色模式下的按钮焦点也顺手测一下"
    f_step = get_font(FONT_REG_PATH, 23)
    st_im = Image.new("RGB", (460, 40), tuple(int(v) for v in wb_comp_col[10, 0]))
    dr_st = ImageDraw.Draw(st_im)
    dr_st.text((0, 4), STEPIN_TXT, font=f_step, fill=(44, 48, 54))
    stepin_np = np.asarray(st_im)
    stepin_cx = [dr_st.textbbox((0, 0), STEPIN_TXT[:i], font=f_step)[2] for i in range(len(STEPIN_TXT) + 1)]

    blobs_np = [
        np.asarray(Image.open(CACHE_DIR / f"blob_{n}.png").convert("RGBA").resize((80, 80), Image.Resampling.LANCZOS))
        for n in ["lilac", "ochre", "blue", "mint"]
    ]
    cap_cards_pil = [Image.open(CACHE_DIR / f"cap_card_{i}.png").convert("RGBA") for i in range(8)]

    p_blade1 = [(-35,-19), (-11,-43), (44,-43), (57,-30), (2,-30), (-21,-7), (-21,26), (-35,12)]
    p_blade2 = [(35,19), (11,43), (-44,43), (-57,30), (-2,30), (21,7), (21,-26), (35,-12)]

    f_type_56 = get_font(FONT_BOLD_PATH, 56)

    chaos_anchors = [
        (110, 95, -6), (1440, 80, 5), (65, 690, 4), (1470, 680, -5),
        (460, 70, 3), (1040, 90, -4), (410, 745, -3), (1080, 740, 4),
        (80, 390, -5), (1490, 395, 6),
    ]

    # Helper to embed live 30FPS `dispatch_light` frame into `stage_varin_post` / `stage_presend` seamlessly!
    def paste_live_bot_stage(st_rgb: np.ndarray, stage_frame_idx: int):
        idx = max(0, min(len(seq_dispatch_light) - 1, stage_frame_idx))
        # Clear y=76..518, x=1715..2219 cleanly with #f3f3f3 (243,243,243), then paste 504x409 at y=92..501!
        st_rgb[WIN_OY + 76:WIN_OY + 518, WIN_OX + 1715:WIN_OX + 2219] = (243, 243, 243)
        st_rgb[WIN_OY + 92:WIN_OY + 501, WIN_OX + 1715:WIN_OX + 2219] = seq_dispatch_light[idx]

    # -----------------------------------------------------------------
    # ACT 1 (0.00 - 5.00s): Blade Collision -> 10-Window Storm -> Shockwave Super Agent!
    # -----------------------------------------------------------------
    def scene_act1_storm_morph(sec: float) -> np.ndarray:
        if sec < 0.91:
            bg = render_dynamic_dark_backdrop(out_dark_bg, sec * 2.4, boost=0.35)
            im = Image.fromarray(bg).convert("RGBA")
            ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            dr = ImageDraw.Draw(ov)
            p = ease_whip(sec / 0.34)
            off = (1.0 - p) * 230.0
            cx, cy = OUT_W // 2 - 110, OUT_H // 2
            sc = 1.48
            dr.polygon([(cx - off + x * sc, cy - off * 0.6 + y * sc) for x, y in p_blade1], fill=(244, 246, 250, int(255 * p)))
            dr.polygon([(cx + off + x * sc, cy + off * 0.6 + y * sc) for x, y in p_blade2], fill=(122, 167, 239, int(255 * p)))
            if sec > 0.14:
                pt = ease_whip((sec - 0.14) / 0.28)
                f_w = get_font(FONT_BOLD_PATH, 80)
                dr.text((int(cx + 98 + (1.0 - pt) * 45), int(cy - 54)), "Varin", font=f_w, fill=(246, 248, 252, int(255 * pt)))
            im.alpha_composite(ov)
            return zoom_scale_frame(np.asarray(im.convert("RGB")), 1.0 + 0.18 * (sec / 0.91))

        out_arr = out_light_bg.copy()
        imp_p = clamp01((sec - 2.68) / 0.38)
        if imp_p < 0.99:
            e_imp = ease_in_quad(imp_p)
            for wi, (wx, wy, _ang) in enumerate(chaos_anchors):
                pop_p = ease_spring((sec - 0.92 - wi * 0.135) / 0.28)
                if pop_p <= 0.01:
                    continue
                drift_x = math.sin(sec * 3.8 + wi * 1.3) * 15.0
                drift_y = math.cos(sec * 3.4 + wi * 1.7) * 12.0
                cur_cx = (wx + 172 + drift_x) * (1.0 - e_imp) + (OUT_W * 0.5) * e_imp
                cur_cy = (wy + 86 + drift_y) * (1.0 - e_imp) + (OUT_H * 0.5) * e_imp
                sc = pop_p * (1.0 - 0.84 * e_imp)
                spr = chaos_windows[wi]
                if sc < 0.96:
                    nw, nh = max(16, int(spr.shape[1] * sc)), max(16, int(spr.shape[0] * sc))
                    spr_s = cv2.resize(spr, (nw, nh), interpolation=cv2.INTER_AREA)
                else:
                    spr_s = spr
                blit_rgba_np(out_arr, spr_s, int(cur_cx - spr_s.shape[1] // 2), int(cur_cy - spr_s.shape[0] // 2),
                             opacity=(1.0 - e_imp * 0.85))

        im = Image.fromarray(out_arr).convert("RGBA")
        ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)

        if sec < 2.86:
            p_in = ease_spring((sec - 0.91) / 0.28)
            split_out = ease_in_quad((sec - 2.66) / 0.20) if sec > 2.66 else 0.0
            sc_txt = (0.90 + 0.10 * p_in + 0.06 * ((sec - 0.91) / 1.7)) * (1.0 + 0.35 * split_out)
            f_dyn = get_font(FONT_BOLD_PATH, int(64 * sc_txt))
            txt = "还在十个窗口间来回救火？"
            tw = dr.textbbox((0, 0), txt, font=f_dyn)[2]
            al = int(255 * (1.0 - split_out))
            dr.rounded_rectangle(((OUT_W - tw) // 2 - 36, 472, (OUT_W + tw) // 2 + 36, 598),
                                 radius=32, fill=(255, 255, 255, int(230 * (1.0 - split_out))),
                                 outline=(205, 214, 228, al), width=2)
            dr.text(((OUT_W - tw) // 2, int(492 - (sc_txt - 1.0) * 30)), txt, font=f_dyn, fill=(28, 35, 40, al))

        if 2.68 <= sec <= 3.30:
            sp = (sec - 2.68) / 0.62
            rad = int(40 + ease_out_cubic(sp) * 880)
            al_r = int(225 * (1.0 - sp))
            dr.ellipse((OUT_W // 2 - rad, OUT_H // 2 - rad, OUT_W // 2 + rad, OUT_H // 2 + rad),
                       outline=(68, 112, 186, al_r), width=max(2, int(11 * (1.0 - sp))))

        if sec >= 2.78:
            drift_z = 1.0 + 0.055 * ((sec - 2.78) / 2.1)
            f_sa = get_font(FONT_BOLD_PATH, int(68 * drift_z))
            t1, t2, t3 = "交给  ", "Super Agent", "  带队推进"
            w1 = dr.textbbox((0, 0), t1, font=f_sa)[2]
            w2 = dr.textbbox((0, 0), t2, font=f_sa)[2]
            w3 = dr.textbbox((0, 0), t3, font=f_sa)[2]
            tx = (OUT_W - (w1 + w2 + w3)) // 2
            ty = int(438 + (1.0 - clamp01((sec - 2.78) / 0.20)) * 28)
            dr.rounded_rectangle((tx + w1 - 14, ty - 10, tx + w1 + w2 + 14, ty + int(86 * drift_z) + 10),
                                 radius=24, fill=(62, 99, 158, 36), outline=(62, 99, 158, 128), width=2)
            im.alpha_composite(ov)
            ov2 = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            td = ImageDraw.Draw(ov2)
            td.text((tx, ty), t1, font=f_sa, fill=(32, 39, 42, 255))
            td.text((tx + w1, ty), t2, font=f_sa, fill=(50, 88, 152, 255))
            td.text((tx + w1 + w2, ty), t3, font=f_sa, fill=(32, 39, 42, 255))
            im.alpha_composite(ov2)

            res = np.asarray(im.convert("RGB")).copy()
            gap = 32
            sx0 = (OUT_W - (4 * 80 + 3 * gap)) // 2
            for bi, b_arr in enumerate(blobs_np):
                bp = clamp01((sec - 2.84 - bi * 0.06) / 0.22)
                if bp > 0.01:
                    bob = math.sin((sec - 2.84) * 8.6 + bi * 1.1) * 10.5
                    bx = int(OUT_W * 0.5 * (1.0 - ease_whip(bp)) + (sx0 + bi * (80 + gap)) * ease_whip(bp))
                    by = int(OUT_H * 0.5 * (1.0 - ease_whip(bp)) + (585 + bob) * ease_whip(bp))
                    blit_rgba_np(res, b_arr, bx, by, opacity=bp)
            return res

        im.alpha_composite(ov)
        return np.asarray(im.convert("RGB"))

    # -----------------------------------------------------------------
    # ACT 2A (4.70 - 9.20s): Native Input + Glowing Bezier Particle Beam to Bot Stage!
    # -----------------------------------------------------------------
    def scene_act2a_input(sec: float) -> np.ndarray:
        st = stage_presend.copy()
        paste_live_bot_stage(st, 0)  # Idle attentive Varin waiting in right stage!

        if sec >= 5.90:
            c_idx = min(len(PROMPT_1), int((sec - 5.90) / (1.95 / len(PROMPT_1))) + 1)
            px_w = prompt1_cx[c_idx]
            if px_w > 0:
                st[WIN_OY + 1232:WIN_OY + 1280, WIN_OX + 190:WIN_OX + 190 + px_w] = prompt1_np[:, :px_w]
        else:
            px_w = 0

        if sec < 8.15 and (int(sec * 6.0) % 2 == 0 or (5.90 <= sec <= 7.90)):
            cx_b = WIN_OX + 190 + px_w + 4
            st[WIN_OY + 1238:WIN_OY + 1272, cx_b:cx_b + 4] = (62, 99, 158)

        send_cx, send_cy = WIN_OX + 1492, WIN_OY + 1345
        if sec >= 7.75:
            cp = ease_whip((sec - 7.75) / 0.40)
            cur_x = int(send_cx + (1.0 - cp) * 200 - 6)
            cur_y = int(send_cy + (1.0 - cp) * 120 - 4)
            if sec >= 8.18:
                rp = clamp01((sec - 8.18) / 0.45)
                cv2.circle(st, (send_cx, send_cy), int(34 + rp * 82), (75, 125, 225), max(2, int(6 * (1.0 - rp))), lineType=cv2.LINE_AA)
            blit_rgba_np(st, CURSOR_SPRITE, cur_x, cur_y, 1.0)

        # UPGRADE #3: Glowing Bezier Particle Stream shooting from Send Button (1492,1345) into Varin's Bot Stage (1966,310)!
        if sec >= 8.20:
            beam_u = (sec - 8.20) / 0.72
            draw_glowing_bezier_stream(
                st,
                (WIN_OX + 1492, WIN_OY + 1345),
                (WIN_OX + 1966, WIN_OY + 310),
                (WIN_OX + 1380, WIN_OY + 620),
                head_u=beam_u * 1.35, tail_len=0.52, color_rgb=(72, 152, 255), thickness=6
            )

        if sec < 5.55:
            u = ease_out_cubic((sec - 4.70) / 0.85)
            fx, fy = 1110.0, 705.0 + 40.0 * (1.0 - u)
            zm = 0.95 + 0.12 * u
            yaw, pitch, roll = 0.0, (1.0 - u) * 4.0, 0.0
        elif sec < 5.95:
            u = ease_whip((sec - 5.55) / 0.40)
            fx = 1110.0 + (780.0 - 1110.0) * u
            fy = 705.0 + (1260.0 - 705.0) * u
            zm = 1.07 + (1.94 - 1.07) * u
            yaw, pitch, roll = -9.5 * u, 6.2 * u, -2.6 * u
        elif sec < 7.75:
            u = (sec - 5.95) / 1.80
            fx = 780.0 + 95.0 * u
            fy = 1260.0 + 10.0 * u
            zm = 1.94 + 0.16 * u
            yaw, pitch, roll = -9.5 + 3.0 * u, 6.2 - 0.8 * u, -2.6 + 0.6 * u
        elif sec < 8.12:
            u = ease_whip((sec - 7.75) / 0.37)
            fx = 875.0 + (1375.0 - 875.0) * u
            fy = 1270.0 + (1325.0 - 1270.0) * u
            zm = 2.10 + (3.10 - 2.10) * u
            yaw = -6.5 + (7.5 - (-6.5)) * u
            pitch, roll = 5.4, -2.0 + 3.8 * u
        else:
            # Camera tracks the glowing Bezier comet UPWARD into the Live Bot Stage!
            up_u = ease_in_out_whip((sec - 8.22) / 0.85) if sec > 8.22 else 0.0
            fx = 1375.0 + (1860.0 - 1375.0) * up_u
            fy = 1325.0 + (440.0 - 1325.0) * up_u
            zm = 3.10 + (1.95 - 3.10) * up_u
            yaw, pitch, roll = 7.5 + 1.5 * up_u, 5.4 - 1.8 * up_u, 1.8

        frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
        return add_corner_pill(frame, "一句话交办跨模块任务", "#7aa7ef", (sec - 5.80) / 0.25, pos=("left", "top"))

    # -----------------------------------------------------------------
    # ACT 2B (8.95 - 16.50s): LIVE Vector Bot Stage Card Throws + Whip Left + Spotless Radio Click!
    # -----------------------------------------------------------------
    def scene_act2b_live_stage_and_radio(sec: float) -> np.ndarray:
        lt = sec - 8.95
        st = stage_varin_post.copy()
        rbg = tuple(int(v) for v in rpanel_bg)

        # UPGRADE #1A: Live 30FPS Official Vector Stage (`dispatch_light` throwing cards left & right!)
        stage_f = int(round(lt * 30.0))
        paste_live_bot_stage(st, stage_f)

        spring_slide_block(st, stage_varin_post, 310, 1660, 112, 224, lt / 0.28)
        spring_slide_block(st, stage_varin_post, 310, 1660, 270, 382, (lt - 0.35) / 0.35)
        spring_slide_block(st, stage_varin_post, 310, 1660, 430, 530, (lt - 0.75) / 0.38)
        spring_slide_block(st, stage_varin_post, 1725, 2210, 715, 815, (lt - 0.65) / 0.35, bg_rgb=rbg)
        spring_slide_block(st, stage_varin_post, 1725, 2210, 825, 925, (lt - 1.15) / 0.35, bg_rgb=rbg)

        if lt > 1.35:
            rad_p = 6 + int(3 * (0.5 + 0.5 * math.sin(sec * 10.0)))
            for gy in [783, 894]:
                cv2.circle(st, (WIN_OX + 1777, WIN_OY + gy), rad_p, (140, 205, 115), -1, lineType=cv2.LINE_AA)
                cv2.circle(st, (WIN_OX + 1777, WIN_OY + gy), 5, (85, 158, 58), -1, lineType=cv2.LINE_AA)

        spring_slide_block(st, stage_varin_post, 175, 1660, 566, 665, (lt - 3.70) / 0.38)
        spring_slide_block(st, stage_varin_post, 175, 1660, 692, 775, (lt - 4.05) / 0.38)
        spring_slide_block(st, stage_varin_post, 175, 1660, 800, 1050, (lt - 4.40) / 0.40)

        click_lt = 15.00 - 8.95  # 6.05s
        if 4.40 <= lt < click_lt:
            st[WIN_OY + 871:WIN_OY + 905, WIN_OX + 182:WIN_OX + 218] = unselected_radio_exact

        if lt >= 5.15:
            cp = ease_whip((lt - 5.15) / 0.80)
            cur_x = int(WIN_OX + 199 + (1.0 - cp) * 240)
            cur_y = int(WIN_OY + 888 + (1.0 - cp) * 120)
            if lt >= click_lt:
                rp = clamp01((lt - click_lt) / 0.42)
                cv2.circle(st, (WIN_OX + 199, WIN_OY + 888), int(18 + rp * 36), (75, 111, 172), max(1, int(4 * (1.0 - rp))), lineType=cv2.LINE_AA)
            blit_rgba_np(st, CURSOR_SPRITE, cur_x, cur_y, 1.0)

        if lt < 3.70:
            u = lt / 3.70
            fx = 1865.0 - 45.0 * u
            fy = 435.0 + 115.0 * u
            zm = 1.98 + 0.18 * u
            yaw, pitch, roll = 9.2 - 2.0 * u, 3.6 + 0.6 * u, 1.8 - 0.5 * u
        elif lt < 4.02:
            u = ease_in_out_whip((lt - 3.70) / 0.32)
            fx = 1820.0 + (560.0 - 1820.0) * u
            fy = 550.0 + (825.0 - 550.0) * u
            zm = 2.16 + (1.92 - 2.16) * u
            yaw = 7.2 + (-8.2 - 7.2) * u
            pitch, roll = 4.2, 1.3 + (-2.0 - 1.3) * u
        else:
            u = (lt - 4.02) / (7.55 - 4.02)
            scroll_exit = ease_in_quad((lt - 6.95) / 0.50) if lt > 6.95 else 0.0
            fx = 560.0 - 40.0 * u + 300.0 * scroll_exit
            fy = 825.0 + 70.0 * u + 360.0 * scroll_exit
            zm = 1.92 + 0.18 * u - 0.42 * scroll_exit
            yaw, pitch, roll = -8.2 + 2.0 * u, 4.2, -2.0 * (1.0 - scroll_exit)

        frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
        if lt < 3.82:
            return add_corner_pill(frame, "Super Agent 实机舞台 · 自动派发多路负责人", "#8ce071", lt / 0.25, pos=("left", "top"))
        return add_corner_pill(frame, "实时流式推进 · 关键分歧才问你", "#7aa7ef", (lt - 3.85) / 0.25, pos=("right", "top"))

    # -----------------------------------------------------------------
    # ACT 2C (16.25 - 20.12s): Feedback Chart (`conversation-chart-zh-CN.png`)
    # -----------------------------------------------------------------
    def scene_act2c_chart(sec: float) -> np.ndarray:
        lt = sec - 16.25
        st = stage_chart.copy()
        spring_slide_block(st, stage_chart, 350, 1850, 275, 442, lt / 0.35)
        card_bg = (250, 250, 250)
        for by0, by1, bx0, bx1, b_dly in [
            (592, 625, 693, 1445, 0.32),
            (640, 673, 693, 1208, 0.48),
            (688, 721, 693, 1130, 0.64),
            (736, 769, 693, 972,  0.80),
        ]:
            bp = ease_whip((lt - b_dly) / 0.60)
            cur_bx = bx0 + int((bx1 - bx0) * bp)
            if cur_bx < bx1:
                st[WIN_OY + by0:WIN_OY + by1, WIN_OX + cur_bx:WIN_OX + bx1] = card_bg
        spring_slide_block(st, stage_chart, 350, 1850, 885, 1035, (lt - 1.25) / 0.42)

        u = lt / 3.80
        enter_u = ease_out_cubic(lt / 0.45)
        fx = 980.0 + 145.0 * u
        fy = (380.0 + (655.0 - 380.0) * enter_u) + 45.0 * u
        zm = 1.48 + 0.36 * enter_u + 0.15 * u
        yaw, pitch, roll = 7.5 - 3.0 * u, 4.2, -1.6 + 0.8 * u
        frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
        return add_corner_pill(frame, "同一会话持续深挖 · 自动生成对比图表", "#7aa7ef", lt / 0.25, pos=("left", "top"))

    # -----------------------------------------------------------------
    # ACT 2D (19.90 - 23.75s): Multi-Select Choices (`conversation-choices-zh-CN.png`)
    # -----------------------------------------------------------------
    def scene_act2d_choices(sec: float) -> np.ndarray:
        lt = sec - 19.90
        st = stage_choices.copy()
        spring_slide_block(st, stage_choices, 380, 1800, 420, 650, lt / 0.35)

        if lt < 1.46:  # sec < 21.36
            st[WIN_OY + 775:WIN_OY + 809, WIN_OX + 438:WIN_OX + 475] = unchecked_box_exact

        if lt < 1.85:
            cp = ease_whip((lt - 0.70) / 0.68)
            cur_x = int(WIN_OX + 455 + (1.0 - cp) * 220)
            cur_y = int(WIN_OY + 792 + (1.0 - cp) * 110)
            if lt >= 1.46:
                rp = clamp01((lt - 1.46) / 0.30)
                cv2.circle(st, (WIN_OX + 455, WIN_OY + 792), int(18 + rp * 32), (75, 111, 172), 3, lineType=cv2.LINE_AA)
        else:
            gp = ease_in_out_whip((lt - 1.85) / 0.55)
            cur_x = int(WIN_OX + 455 + (545 - 455) * gp)
            cur_y = int(WIN_OY + 792 + (995 - 792) * gp)
            if lt >= 2.60:  # sec >= 22.50
                rp = clamp01((lt - 2.60) / 0.38)
                cv2.circle(st, (WIN_OX + 545, WIN_OY + 995), int(22 + rp * 48), (75, 111, 172), 3, lineType=cv2.LINE_AA)
        blit_rgba_np(st, CURSOR_SPRITE, cur_x, cur_y, 1.0)

        u = lt / 3.70
        fx = 760.0 - 80.0 * u
        fy = 760.0 + 145.0 * u
        zm = 1.78 + 0.36 * u
        yaw, pitch, roll = -7.5 + 2.5 * u, 4.8, -1.8 + 0.6 * u
        frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
        return add_corner_pill(frame, "多选确认方向 · 一键生成完整稿", "#7aa7ef", lt / 0.25, pos=("right", "top"))

    # -----------------------------------------------------------------
    # ACT 2E (23.52 - 27.40s): NEW Official UI! Live Interactive Dual-Slider Calculator (`conversation-zh-CN.png`)
    # -----------------------------------------------------------------
    f_kpi_big = get_font(FONT_REG_PATH, 68)
    f_kpi_unit = get_font(FONT_REG_PATH, 25)
    f_kpi_sub = get_font(FONT_REG_PATH, 19)
    f_kpi_val = get_font(FONT_BOLD_PATH, 20)

    def scene_act2e_live_calculator(sec: float) -> np.ndarray:
        lt = sec - 23.52  # 0.0 .. 3.88s
        st = stage_calc.copy()
        # Drag ratio smoothly from 60% (lt <= 1.25) to 80% (lt >= 2.85)!
        drag_p = ease_in_out_whip((lt - 1.25) / 1.60)
        ratio = 0.60 + 0.20 * drag_p

        if drag_p > 0.002:
            bg_c = (243, 243, 243)
            # Clear dynamic regions cleanly on `#f3f3f3`
            st[WIN_OY + 598:WIN_OY + 712, WIN_OX + 422:WIN_OX + 690] = bg_c      # Big KPI + subtext
            st[WIN_OY + 626:WIN_OY + 656, WIN_OX + 1655:WIN_OX + 1800] = bg_c    # Bar 2 right label
            st[WIN_OY + 668:WIN_OY + 688, WIN_OX + 1021:WIN_OX + 1794] = (230, 230, 230)  # Bar 2 gray track
            st[WIN_OY + 800:WIN_OY + 825, WIN_OX + 1025:WIN_OX + 1086] = bg_c    # '60%' label
            st[WIN_OY + 842:WIN_OY + 876, WIN_OX + 420:WIN_OX + 1086] = bg_c     # Slider 1 track+thumb
            st[WIN_OY + 950:WIN_OY + 978, WIN_OX + 422:WIN_OX + 760] = bg_c      # Bottom summary

            saved_h = 37.5 * ratio              # 22.5 -> 30.0
            after_h = 45.0 - saved_h            # 22.5 -> 15.0
            red_pct = int(round(saved_h / 45.0 * 100))  # 50% -> 67%
            docs_n = int(round(90 * ratio))     # 54 -> 72
            chk_h = docs_n * (5.0 / 60.0)       # 4.5 -> 6.0

            # Draw Bar 2 blue fill
            bar2_w = int(round((after_h / 45.0) * (1794 - 1021)))
            cv2.rectangle(st, (WIN_OX + 1021, WIN_OY + 669), (WIN_OX + 1021 + bar2_w, WIN_OY + 686), (75, 111, 172), -1)

            # Draw Slider 1 track + active blue segment + circular thumb
            sl_x0, sl_x1, sl_y = WIN_OX + 426, WIN_OX + 1076, WIN_OY + 859
            th_x = int(round(sl_x0 + ratio * (sl_x1 - sl_x0)))
            cv2.line(st, (sl_x0, sl_y), (sl_x1, sl_y), (220, 222, 226), 5, cv2.LINE_AA)
            cv2.line(st, (sl_x0, sl_y), (th_x, sl_y), (75, 111, 172), 5, cv2.LINE_AA)
            cv2.circle(st, (th_x, sl_y), 11, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(st, (th_x, sl_y), 11, (75, 111, 172), 2, cv2.LINE_AA)
            cv2.circle(st, (th_x, sl_y), 6, (75, 111, 172), -1, cv2.LINE_AA)

            # Render crisp updated numbers onto patch via PIL
            patch = Image.fromarray(st[WIN_OY + 595:WIN_OY + 982, WIN_OX + 420:WIN_OX + 1805])
            dr = ImageDraw.Draw(patch)
            s_num = f"{saved_h:.1f}"
            dr.text((6, 0), s_num, font=f_kpi_big, fill=(32, 36, 40))
            wn = dr.textbbox((0, 0), s_num, font=f_kpi_big)[2]
            dr.text((6 + wn + 10, 36), "小时", font=f_kpi_unit, fill=(115, 120, 126))
            dr.text((6, 90), f"人工投入比原来减少 {red_pct}%", font=f_kpi_sub, fill=(115, 120, 126))

            lbl_b2 = f"{after_h:.1f} 小时 / 周"
            wb2 = dr.textbbox((0, 0), lbl_b2, font=f_kpi_sub)[2]
            dr.text((1792 - 420 - wb2, 33), lbl_b2, font=f_kpi_sub, fill=(72, 76, 82))

            lbl_pct = f"{int(round(ratio * 100))}%"
            wpct = dr.textbbox((0, 0), lbl_pct, font=f_kpi_val)[2]
            dr.text((1078 - 420 - wpct, 206), lbl_pct, font=f_kpi_val, fill=(38, 42, 48))

            dr.text((6, 357), f"每周交办 {docs_n} 份，人工检查约 {chk_h:.1f} 小时。", font=f_kpi_sub, fill=(115, 120, 126))
            st[WIN_OY + 595:WIN_OY + 982, WIN_OX + 420:WIN_OX + 1805] = np.asarray(patch)
        else:
            th_x, sl_y = WIN_OX + 816, WIN_OY + 859

        # Cursor glides onto slider thumb and drags it live!
        cp = ease_whip((lt - 0.55) / 0.65)
        cur_x = int(th_x + (1.0 - cp) * 180)
        cur_y = int(sl_y + (1.0 - cp) * 95)
        if 1.25 <= lt <= 2.95:
            cv2.circle(st, (th_x, sl_y), 22, (75, 111, 172), 2, cv2.LINE_AA)
        blit_rgba_np(st, CURSOR_SPRITE, cur_x, cur_y, 1.0)

        u = lt / 3.85
        fx = 860.0 + 130.0 * u
        fy = 735.0 + 35.0 * u
        zm = 1.72 + 0.24 * u
        yaw, pitch, roll = 7.8 - 4.0 * u, 4.6, -1.6 + 0.8 * u
        frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
        return add_corner_pill(frame, "对话内嵌原生交互组件 · 拖动滑块实时测算", "#7aa7ef", lt / 0.25, pos=("right", "top"))

    # -----------------------------------------------------------------
    # ACT 3A (27.18 - 31.95s): SPECTACLE UPGRADE #2 — 3D Multi-Window Spatial Array + Bezier Streams!
    # -----------------------------------------------------------------
    def scene_act3a_multi_window_array(sec: float) -> np.ndarray:
        lt = sec - 27.18  # 0.0 .. 4.77s
        p_in = ease_spring(lt / 0.55)
        dive_p = ease_in_out_whip((lt - 3.95) / 0.78) if lt > 3.95 else 0.0

        canvas = out_light_bg.copy()
        sweep = lt / 4.75

        # Left Wing: Conversation Window (`varin-zh-CN`) tilted inward (+20 deg yaw)
        if dive_p < 0.96:
            cx_l = 410.0 - 520.0 * dive_p - (1.0 - p_in) * 180.0
            cy_l = 575.0 + 40.0 * dive_p
            zm_l = (0.52 + 0.03 * sweep) * (1.0 - 0.25 * dive_p)
            canvas = project_3d(stage_varin_rgba, 1110.0, 705.0, zm_l,
                                yaw_deg=20.0 - 3.0 * sweep, pitch_deg=4.5, roll_deg=-2.0,
                                custom_bg_1080=canvas, screen_cx=cx_l, screen_cy=cy_l)

            # Right Wing: IDE Window (`ide-zh-CN`) tilted inward (-20 deg yaw)
            cx_r = 1510.0 + 520.0 * dive_p + (1.0 - p_in) * 180.0
            cy_r = 575.0 + 40.0 * dive_p
            canvas = project_3d(stage_ide_rgba, 1110.0, 705.0, zm_l,
                                yaw_deg=-20.0 + 3.0 * sweep, pitch_deg=4.5, roll_deg=2.0,
                                custom_bg_1080=canvas, screen_cx=cx_r, screen_cy=cy_r)

        # Center Hero: Workbench Window (`workbench-zh-CN`) — dives smoothly to fill screen at end!
        cx_c = OUT_W * 0.5 + 140.0 * dive_p
        cy_c = 585.0 - 45.0 * dive_p + (1.0 - p_in) * 65.0
        zm_c = 0.68 + 0.06 * sweep + (1.68 - 0.74) * dive_p
        yaw_c = -4.0 + 12.0 * dive_p + math.sin(lt * 1.6) * 2.5 * (1.0 - dive_p)
        canvas = project_3d(stage_wb_rgba, 1110.0 + 430.0 * dive_p, 705.0 - 170.0 * dive_p, zm_c,
                            yaw_deg=yaw_c, pitch_deg=4.0, roll_deg=-1.8 * dive_p,
                            custom_bg_1080=canvas, screen_cx=cx_c, screen_cy=cy_c)

        # Glowing Bezier Data Streams linking Conversation -> Workbench -> IDE!
        if 0.35 <= lt <= 4.15:
            bu1 = ((lt - 0.35) * 1.15) % 1.45
            bu2 = ((lt - 0.65) * 1.15) % 1.45
            draw_glowing_bezier_stream(canvas, (430, 520), (940, 495), (685, 340), bu1, tail_len=0.48, color_rgb=(68, 142, 248), thickness=4)
            if lt >= 0.65:
                draw_glowing_bezier_stream(canvas, (980, 495), (1490, 520), (1235, 340), bu2, tail_len=0.48, color_rgb=(110, 205, 130), thickness=4)

        # Floating Hero Headline Banner at top
        if dive_p < 0.92:
            al = int(255 * clamp01(lt / 0.30) * (1.0 - dive_p))
            im = Image.fromarray(canvas).convert("RGBA")
            ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            dr = ImageDraw.Draw(ov)
            f_h = get_font(FONT_BOLD_PATH, 50)
            t1, t2 = "多视图同场推进 · ", "成员直连不黑盒"
            w1 = dr.textbbox((0, 0), t1, font=f_h)[2]
            w2 = dr.textbbox((0, 0), t2, font=f_h)[2]
            tx = (OUT_W - (w1 + w2)) // 2
            ty = int(64 - dive_p * 50)
            dr.rounded_rectangle((tx - 28, ty - 10, tx + w1 + w2 + 28, ty + 74),
                                 radius=26, fill=(255, 255, 255, int(225 * (1.0 - dive_p))),
                                 outline=(198, 212, 234, al), width=2)
            dr.text((tx, ty), t1, font=f_h, fill=(32, 39, 42, al))
            dr.text((tx + w1, ty), t2, font=f_h, fill=(50, 90, 158, al))
            im.alpha_composite(ov)
            return np.asarray(im.convert("RGB"))
        return canvas

    # -----------------------------------------------------------------
    # ACT 3B (31.82 - 42.85s): Workbench Direct Collab & Step-in -> In-Window IDE Build Pass!
    # -----------------------------------------------------------------
    def scene_act3b_wb_and_ide(sec: float) -> np.ndarray:
        lt = sec - 31.82  # 0.0 .. 11.03s
        if sec < 39.55:
            st = stage_wb_clean.copy()
            wb_rbg = (243, 243, 243)
            spring_slide_block(st, stage_wb_clean, 315, 1555, 535, 735, (lt - 0.20) / 0.40)
            spring_slide_block(st, stage_wb_clean, 1600, 2135, 175, 460, (lt - 0.40) / 0.38, bg_rgb=wb_rbg)
            spring_slide_block(st, stage_wb_clean, 1600, 2135, 495, 805, (lt - 1.85) / 0.40, bg_rgb=wb_rbg)
            spring_slide_block(st, stage_wb_clean, 315, 1555, 748, 845, (lt - 2.20) / 0.40)

            # Live step-in typing (sec 35.80 -> 37.65, lt 3.98 -> 5.83)
            if lt >= 3.98:
                c_idx = min(len(STEPIN_TXT), int((lt - 3.98) / (1.85 / len(STEPIN_TXT))) + 1)
                sw = stepin_cx[c_idx]
                if sw > 0:
                    st[WIN_OY + 1246:WIN_OY + 1286, WIN_OX + 1632:WIN_OX + 1632 + sw] = stepin_np[:, :sw]
                if lt < 6.36 and (int(sec * 6.0) % 2 == 0 or lt < 5.85):
                    cbx = WIN_OX + 1632 + sw + 3
                    st[WIN_OY + 1251:WIN_OY + 1280, cbx:cbx + 3] = (62, 99, 158)

            if 5.85 <= lt < 6.80:
                cp = ease_whip((lt - 5.85) / 0.42)
                cur_x = int(WIN_OX + 2086 - (1.0 - cp) * 140)
                cur_y = int(WIN_OY + 1326 - (1.0 - cp) * 85)
                if lt >= 6.36:  # sec 38.18
                    rp = clamp01((lt - 6.36) / 0.40)
                    cv2.circle(st, (WIN_OX + 2088, WIN_OY + 1326), int(22 + rp * 44), (75, 111, 172), 3, lineType=cv2.LINE_AA)
                blit_rgba_np(st, CURSOR_SPRITE, cur_x, cur_y, 1.0)
            elif lt >= 6.80:
                cp = ease_whip((lt - 6.90) / 0.52)
                cur_x = int(WIN_OX + 218 + (1.0 - cp) * 340)
                cur_y = int(WIN_OY + 38 + (1.0 - cp) * 240)
                if lt >= 7.50:  # sec 39.32
                    cv2.circle(st, (WIN_OX + 218, WIN_OY + 38), int(18 + (lt - 7.50) * 160), (75, 111, 172), 3, lineType=cv2.LINE_AA)
                blit_rgba_np(st, CURSOR_SPRITE, cur_x, cur_y, 1.0)

            if lt < 3.55:
                u = lt / 3.55
                fx = 1540.0 + 55.0 * u
                fy = 535.0 + 45.0 * u
                zm = 1.68 + 0.18 * u
                yaw, pitch, roll = 8.0 - 1.5 * u, 3.8, -1.8 + 0.4 * u
            elif lt < 3.88:
                u = ease_in_out_whip((lt - 3.55) / 0.33)
                fx = 1595.0 + (1805.0 - 1595.0) * u
                fy = 580.0 + (1175.0 - 580.0) * u
                zm = 1.86 + (2.34 - 1.86) * u
                yaw, pitch, roll = 6.5 + 2.5 * u, 3.8 + 1.7 * u, -1.4 + 3.0 * u
            elif lt < 6.80:
                u = (lt - 3.88) / 2.92
                fx, fy, zm = 1805.0 + 25.0 * u, 1175.0, 2.34 + 0.08 * u
                yaw, pitch, roll = 9.0, 5.5, 1.6
            else:
                u = ease_in_out_whip((lt - 6.80) / 0.55)
                fx = 1830.0 + (540.0 - 1830.0) * u
                fy = 1175.0 + (280.0 - 1175.0) * u
                zm = 2.42 + (1.72 - 2.42) * u
                yaw, pitch, roll = 9.0 + (-6.5 - 9.0) * u, 5.5 - 2.0 * u, 1.6 - 3.0 * u

            frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
            if lt < 3.70:
                return add_corner_pill(frame, "成员直连互发 · 代码改动逐轮留档", "#8ce071", lt / 0.25, pos=("left", "top"))
            elif lt < 6.80:
                return add_corner_pill(frame, "定向插话 · 随时向指定成员补充要求", "#f4c56b", (lt - 3.75) / 0.25, pos=("left", "top"))
            return frame
        else:
            # 39.55 - 42.85s: Seamless horizontal pane wipe into IDE + `$ bun run build`!
            it = sec - 39.55
            st = stage_ide.copy()
            if it < 0.34:
                wp = ease_in_out_whip(it / 0.34)
                split_x = WIN_OX + int(2220 * wp)
                st[WIN_OY + 74:WIN_OY + 1408, split_x:WIN_OX + 2218] = stage_wb_raw[WIN_OY + 74:WIN_OY + 1408, split_x:WIN_OX + 2218]

            term_bg = (243, 243, 243)
            if it < 0.70:
                st[WIN_OY + 1268:WIN_OY + 1372, WIN_OX + 352:WIN_OX + 620] = term_bg
            elif it < 1.60:
                tp = (it - 0.70) / 0.90
                rx = 352 + int((558 - 352) * tp)
                st[WIN_OY + 1268:WIN_OY + 1298, WIN_OX + rx:WIN_OX + 565] = term_bg
                st[WIN_OY + 1302:WIN_OY + 1372, WIN_OX + 330:WIN_OX + 620] = term_bg
            elif it < 2.04:
                st[WIN_OY + 1302:WIN_OY + 1372, WIN_OX + 330:WIN_OX + 620] = term_bg
            else:
                gp = clamp01((it - 2.04) / 0.25)
                cv2.rectangle(st, (WIN_OX + 340, WIN_OY + 1300), (WIN_OX + 515, WIN_OY + 1340),
                              (95, 165, 65), thickness=max(2, int(3 * gp)), lineType=cv2.LINE_AA)

            dive_u = ease_whip((it - 0.20) / 0.45)
            drift_u = it / 3.25
            fx = 540.0 + (650.0 - 540.0) * dive_u + 45.0 * drift_u
            fy = 280.0 + (1155.0 - 280.0) * dive_u
            zm = 1.72 + (2.25 - 1.72) * dive_u + 0.14 * drift_u
            yaw, pitch, roll = -6.5 - 1.5 * dive_u + 1.8 * drift_u, 3.5 + 2.0 * dive_u, -1.4 - 0.6 * dive_u
            frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
            return add_corner_pill(frame, "同一会话直切内置 IDE · 7 门语言 LSP 秒级构建", "#8ce071", (it - 0.30) / 0.25, pos=("right", "top"))

    # -----------------------------------------------------------------
    # ACT 3C (42.73 - 45.50s): NEW Official UI! Side-by-Side Comparison (`conversation-reading-zh-CN.png`)
    # -----------------------------------------------------------------
    def scene_act3c_reading_compare(sec: float) -> np.ndarray:
        lt = sec - 42.73  # 0.0 .. 2.77s
        st = stage_reading.copy()
        spring_slide_block(st, stage_reading, 415, 1805, 625, 815, (lt - 0.35) / 0.42)
        u = lt / 2.75
        fx = 1080.0 + 60.0 * u
        fy = 545.0 + 95.0 * u
        zm = 1.54 + 0.22 * u
        yaw, pitch, roll = 6.5 - 4.0 * u, 4.2, -1.2 + 0.6 * u
        frame = project_3d(st, fx, fy, zm, yaw, pitch, roll)
        return add_corner_pill(frame, "对话、工作台、IDE 无缝串联 · 随时深入细节", "#7aa7ef", lt / 0.25, pos=("left", "top"))

    # -----------------------------------------------------------------
    # Fast Kinetic Typewriter Helper (supports both Light and Dark themes!)
    # -----------------------------------------------------------------
    def scene_typewriter_fast(local_t: float, prefix: str, highlight: str, dark_theme: bool = False) -> np.ndarray:
        base_bg = render_dynamic_dark_backdrop(out_dark_bg, 52.8 + local_t) if dark_theme else out_light_bg
        im = Image.fromarray(base_bg).convert("RGBA")
        ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        full = prefix + highlight
        n_tot = len(full)
        t_span = 0.78 if not dark_theme else 1.25
        c_idx = min(n_tot, max(1, int((local_t - 0.05) / (t_span / n_tot)) + 1)) if local_t >= 0.05 else 0
        w_pre = dr.textbbox((0, 0), prefix, font=f_type_56)[2]
        w_hl = dr.textbbox((0, 0), highlight, font=f_type_56)[2]
        sx = (OUT_W - (w_pre + w_hl)) // 2
        ty = 496

        s_pre = full[:min(c_idx, len(prefix))]
        s_hl = full[len(prefix):c_idx] if c_idx > len(prefix) else ""
        cur_x = sx
        c_pre = (238, 242, 248, 255) if dark_theme else (32, 39, 42, 255)
        c_hl = (122, 178, 252, 255) if dark_theme else (52, 92, 162, 255)
        if s_pre:
            dr.text((sx, ty), s_pre, font=f_type_56, fill=c_pre)
            cur_x = sx + dr.textbbox((0, 0), s_pre, font=f_type_56)[2]
        if s_hl:
            dr.text((sx + w_pre, ty), s_hl, font=f_type_56, fill=c_hl)
            cur_x = sx + w_pre + dr.textbbox((0, 0), s_hl, font=f_type_56)[2]
        if c_idx < n_tot or int(local_t * 6.0) % 2 == 0:
            dr.rounded_rectangle((cur_x + 8, ty + 8, cur_x + 14, ty + 66), radius=3, fill=c_hl)
        im.alpha_composite(ov)
        return zoom_scale_frame(np.asarray(im.convert("RGB")), 0.97 + 0.08 * (local_t / 1.50))

    # -----------------------------------------------------------------
    # ACT 4A (46.30 - 52.85s): Dark Cyber-Grid + 2.5D Codex/Claude Cards + Bezier Streams!
    # -----------------------------------------------------------------
    def scene_act4a_dark_codex(sec: float) -> np.ndarray:
        lt = sec - 46.36  # 0.0 .. 6.49s
        lt = max(0.0, lt)
        dyn_bg = render_dynamic_dark_backdrop(out_dark_bg, sec, boost=0.15)
        st_rgba = stage_dark_4a_rgba.copy()
        st_rgb = np.ascontiguousarray(st_rgba[..., :3])

        if lt < 3.65:
            u = lt / 3.65
            enter_u = ease_whip(lt / 0.55)
            fx = 1110.0 + (965.0 - 1110.0) * enter_u + 85.0 * u
            fy = 705.0 + (565.0 - 705.0) * enter_u + 55.0 * u
            zm = 0.92 + (1.68 - 0.92) * enter_u + 0.14 * u
            yaw = 14.0 - 6.5 * u
            pitch, roll = 5.0 - 0.8 * u, -2.2 + 0.6 * u
        elif lt < 4.02:
            u = ease_in_out_whip((lt - 3.65) / 0.37)
            fx = 1050.0 + (1765.0 - 1050.0) * u
            fy = 620.0 + (525.0 - 620.0) * u
            zm = 1.82 + (1.96 - 1.82) * u
            yaw = 7.5 + (-10.0 - 7.5) * u
            pitch, roll = 4.2, -1.6 + 3.4 * u
        else:
            u = (lt - 4.02) / 2.35
            fx, fy, zm = 1765.0 + 35.0 * u, 525.0 + 35.0 * u, 1.96 + 0.14 * u
            yaw, pitch, roll = -10.0 + 2.0 * u, 4.2, 1.8

        elevate_25d_card(st_rgb, stage_dark_4a_rgb_ref, 414, 360, 964, 632, (lt - 0.85) / 0.40, yaw, glow_rgb=(233, 193, 110))
        elevate_25d_card(st_rgb, stage_dark_4a_rgb_ref, 984, 360, 1534, 632, (lt - 1.18) / 0.40, yaw, glow_rgb=(185, 172, 215))
        if lt > 3.85:
            elevate_25d_card(st_rgb, stage_dark_4a_rgb_ref, 1605, 398, 2190, 622, (lt - 3.85) / 0.38, yaw, glow_rgb=(122, 167, 239))

        # Glowing Bezier dispatch arcs into Codex & Claude Code cards!
        if 0.60 <= lt <= 2.40:
            bu = (lt - 0.60) / 0.85
            draw_glowing_bezier_stream(st_rgb, (WIN_OX + 1850, WIN_OY + 250), (WIN_OX + 690, WIN_OY + 490),
                                       (WIN_OX + 1280, WIN_OY + 160), bu, tail_len=0.45, color_rgb=(240, 195, 95), thickness=5)
            draw_glowing_bezier_stream(st_rgb, (WIN_OX + 1850, WIN_OY + 250), (WIN_OX + 1260, WIN_OY + 490),
                                       (WIN_OX + 1560, WIN_OY + 190), max(0.0, bu - 0.25), tail_len=0.45, color_rgb=(190, 165, 245), thickness=5)

        if lt >= 4.25:
            cp = ease_whip((lt - 4.25) / 0.55)
            cur_x = int(WIN_OX + 1755 - (1.0 - cp) * 200)
            cur_y = int(WIN_OY + 568 + (1.0 - cp) * 130)
            if lt >= 5.00:
                rp = clamp01((lt - 5.00) / 0.45)
                cv2.circle(st_rgb, (WIN_OX + 1755, WIN_OY + 568), int(22 + rp * 48), (122, 167, 239), 3, lineType=cv2.LINE_AA)
            blit_rgba_np(st_rgb, CURSOR_SPRITE, cur_x, cur_y, 1.0)

        st_rgba[..., :3] = st_rgb
        frame = project_3d(st_rgba, fx, fy, zm, yaw, pitch, roll, custom_bg_1080=dyn_bg)
        return add_corner_pill(frame, "本机直调 Codex · Claude Code · ACP 协议工具", "#f4c56b", (lt - 0.50) / 0.25, pos=("left", "top"))

    # -----------------------------------------------------------------
    # ACT 4B (54.55 - 61.90s): Dark Cyber-Grid + 2.5D Stepped DOCX/XLSX/PPTX Cards!
    # -----------------------------------------------------------------
    def scene_act4b_dark_office(sec: float) -> np.ndarray:
        lt = max(0.0, sec - 54.55)  # 0.0 .. 7.27s
        dyn_bg = render_dynamic_dark_backdrop(out_dark_bg, sec + 10.0, boost=0.18)
        st_rgba = stage_dark_4b_rgba.copy()
        st_rgb = np.ascontiguousarray(st_rgba[..., :3])

        if lt < 4.20:
            u = lt / 4.20
            enter_u = ease_whip(lt / 0.55)
            fx = 1110.0 + (955.0 - 1110.0) * enter_u + 95.0 * u
            fy = 705.0 + (655.0 - 705.0) * enter_u + 45.0 * u
            zm = 0.88 + (1.68 - 0.88) * enter_u + 0.16 * u
            yaw = -14.0 + 6.5 * u
            pitch, roll = 5.0 - 0.8 * u, 2.2 - 0.6 * u
        elif lt < 4.58:
            u = ease_in_out_whip((lt - 4.20) / 0.38)
            fx = 1050.0 + (1770.0 - 1050.0) * u
            fy = 700.0 + (545.0 - 700.0) * u
            zm = 1.84 + (1.96 - 1.84) * u
            yaw = -7.5 + (10.0 - (-7.5)) * u
            pitch, roll = 4.2, 1.6 - 3.4 * u
        else:
            u = (lt - 4.58) / 2.68
            fx, fy, zm = 1770.0 - 25.0 * u, 545.0 + 30.0 * u, 1.96 + 0.14 * u
            yaw, pitch, roll = 10.0 - 2.0 * u, 4.2, -1.8

        elevate_25d_card(st_rgb, stage_dark_4b_rgb_ref, 414, 618, 770, 844, (lt - 1.40) / 0.36, yaw, glow_rgb=(122, 167, 239))
        elevate_25d_card(st_rgb, stage_dark_4b_rgb_ref, 790, 618, 1148, 844, (lt - 1.70) / 0.36, yaw, glow_rgb=(140, 224, 113))
        elevate_25d_card(st_rgb, stage_dark_4b_rgb_ref, 1168, 618, 1524, 844, (lt - 2.00) / 0.36, yaw, glow_rgb=(233, 193, 110))
        if lt > 4.40:
            elevate_25d_card(st_rgb, stage_dark_4b_rgb_ref, 1590, 415, 2190, 662, (lt - 4.40) / 0.38, yaw, glow_rgb=(122, 167, 239))

        st_rgba[..., :3] = st_rgb
        frame = project_3d(st_rgba, fx, fy, zm, yaw, pitch, roll, custom_bg_1080=dyn_bg)
        return add_corner_pill(frame, "科研检索 + 原生导出 DOCX · XLSX · PPTX", "#8ce071", (lt - 0.50) / 0.25, pos=("right", "top"))

    # -----------------------------------------------------------------
    # ACT 5A (61.82 - 67.35s): SPECTACLE UPGRADE #1B — LIVE 16-Agent & 12-Report Storm Hero Stage!
    # -----------------------------------------------------------------
    # Place storm_dark on a 3000x1900 RGBA stage wrapper once per frame with glowing rim!
    def scene_act5a_live_16_agent_storm(sec: float) -> np.ndarray:
        lt = max(0.0, sec - 61.82)  # 0.0 .. 5.53s
        dyn_bg = render_dynamic_dark_backdrop(out_dark_bg, sec * 1.4, boost=0.45)

        f_idx = min(119, int(round((lt / 5.45) * 119.0)))
        im_storm = seq_storm_dark_rgba[f_idx]  # 1440 x 728 RGBA

        # Project storm card in dynamic 3D perspective over dark cyber-grid!
        st_rgba = np.zeros((PM_H, PM_W, 4), dtype=np.uint8)
        ox_s, oy_s = (PM_W - storm_w) // 2, (PM_H - storm_h) // 2 + 40
        st_rgba[oy_s:oy_s + storm_h, ox_s:ox_s + storm_w] = np.asarray(im_storm)
        # Crisp glowing electric border on the hero stage card
        st_rgb_slice = np.ascontiguousarray(st_rgba[oy_s:oy_s + storm_h, ox_s:ox_s + storm_w, :3])
        cv2.rectangle(st_rgb_slice, (1, 1), (storm_w - 2, storm_h - 2), (110, 168, 250), 3, cv2.LINE_AA)
        st_rgba[oy_s:oy_s + storm_h, ox_s:ox_s + storm_w, :3] = st_rgb_slice

        u = lt / 5.45
        enter_u = ease_spring(lt / 0.55)
        zm = 0.85 + 0.92 * enter_u + 0.18 * u
        yaw = -11.0 + 22.0 * u
        pitch = 6.5 - 3.0 * u
        roll = -1.8 + 3.6 * u
        canvas = project_3d(st_rgba, 1110.0, 745.0, zm, yaw, pitch, roll, custom_bg_1080=dyn_bg)

        # Ambient Bezier energy streams feeding into the 16-Agent Stage!
        if lt < 4.6:
            bu_l = (lt * 1.25) % 1.4
            bu_r = ((lt + 0.35) * 1.25) % 1.4
            draw_glowing_bezier_stream(canvas, (60, 880), (420, 560), (180, 520), bu_l, tail_len=0.45, color_rgb=(95, 185, 255), thickness=4)
            draw_glowing_bezier_stream(canvas, (1860, 880), (1500, 560), (1740, 520), bu_r, tail_len=0.45, color_rgb=(135, 225, 150), thickness=4)

        # Top Hero Title Overlay
        im = Image.fromarray(canvas).convert("RGBA")
        ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        al = int(255 * clamp01(lt / 0.30))
        f_h = get_font(FONT_BOLD_PATH, 48)
        t1, t2 = "16 位负责人并坐窗沿 · ", "多级子 Agent 并发风暴"
        w1 = dr.textbbox((0, 0), t1, font=f_h)[2]
        w2 = dr.textbbox((0, 0), t2, font=f_h)[2]
        tx = (OUT_W - (w1 + w2)) // 2
        ty = 52
        dr.rounded_rectangle((tx - 28, ty - 10, tx + w1 + w2 + 28, ty + 72),
                             radius=24, fill=(18, 24, 36, 220), outline=(95, 148, 235, al), width=2)
        dr.text((tx, ty), t1, font=f_h, fill=(242, 246, 252, al))
        dr.text((tx + w1, ty), t2, font=f_h, fill=(122, 184, 255, al))
        im.alpha_composite(ov)
        return np.asarray(im.convert("RGB"))

    # -----------------------------------------------------------------
    # ACT 5B (67.27 - 72.80s): Depth-Sorted 3D 8-Card Capability Flywheel (Accelerating!)
    # -----------------------------------------------------------------
    def scene_act5b_3d_flywheel(sec: float) -> np.ndarray:
        lt = max(0.0, sec - 67.27)  # 0.0 .. 5.53s
        out_arr = out_light_bg.copy()
        accel = 1.0 + 0.45 * (lt / 5.45) ** 2

        card_items = []
        for ci in range(8):
            cp_in = ease_spring((lt - 0.04 - ci * 0.06) / 0.36)
            if cp_in <= 0.01:
                continue
            ang = (ci / 8.0) * 2.0 * math.pi + lt * 0.82 * accel
            z = math.cos(ang)
            x3 = math.sin(ang) * 715.0 * cp_in
            y3 = z * 220.0 * cp_in - 16.0 + math.sin(lt * 3.5 + ci) * 8.0
            persp_scale = 0.86 + 0.25 * z
            opacity = clamp01(cp_in * (0.74 + 0.26 * ((z + 1.0) * 0.5)))
            card_items.append((z, ci, x3, y3, persp_scale, opacity))

        card_items.sort(key=lambda it: it[0])

        def draw_center_title(arr_rgb: np.ndarray):
            im = Image.fromarray(arr_rgb).convert("RGBA")
            ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
            dr = ImageDraw.Draw(ov)
            sc_t = 0.92 + 0.08 * ease_spring(lt / 0.35) + 0.05 * (lt / 5.45)
            al_t = int(255 * clamp01(lt * 5.0))
            f_big = get_font(FONT_BOLD_PATH, int(74 * sc_t))
            f_sub = get_font(FONT_REG_PATH, int(24 * sc_t))
            t1, t2 = "全场景，", "都能带队"
            w1 = dr.textbbox((0, 0), t1, font=f_big)[2]
            w2 = dr.textbbox((0, 0), t2, font=f_big)[2]
            tx = (OUT_W - (w1 + w2)) // 2
            ty = int(458 - (sc_t - 1.0) * 35)
            dr.rounded_rectangle((tx - 32, ty - 14, tx + w1 + w2 + 32, ty + int(138 * sc_t)),
                                 radius=32, fill=(248, 250, 252, 224))
            dr.text((tx, ty), t1, font=f_big, fill=(32, 39, 42, al_t))
            dr.text((tx + w1, ty), t2, font=f_big, fill=(52, 90, 154, al_t))
            sub_s = "编程工程  ·  科研探索  ·  Office 办公  ·  通用日常"
            ws = dr.textbbox((0, 0), sub_s, font=f_sub)[2]
            dr.text(((OUT_W - ws) // 2, ty + int(94 * sc_t)), sub_s, font=f_sub, fill=(92, 102, 114, al_t))
            im.alpha_composite(ov)
            return np.asarray(im.convert("RGB")).copy()

        drew_title = False
        for z, ci, x3, y3, p_sc, op in card_items:
            if not drew_title and z >= 0.0:
                out_arr = draw_center_title(out_arr)
                drew_title = True
            cw = max(24, int(340 * p_sc))
            ch = max(24, int(210 * p_sc))
            c_rgba = np.asarray(cap_cards_pil[ci].resize((cw, ch), Image.Resampling.BILINEAR))
            blit_rgba_np(out_arr, c_rgba, int(OUT_W * 0.5 + x3 - cw // 2), int(OUT_H * 0.5 + y3 - ch // 2), opacity=op)
        if not drew_title:
            out_arr = draw_center_title(out_arr)
        return out_arr

    # -----------------------------------------------------------------
    # ACT 5C (72.73 - 76.36s): SPECTACLE UPGRADE #5A — 8-Beat Snare-Riser Rapid-Fire Climax Montage!
    # -----------------------------------------------------------------
    # Pre-render 8 ultra-crisp hero background plates for the 8 rapid-fire 1-beat (0.454s) climax cuts!
    montage_specs = [
        ("~90", "原生工具开箱即用", "读写 · 检索 · 终端 · 浏览器 · 图表 · 文档", project_3d(stage_chart, 1080, 660, 1.75, -8.5, 4.5, -1.8)),
        ("4 × 4", "四大模式 · 四套工作台", "Agent · IDE · Research · Bot 自由切换", project_3d(stage_wb_raw, 1320, 620, 1.70, 8.5, 4.5, 1.8)),
        ("CLI", "本机直调 Codex & Claude Code", "兼容 ACP 协议 · 多智能体混合编队", project_3d(stage_dark_4a_rgba, 980, 520, 1.78, -9.5, 4.5, -1.6, custom_bg_1080=out_dark_bg)),
        ("9 种", "原生模型协议 · 本地自控", "自有 API Key · 数据留在你自己的主机", project_3d(stage_calc, 920, 740, 1.80, 8.0, 4.5, -1.5)),
        ("7 门", "内置语言服务 · 秒级构建", "TS · Python · Rust · Go · C/C++ · Java", project_3d(stage_ide, 680, 1080, 2.05, -8.0, 5.0, -1.6)),
        ("16 路", "团队并坐窗沿 · 不做黑盒", "多级子 Agent 并发 · 关键分歧才问你", scene_act5a_live_16_agent_storm(63.4)),
        ("全平台", "桌面与容器一键部署", "Windows · macOS · Linux · Docker", project_3d(stage_reading, 1110, 580, 1.68, 7.5, 4.2, 1.4)),
        ("随身连", "Android · iOS 远程直连主机", "离开工位也能随时查看进度与拍板", project_3d(stage_choices, 720, 820, 1.88, -7.5, 4.5, -1.6)),
    ]

    def scene_act5c_climax_montage(sec: float) -> np.ndarray:
        lt = max(0.0, sec - 72.73)  # 0.0 .. 3.636s (exact 8 beats!)
        beat_f = lt / BEAT_SEC
        idx = min(7, int(beat_f))
        sub_u = beat_f - idx  # 0.0 .. 1.0 within this 0.4545s cut!

        big_num, title_s, sub_s, bg_plate = montage_specs[idx]
        # High-velocity punch zoom on every beat + implosion tunnel on final 0.25s!
        implode_u = ease_in_quad((sec - 76.06) / 0.30) if sec > 76.06 else 0.0
        sc = (1.16 - 0.14 * ease_out_cubic(sub_u)) * (1.0 + 1.15 * implode_u)
        zoomed = zoom_scale_frame(bg_plate, sc)

        # Deep-navy cyber blur + frosted dark-glass hero card for maximum visual punch!
        blurred = cv2.GaussianBlur(zoomed, (17, 17), 0).astype(np.float32)
        tint = np.empty_like(blurred)
        tint[..., 0] = blurred[..., 0] * 0.14 + 10.0
        tint[..., 1] = blurred[..., 1] * 0.19 + 15.0
        tint[..., 2] = blurred[..., 2] * 0.30 + 28.0
        dim = np.clip(tint, 0, 255).astype(np.uint8)
        im = Image.fromarray(dim).convert("RGBA")
        ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)

        pop = ease_whip(sub_u / 0.28)
        f_num = get_font(FONT_BOLD_PATH, int(124 * (0.88 + 0.12 * pop)))
        f_tit = get_font(FONT_BOLD_PATH, 60)
        f_sb = get_font(FONT_REG_PATH, 27)

        wn = dr.textbbox((0, 0), big_num, font=f_num)[2]
        wt = dr.textbbox((0, 0), title_s, font=f_tit)[2]
        ws = dr.textbbox((0, 0), sub_s, font=f_sb)[2]
        card_w = max(wt, ws) + 140
        cx0_m, cx1_m = (OUT_W - card_w) // 2, (OUT_W + card_w) // 2
        dr.rounded_rectangle((cx0_m, 268, cx1_m, 682), radius=36,
                             fill=(14, 20, 34, 212), outline=(96, 165, 250, 175), width=3)

        dr.text(((OUT_W - wn) // 2, int(298 + (1.0 - pop) * 24)), big_num, font=f_num, fill=(118, 190, 255, 255))
        dr.text(((OUT_W - wt) // 2, int(468 + (1.0 - pop) * 18)), title_s, font=f_tit, fill=(248, 250, 255, 255))
        dr.rounded_rectangle(((OUT_W - ws) // 2 - 28, 576, (OUT_W + ws) // 2 + 28, 634),
                             radius=24, fill=(42, 68, 112, 165), outline=(122, 186, 255, 165), width=2)
        dr.text(((OUT_W - ws) // 2, 586), sub_s, font=f_sb, fill=(226, 238, 255, 255))

        # Subtle beat flash on cut entry + bright white-cyan flash right at 76.34s pre-drop!
        flash_a = int(95 * (1.0 - clamp01(sub_u / 0.16)) + 235 * implode_u)
        if flash_a > 2:
            dr.rectangle((0, 0, OUT_W, OUT_H), fill=(225, 240, 255, min(255, flash_a)))

        im.alpha_composite(ov)
        return np.asarray(im.convert("RGB"))

    # -----------------------------------------------------------------
    # ACT 5D (76.36 - 80.00s): SPECTACLE UPGRADE #5B — Final Impact Shockwave + Living 30FPS Mascot Squad Finale!
    # -----------------------------------------------------------------
    def scene_act5d_impact_finale(sec: float) -> np.ndarray:
        lt = max(0.0, sec - (168 * BEAT_SEC))  # 0.0 .. 3.636s
        p_in = ease_whip(lt / 0.36)

        im = Image.fromarray(out_light_bg).convert("RGBA")
        ov = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)

        # Impact Shockwave Ring bursting outward at 76.36s -> 77.15s!
        if lt < 0.82:
            sp = lt / 0.82
            rad = int(50 + ease_out_cubic(sp) * 1020)
            al_r = int(230 * (1.0 - sp))
            dr.ellipse((OUT_W // 2 - rad, 380 - rad, OUT_W // 2 + rad, 380 + rad),
                       outline=(78, 138, 232, al_r), width=max(2, int(14 * (1.0 - sp))))
        if lt < 0.22:
            dr.rectangle((0, 0, OUT_W, OUT_H), fill=(255, 255, 255, int(190 * (1.0 - lt / 0.22))))

        # Crisp Supersampled Varin Dual-Blade Mark + Wordmark
        ss = 2
        logo_layer = Image.new("RGBA", (OUT_W * ss, OUT_H * ss), (0, 0, 0, 0))
        ld = ImageDraw.Draw(logo_layer)
        vcx, vcy = OUT_W - 145, int(492 * ss)
        ld.polygon([(vcx + x * 1.55, vcy + y * 1.55) for x, y in p_blade1], fill=(32, 39, 42, int(255 * p_in)))
        ld.polygon([(vcx + x * 1.55, vcy + y * 1.55) for x, y in p_blade2], fill=(92, 138, 212, int(255 * p_in)))
        f_vw = get_font(FONT_BOLD_PATH, 108)
        ld.text((vcx + 108, vcy - 68), "Varin", font=f_vw, fill=(32, 39, 42, int(255 * p_in)))
        im.alpha_composite(logo_layer.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS), (0, 0))

        f_tag_m = get_font(FONT_BOLD_PATH, 46)
        t1, t2 = "通用 Super Agent · ", "一次创新探索"
        w1 = dr.textbbox((0, 0), t1, font=f_tag_m)[2]
        w2 = dr.textbbox((0, 0), t2, font=f_tag_m)[2]
        tx = (OUT_W - (w1 + w2)) // 2
        ty = int(562 + (1.0 - p_in) * 22)
        dr.text((tx, ty), t1, font=f_tag_m, fill=(32, 39, 42, int(255 * p_in)))
        dr.text((tx + w1, ty), t2, font=f_tag_m, fill=(52, 92, 162, int(255 * p_in)))

        f_pl = get_font(FONT_BOLD_PATH, 18)
        plat_tags = ["macOS · Windows · Linux · Docker", "Android · iOS 远程直连", "自有 API Key 本地自控", "可调度 Codex / Claude Code"]
        gap = 14
        p_widths = [dr.textbbox((0, 0), tg, font=f_pl)[2] + 36 for tg in plat_tags]
        tot_pw = sum(p_widths) + gap * (len(plat_tags) - 1)
        px_cur = (OUT_W - tot_pw) // 2
        for ti, (tg, pw_i) in enumerate(zip(plat_tags, p_widths)):
            pp = ease_spring((lt - 0.12 - ti * 0.06) / 0.32)
            if pp > 0.01:
                wave_y = math.sin(lt * 3.4 + ti * 0.85) * 4.0
                py_p = int(648 + (1.0 - pp) * 20 + wave_y)
                dr.rounded_rectangle((px_cur, py_p, px_cur + pw_i, py_p + 42), radius=21,
                                     fill=(230, 238, 250, int(245 * clamp01(pp))),
                                     outline=(188, 208, 238, int(255 * clamp01(pp))), width=2)
                dr.text((px_cur + 18, py_p + 9), tg, font=f_pl, fill=(50, 86, 148, int(255 * clamp01(pp))))
            px_cur += pw_i + gap

        p_cta = ease_whip((lt - 0.24) / 0.34)
        if p_cta > 0.01:
            f_cta = get_font(FONT_BOLD_PATH, 21)
            cta_txt = "AGPL-3.0 开源免费  ·  立即下载与源码构建  ·  github.com/Youzini-afk/Varin  ·  varin.dev"
            wc = dr.textbbox((0, 0), cta_txt, font=f_cta)[2] + 64
            cx0 = (OUT_W - wc) // 2
            cy0 = int(718 + (1.0 - p_cta) * 18)
            dr.rounded_rectangle((cx0, cy0, cx0 + wc, cy0 + 54), radius=27, fill=(22, 28, 38, int(248 * p_cta)))
            sheen_x = cx0 + int(((lt * 0.52) % 1.30) * wc) - 50
            if cx0 + 8 <= sheen_x <= cx0 + wc - 98:
                dr.rounded_rectangle((sheen_x, cy0 + 3, sheen_x + 90, cy0 + 51),
                                     radius=22, fill=(40, 62, 98, int(248 * p_cta)))
            dr.rounded_rectangle((cx0, cy0, cx0 + wc, cy0 + 54), radius=27, outline=(112, 164, 242, int(185 * p_cta)), width=2)
            dr.text((cx0 + 32, cy0 + 14), cta_txt, font=f_cta, fill=(246, 248, 252, int(255 * p_cta)))

        im.alpha_composite(ov)
        out_arr = np.asarray(im.convert("RGB")).copy()

        # Genuine 30FPS Spring-Physics Mascot + 4 Squad Leads (`seq_finale_rgba`: star burst -> wave -> wink!)
        m_idx = min(119, int(round((lt / 3.636) * 114.0)))
        m_rgba = seq_finale_rgba[m_idx]
        blit_rgba_np(out_arr, m_rgba, (OUT_W - m_rgba.shape[1]) // 2, int(62 + (1.0 - p_in) * 26), opacity=p_in)
        return zoom_scale_frame(out_arr, 1.0 + 0.035 * (lt / 3.64))

    # -----------------------------------------------------------------
    # Master Frame Router with Seamless Zoom-Through & Diagonal Laser Bridges!
    # -----------------------------------------------------------------
    def eval_frame(sec: float) -> np.ndarray:
        sec = max(0.0, min(DURATION - 0.001, sec))

        if sec < 4.72:
            return scene_act1_storm_morph(sec)
        if sec < 5.00:
            return zoom_through_blend(scene_act1_storm_morph(sec), scene_act2a_input(sec), (sec - 4.72) / 0.28)

        if sec < 8.95:
            return scene_act2a_input(sec)
        if sec < 9.18:
            p = ease_in_out_whip((sec - 8.95) / 0.23)
            return np.clip(scene_act2a_input(sec) * (1.0 - p) + scene_act2b_live_stage_and_radio(sec) * p, 0, 255).astype(np.uint8)

        if sec < 16.25:
            return scene_act2b_live_stage_and_radio(sec)
        if sec < 16.50:
            return zoom_through_blend(scene_act2b_live_stage_and_radio(sec), scene_act2c_chart(sec), (sec - 16.25) / 0.25)

        if sec < 19.90:
            return scene_act2c_chart(sec)
        if sec < 20.14:
            return zoom_through_blend(scene_act2c_chart(sec), scene_act2d_choices(sec), (sec - 19.90) / 0.24)

        if sec < 23.52:
            return scene_act2d_choices(sec)
        if sec < 23.76:
            return zoom_through_blend(scene_act2d_choices(sec), scene_act2e_live_calculator(sec), (sec - 23.52) / 0.24)

        if sec < 27.18:
            return scene_act2e_live_calculator(sec)
        if sec < 27.44:
            return zoom_through_blend(scene_act2e_live_calculator(sec), scene_act3a_multi_window_array(sec), (sec - 27.18) / 0.26)

        if sec < 31.78:
            return scene_act3a_multi_window_array(sec)
        if sec < 31.98:
            p = ease_in_out_whip((sec - 31.78) / 0.20)
            return np.clip(scene_act3a_multi_window_array(sec) * (1.0 - p) + scene_act3b_wb_and_ide(sec) * p, 0, 255).astype(np.uint8)

        if sec < 42.68:
            return scene_act3b_wb_and_ide(sec)
        if sec < 42.92:
            return zoom_through_blend(scene_act3b_wb_and_ide(sec), scene_act3c_reading_compare(sec), (sec - 42.68) / 0.24)

        if sec < 45.32:
            return scene_act3c_reading_compare(sec)
        if sec < 45.56:
            return zoom_through_blend(scene_act3c_reading_compare(sec),
                                      scene_typewriter_fast(max(0.0, sec - 45.45), "比如，", "直接调度本机 Codex 组队攻坚？", dark_theme=False),
                                      (sec - 45.32) / 0.24)

        # Typewriter 1 -> UPGRADE #4 Diagonal Electric-Cyan Laser Wipe into Dark 3D Codex!
        if sec < 46.26:
            return scene_typewriter_fast(sec - 45.45, "比如，", "直接调度本机 Codex 组队攻坚？", dark_theme=False)
        if sec < 46.80:
            return diagonal_laser_wipe(
                scene_typewriter_fast(sec - 45.45, "比如，", "直接调度本机 Codex 组队攻坚？", dark_theme=False),
                scene_act4a_dark_codex(sec),
                (sec - 46.26) / 0.54
            )

        if sec < 52.62:
            return scene_act4a_dark_codex(sec)
        if sec < 52.86:
            return zoom_through_blend(scene_act4a_dark_codex(sec),
                                      scene_typewriter_fast(max(0.0, sec - 52.73), "再比如，", "查完文献顺手生成整套汇报？", dark_theme=True),
                                      (sec - 52.62) / 0.24)

        if sec < 54.42:
            return scene_typewriter_fast(sec - 52.73, "再比如，", "查完文献顺手生成整套汇报？", dark_theme=True)
        if sec < 54.68:
            return zoom_through_blend(scene_typewriter_fast(sec - 52.73, "再比如，", "查完文献顺手生成整套汇报？", dark_theme=True),
                                      scene_act4b_dark_office(sec), (sec - 54.42) / 0.26)

        if sec < 61.70:
            return scene_act4b_dark_office(sec)
        if sec < 61.96:
            return zoom_through_blend(scene_act4b_dark_office(sec), scene_act5a_live_16_agent_storm(sec), (sec - 61.70) / 0.26)

        if sec < 67.15:
            return scene_act5a_live_16_agent_storm(sec)
        if sec < 67.41:
            return zoom_through_blend(scene_act5a_live_16_agent_storm(sec), scene_act5b_3d_flywheel(sec), (sec - 67.15) / 0.26)

        if sec < 72.73:
            return scene_act5b_3d_flywheel(sec)

        impact_t = 168 * BEAT_SEC  # 76.3636s
        if sec < impact_t:
            return scene_act5c_climax_montage(sec)
        return scene_act5d_impact_finale(sec)

    whip_spans = [
        (2.68, 3.05), (4.72, 5.00), (5.55, 5.95), (7.75, 8.15), (8.95, 9.20),
        (12.65, 12.98), (16.25, 16.50), (19.90, 20.14), (23.52, 23.76), (27.18, 27.44),
        (31.65, 31.98), (35.35, 35.70), (38.62, 39.15), (39.55, 39.89), (42.68, 42.92),
        (45.32, 45.56), (46.26, 46.80), (50.00, 50.38), (52.62, 52.86), (54.42, 54.68),
        (58.75, 59.15), (61.70, 61.96), (67.15, 67.41),
    ]
    def is_whip(s):
        return any(a <= s <= b for a, b in whip_spans)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{OUT_W}x{OUT_H}",
        "-r", str(FPS),
        "-i", "-",
        "-i", str(mix_wav_path),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(mp4_out_path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    kf_map = {
        int(8.55 * FPS):  KF80 / "kf01_bezier_send_beam.png",
        int(10.60 * FPS): KF80 / "kf02_live_embedded_stage.png",
        int(14.80 * FPS): KF80 / "kf03_spotless_radio.png",
        int(25.90 * FPS): KF80 / "kf04_live_slider_calc_30h.png",
        int(29.20 * FPS): KF80 / "kf05_3d_multi_window_array.png",
        int(44.10 * FPS): KF80 / "kf06_dual_view_reading.png",
        int(46.52 * FPS): KF80 / "kf07_diagonal_laser_wipe.png",
        int(64.20 * FPS): KF80 / "kf08_live_16_agent_storm.png",
        int(74.30 * FPS): KF80 / "kf09_climax_montage.png",
        int(77.80 * FPS): KF80 / "kf10_living_squad_finale.png",
    }

    for f_idx in range(TOTAL_FRAMES):
        sec = f_idx / float(FPS)
        if is_whip(sec):
            fa = eval_frame(sec - 0.009).astype(np.float32)
            fb = eval_frame(sec).astype(np.float32)
            fc = eval_frame(sec + 0.009).astype(np.float32)
            rgb = np.clip(fa * 0.25 + fb * 0.50 + fc * 0.25, 0, 255).astype(np.uint8)
        else:
            rgb = eval_frame(sec)

        if f_idx in kf_map:
            Image.fromarray(rgb).save(kf_map[f_idx])

        proc.stdin.write(rgb.tobytes())
        if (f_idx + 1) % 400 == 0:
            print(f"Progress: {f_idx + 1}/{TOTAL_FRAMES} frames ({time.time() - t_start:.1f}s)")

    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", errors="replace")
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"FFmpeg failed ({ret}):\n{err}")
    print(f"DONE! Rendered 80s Flagship Spectacle MP4 in {time.time() - t_start:.1f}s -> {mp4_out_path} ({mp4_out_path.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    mix_wav = build_80s_audio_stems()
    mp4_80 = OUT_DIR / "varin-promo-80s-flagship.mp4"
    render_80s_master(mix_wav, mp4_80)
    shutil.copy2(mp4_80, BUNDLE80 / mp4_80.name)
