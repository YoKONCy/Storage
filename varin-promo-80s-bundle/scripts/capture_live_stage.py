import base64
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE = Path("/working_dir/c_060eff669e9961d5/artifacts/file_generation/ttl=63d/intermediate")
SRC_DIR = BASE / "unpacked_assets/video-assets/素材/mascot/source"
OUT_CAP = BASE / "stage_captures"
for sub in ["dispatch_light", "storm_dark", "finale_rgba"]:
    (OUT_CAP / sub).mkdir(parents=True, exist_ok=True)

varin_art_js = (SRC_DIR / "varin-art.js").read_text("utf-8")
team_art_js = (SRC_DIR / "team-art.js").read_text("utf-8")
figure_js = (SRC_DIR / "figure.js").read_text("utf-8")
poses_js = (SRC_DIR / "figure-stage-poses.js").read_text("utf-8")
stage_js = (SRC_DIR / "stage.js").read_text("utf-8")

# Patch figure.js & stage.js so automatic rAF loop is disabled and we step exact 1/30s frames deterministically!
figure_js_patched = figure_js.replace(
    "requestAnimationFrame(frame);",
    "// manual deterministic stepping enabled"
)
stage_js_patched = stage_js.replace(
    "requestAnimationFrame(t => { last = t; requestAnimationFrame(frame); });",
    """
    window.__stage = stage;
    window.__stepDt = function(dt) {
      for (const f of Figure.live) {
        f.visible = true;
        f.still = false;
        f.step(dt);
        f.fxStep(dt);
      }
      stage.renderUi();
    };
    """
)

def make_stage_html(w_css: int, h_css: int, mode: str) -> str:
    """
    mode:
      - 'light_embed': 251x216 CSS (502x432 @ 2x) matching varin-zh-CN.png right Bot Stage (#f3f3f3)
      - 'dark_storm':  680x370 CSS (1360x740 @ 2x) wide hero 16-agent storm panel in dark mode
      - 'finale_rgba': 380x240 CSS (760x480 @ 2x) transparent RGBA mascot + 4 squad leads cheering/waving
    """
    is_dark = (mode == "dark_storm")
    is_rgba = (mode == "finale_rgba")
    bg_css = "transparent" if is_rgba else ("#141822" if is_dark else "#f3f3f3")
    panel_bg = "transparent" if is_rgba else ("#141822" if is_dark else "#f3f3f3")
    stage_h = h_css if not is_dark else (h_css - 66)
    fig_h = int(stage_h * 0.72) if not is_rgba else (h_css - 16)

    extra_css = ""
    if mode == "light_embed":
        extra_css = """
        .panel { border:none !important; border-radius:0 !important; background:#f3f3f3 !important; }
        .list { display:none !important; }
        .stage { height:216px !important; padding:0 0 8px !important; }
        .fig-host { height:158px !important; margin-bottom:4px !important; }
        .name { font-size:15px !important; }
        .state { font-size:11.5px !important; }
        .menu { display:none !important; }
        """
    elif mode == "dark_storm":
        extra_css = """
        .panel { border:1px solid #2b3344 !important; border-radius:18px !important; background:#141822 !important; }
        .stage { height:278px !important; padding:0 0 10px !important; }
        .fig-host { height:206px !important; margin-bottom:6px !important; }
        .list { padding:8px 18px 12px !important; display:flex; flex-wrap:wrap; gap:6px 18px; align-items:center; }
        .list h3 { width:100%; margin:0 0 2px !important; color:#8fb0ea !important; }
        .row { width:calc(25% - 14px); padding:2px 0 !important; font-size:12px !important; }
        .row .where { display:none !important; }
        """
    elif mode == "finale_rgba":
        extra_css = """
        body, .panel, .stage { background:transparent !important; border:none !important; }
        .floor, .menu, .name, .state, .list { display:none !important; }
        .stage { height:240px !important; padding:0 !important; justify-content:center !important; }
        .fig-host { height:232px !important; margin:0 !important; }
        """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  :root {{ --page:{bg_css}; --panel:{panel_bg}; --line:#e1e4ea; --text:#1c1f26; --muted:#6b717c; --grid:#e3e6ec; --ledge:#dfe2e9; --mark:#8a90a0; --bubble:#ffffff;
    --chip:#ffffff; --chip-text:#3a3f4a; --accent:#8fb0ea; --warn:#c98a2b; }}
  body.dark {{ --page:#141822; --panel:#141822; --line:#283040; --text:#eef2f8; --muted:#94a0b4; --grid:#232a38; --ledge:#333c4e; --mark:#a5b0c2; --bubble:#252c3a;
    --chip:#252c3a; --chip-text:#dce4f2; --warn:#e3a24f; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ width:{w_css}px; height:{h_css}px; overflow:hidden; background:{bg_css}; color:var(--text);
    font:14px/1.5 "Noto Sans CJK SC", "PingFang SC", system-ui, sans-serif; }}
  .panel {{ width:{w_css}px; height:{h_css}px; background:var(--panel); overflow:hidden; }}
  .stage {{ position:relative; height:{stage_h}px; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; padding:0 0 10px; overflow:hidden; }}
  .floor {{ position:absolute; inset:0; pointer-events:none;
    background-image:linear-gradient(to right, var(--grid) 1px, transparent 1px), linear-gradient(to bottom, var(--grid) 1px, transparent 1px);
    background-size:20px 20px; background-position:center 10px;
    -webkit-mask-image:radial-gradient(ellipse 74% 72% at 50% 42%, #000 0%, transparent 82%); mask-image:radial-gradient(ellipse 74% 72% at 50% 42%, #000 0%, transparent 82%); }}
  .fig-host {{ position:relative; align-self:stretch; height:{fig_h}px; }}
  .menu {{ position:absolute; top:8px; right:12px; color:var(--muted); font-size:18px; }}
  .name {{ position:relative; display:flex; gap:6px; align-items:center; font-size:18px; font-weight:700; line-height:1.25; }}
  .name .edit {{ font-size:11px; color:var(--muted); border:1px solid var(--line); border-radius:50%; width:20px; height:20px; display:inline-flex; align-items:center; justify-content:center; }}
  .state {{ position:relative; min-height:20px; font-size:12.5px; color:var(--muted); display:flex; gap:6px; align-items:center; }}
  .state i {{ width:9px; height:9px; border-radius:50%; background:#7cc79a; display:inline-block; }}
  .list {{ border-top:1px solid var(--line); padding:8px 14px; font-size:12.5px; }}
  .row {{ display:flex; align-items:center; gap:6px; padding:2px 0; }}
  .row .sub {{ color:var(--muted); font-size:11.5px; }}
  .hidden-dom {{ display:none !important; }}
  {extra_css}
</style>
</head>
<body class="{'dark' if is_dark else ''}">
  <div class="panel" id="panel">
    <div class="stage">
      <div class="floor"></div>
      <span class="menu">⋯</span>
      <div class="fig-host" id="figHost"></div>
      <div class="name">Varin <span class="edit">✎</span></div>
      <div class="state" id="stateLine"><i></i><span>空闲</span></div>
    </div>
    <div class="list" id="workList"></div>
  </div>
  <div class="hidden-dom">
    <div id="own"></div><div id="meter"></div><div id="log"></div>
    <input id="typing" type="checkbox"><select id="speed"><option value="1" selected>1</option></select>
    <input id="width" value="{w_css}"><span id="widthOut"></span>
    <input id="zoomBox" type="checkbox"><input id="dark" type="checkbox">
  </div>
  <script>{varin_art_js}</script>
  <script>{team_art_js}</script>
  <script>{figure_js_patched}</script>
  <script>{poses_js}</script>
  <script>{stage_js_patched}</script>
</body>
</html>"""

opts = Options()
opts.binary_location = "/usr/bin/chromium"
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--hide-scrollbars")
opts.add_argument("--force-device-scale-factor=2")

driver = webdriver.Chrome(options=opts)

def capture_sequence(mode: str, w_css: int, h_css: int, n_frames: int, init_js: str, per_frame_js: str, out_subdir: str):
    t0 = time.time()
    if mode == "finale_rgba":
        driver.execute_cdp_cmd("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
    else:
        driver.execute_cdp_cmd("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 243, "g": 243, "b": 243, "a": 255}})
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": w_css, "height": h_css, "deviceScaleFactor": 2, "mobile": False
    })
    html = make_stage_html(w_css, h_css, mode)
    b64 = base64.b64encode(html.encode("utf-8")).decode("ascii")
    driver.get(f"data:text/html;base64,{b64}")
    driver.execute_script(init_js)

    out_d = OUT_CAP / out_subdir
    for i in range(n_frames):
        driver.execute_script(f"const frameIdx = {i}; {per_frame_js}; window.__stepDt(1.0 / 30.0);")
        res = driver.execute_cdp_cmd("Page.captureScreenshot", {"format": "png"})
        (out_d / f"f_{i:04d}.png").write_bytes(base64.b64decode(res["data"]))
    print(f"Captured {n_frames} frames for {out_subdir} in {time.time() - t0:.2f}s")

try:
    # 1. Embedded Light Window Dispatch Sequence (105 frames = 3.5s, 502x432 px)
    capture_sequence(
        mode="light_embed", w_css=251, h_css=216, n_frames=105,
        init_js="""
          const s = window.__stage;
          s.reset();
          s.own = 'preparing';
          s.say('收到你的消息');
          s.fig.play('ack');
          for (let k = 0; k < 5; k++) window.__stepDt(0.02);
        """,
        per_frame_js="""
          const s = window.__stage;
          if (frameIdx === 8) { s.own = 'idle'; window.__leadA = s.dispatch('发布页面', { side:'R' }); }
          if (frameIdx === 24) { window.__leadB = s.dispatch('用户反馈整理', { side:'L' }); }
          if (frameIdx === 45 && window.__leadA) { s.setStatus(window.__leadA, 'tool'); s.subDispatch(window.__leadA); }
          if (frameIdx === 56 && window.__leadB) { s.setStatus(window.__leadB, 'thinking'); s.subDispatch(window.__leadB); }
          if (frameIdx === 72 && window.__leadA) { s.subDispatch(window.__leadA); }
        """,
        out_subdir="dispatch_light"
    )

    # 2. Dark 16-Agent + 12-Report Flying Storm Sequence (120 frames = 4.0s, 1360x740 px)
    capture_sequence(
        mode="dark_storm", w_css=680, h_css=370, n_frames=120,
        init_js="""
          const s = window.__stage;
          s.reset();
          const names = ['调研','写作','测试','设计','前端','后端','数据','审校','检索','规划','文档','安全','部署','评估','翻译','运维'];
          const act = ['thinking','replying','tool'];
          for (let i = 0; i < 16; i++) {
            const m = s.addLead(names[i], { instant:true, status:act[i % 3], auto:true });
            const subs = 2 + (i * 3) % 4;
            for (let k = 0; k < subs; k++) s.addSub(m, { instant:true });
          }
          for (let k = 0; k < 18; k++) window.__stepDt(0.033);
        """,
        per_frame_js="""
          const s = window.__stage;
          const live = s.leads().filter(m => !m.leaving && m.mode !== 'pile');
          if (frameIdx % 5 === 1 && frameIdx < 66 && live.length) {
            const m = live[(frameIdx * 3) % live.length];
            s.report(m, 'ok');
          }
          if (frameIdx % 9 === 4 && frameIdx < 60 && live.length) {
            s.subDispatch(live[(frameIdx * 5) % live.length]);
          }
          if (frameIdx === 68) { s.own = 'thinking'; s.gather(); }
          if (frameIdx === 86) { s.own = 'idle'; s.say('12 份并行结果已汇总'); s.react.event({ kind:'complete', weight:'large', outcome:'ok' }); }
        """,
        out_subdir="storm_dark"
    )

    # 3. Transparent RGBA Finale Mascot + 4 Squad Leads Cheering/Waving/Winking (120 frames = 4.0s, 760x480 px)
    capture_sequence(
        mode="finale_rgba", w_css=380, h_css=240, n_frames=120,
        init_js="""
          const s = window.__stage;
          s.reset();
          const sq = [['调研','L','thinking'], ['写作','R','replying'], ['设计','L','tool'], ['测试','R','thinking']];
          for (const [nm, sd, st] of sq) {
            s.addLead(nm, { instant:true, side:sd, status:st, auto:true });
          }
          for (let k = 0; k < 20; k++) window.__stepDt(0.033);
          s.fig.setState('result');
        """,
        per_frame_js="""
          const s = window.__stage;
          if (frameIdx === 45) { s.fig.setState('idle'); s.fig.play('wave'); }
          if (frameIdx === 88) { s.fig.play('wink'); }
        """,
        out_subdir="finale_rgba"
    )
finally:
    driver.quit()
