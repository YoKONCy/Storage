import base64
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

BASE = Path("/working_dir/c_060eff669e9961d5/artifacts/file_generation/ttl=63d/intermediate")
SRC_DIR = BASE / "unpacked_assets/video-assets/素材/mascot/source"
OUT_CAP = BASE / "stage_captures"

varin_art_js = (SRC_DIR / "varin-art.js").read_text("utf-8")
team_art_js = (SRC_DIR / "team-art.js").read_text("utf-8")
figure_js = (SRC_DIR / "figure.js").read_text("utf-8").replace("requestAnimationFrame(frame);", "// manual")
poses_js = (SRC_DIR / "figure-stage-poses.js").read_text("utf-8")
stage_js = (SRC_DIR / "stage.js").read_text("utf-8").replace(
    "requestAnimationFrame(t => { last = t; requestAnimationFrame(frame); });",
    """
    window.__stage = stage;
    window.__stepDt = function(dt) {
      for (const f of Figure.live) { f.visible = true; f.still = false; f.step(dt); f.fxStep(dt); }
      stage.renderUi();
    };
    """
)

def make_fixed_html(w_css: int, h_css: int, mode: str) -> str:
    is_dark = (mode == "dark_storm")
    bg_css = "#141822" if is_dark else "#f3f3f3"
    extra_css = ""
    if mode == "light_embed":
        # Native 360x292 CSS -> 720x584 @ 2x! Keeps fig-host at exact native 216px -> ZERO overlap!
        extra_css = """
        .panel { border:none !important; border-radius:0 !important; background:#f3f3f3 !important; }
        .list, .menu { display:none !important; }
        .stage { height:292px !important; padding:0 0 10px !important; }
        .fig-host { height:216px !important; margin-bottom:8px !important; }
        """
    elif mode == "dark_storm":
        # Wide 720x364 CSS -> 1440x728 @ 2x! Single-line crisp rows (only first 4 shown cleanly)!
        extra_css = """
        .panel { border:2px solid #2d384c !important; border-radius:20px !important; background:#141822 !important; }
        .stage { height:292px !important; padding:0 0 10px !important; }
        .fig-host { height:216px !important; margin-bottom:8px !important; }
        .list { height:70px !important; padding:10px 22px !important; display:flex; flex-wrap:wrap; gap:4px 22px; align-items:center; overflow:hidden !important; }
        .list h3 { width:100%; margin:0 !important; color:#8fb0ea !important; font-size:12.5px !important; }
        .row { width:calc(25% - 18px); padding:0 !important; font-size:12px !important; white-space:nowrap !important; overflow:hidden !important; }
        .row:nth-of-type(n+5) { display:none !important; }
        .row .where { display:none !important; }
        """

    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>
      :root {{ --page:{bg_css}; --panel:{bg_css}; --line:#e1e4ea; --text:#1c1f26; --muted:#6b717c; --grid:#e3e6ec; --ledge:#dfe2e9; --mark:#8a90a0; --bubble:#ffffff; --chip:#ffffff; --chip-text:#3a3f4a; --accent:#8fb0ea; --warn:#c98a2b; }}
      body.dark {{ --page:#141822; --panel:#141822; --line:#283040; --text:#eef2f8; --muted:#94a0b4; --grid:#232a38; --ledge:#333c4e; --mark:#a5b0c2; --bubble:#252c3a; --chip:#252c3a; --chip-text:#dce4f2; --warn:#e3a24f; }}
      * {{ box-sizing:border-box; margin:0; padding:0; }}
      body {{ width:{w_css}px; height:{h_css}px; overflow:hidden; background:{bg_css}; color:var(--text); font:14px/1.45 "Noto Sans CJK SC", system-ui, sans-serif; }}
      .panel {{ width:{w_css}px; height:{h_css}px; background:var(--panel); overflow:hidden; }}
      .stage {{ position:relative; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; overflow:hidden; }}
      .floor {{ position:absolute; inset:0; pointer-events:none; background-image:linear-gradient(to right, var(--grid) 1px, transparent 1px), linear-gradient(to bottom, var(--grid) 1px, transparent 1px); background-size:22px 22px; background-position:center 12px; -webkit-mask-image:radial-gradient(ellipse 74% 72% at 50% 42%, #000 0%, transparent 82%); mask-image:radial-gradient(ellipse 74% 72% at 50% 42%, #000 0%, transparent 82%); }}
      .fig-host {{ position:relative; align-self:stretch; }}
      .menu {{ position:absolute; top:10px; right:14px; color:var(--muted); font-size:18px; }}
      .name {{ position:relative; display:flex; gap:6px; align-items:center; font-size:19px; font-weight:700; line-height:1.25; }}
      .name .edit {{ font-size:12px; color:var(--muted); border:1px solid var(--line); border-radius:50%; width:22px; height:22px; display:inline-flex; align-items:center; justify-content:center; }}
      .state {{ position:relative; min-height:20px; font-size:13px; color:var(--muted); display:flex; gap:6px; align-items:center; }}
      .state i {{ width:9px; height:9px; border-radius:50%; background:#7cc79a; display:inline-block; }}
      .list {{ border-top:1px solid var(--line); }}
      .row {{ display:flex; align-items:center; gap:6px; }}
      .row .sub {{ color:var(--muted); font-size:11.5px; }}
      .hidden-dom {{ display:none !important; }}
      {extra_css}
    </style></head><body class="{'dark' if is_dark else ''}">
      <div class="panel" id="panel">
        <div class="stage"><div class="floor"></div><span class="menu">⋯</span><div class="fig-host" id="figHost"></div>
          <div class="name">Varin <span class="edit">✎</span></div><div class="state" id="stateLine"><i></i><span>空闲</span></div></div>
        <div class="list" id="workList"></div>
      </div>
      <div class="hidden-dom"><div id="own"></div><div id="meter"></div><div id="log"></div>
        <input id="typing" type="checkbox"><select id="speed"><option value="1" selected>1</option></select>
        <input id="width" value="{w_css}"><span id="widthOut"></span><input id="zoomBox" type="checkbox"><input id="dark" type="checkbox">
      </div>
      <script>{varin_art_js}</script><script>{team_art_js}</script><script>{figure_js}</script><script>{poses_js}</script><script>{stage_js}</script>
    </body></html>"""

opts = Options()
opts.binary_location = "/usr/bin/chromium"
for a in ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--hide-scrollbars", "--force-device-scale-factor=2"]:
    opts.add_argument(a)
driver = webdriver.Chrome(options=opts)

def run_cap(mode, w_css, h_css, n_frames, init_js, per_js, subdir):
    t0 = time.time()
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {"width": w_css, "height": h_css, "deviceScaleFactor": 2, "mobile": False})
    b64 = base64.b64encode(make_fixed_html(w_css, h_css, mode).encode("utf-8")).decode("ascii")
    driver.get(f"data:text/html;base64,{b64}")
    driver.execute_script(init_js)
    out_d = OUT_CAP / subdir
    for i in range(n_frames):
        driver.execute_script(f"const frameIdx = {i}; {per_js}; window.__stepDt(1.0 / 30.0);")
        res = driver.execute_cdp_cmd("Page.captureScreenshot", {"format": "png"})
        (out_d / f"f_{i:04d}.png").write_bytes(base64.b64decode(res["data"]))
    print(f"Re-captured {n_frames} frames -> {subdir} in {time.time() - t0:.2f}s")

try:
    run_cap(
        "light_embed", 360, 292, 105,
        """const s=window.__stage; s.reset(); s.own='preparing'; s.say('收到你的消息'); s.fig.play('ack'); for(let k=0;k<5;k++) window.__stepDt(0.02);""",
        """const s=window.__stage;
           if(frameIdx===6){ s.own='idle'; window.__leadA=s.dispatch('发布页面',{side:'R'}); }
           if(frameIdx===22){ window.__leadB=s.dispatch('用户反馈整理',{side:'L'}); }
           if(frameIdx===44 && window.__leadA){ s.setStatus(window.__leadA,'tool'); s.subDispatch(window.__leadA); }
           if(frameIdx===55 && window.__leadB){ s.setStatus(window.__leadB,'thinking'); s.subDispatch(window.__leadB); }
           if(frameIdx===70 && window.__leadA){ s.subDispatch(window.__leadA); }""",
        "dispatch_light"
    )
    run_cap(
        "dark_storm", 720, 364, 120,
        """const s=window.__stage; s.reset();
           const names=['调研','写作','测试','设计','前端','后端','数据','审校','检索','规划','文档','安全','部署','评估','翻译','运维'];
           const act=['thinking','replying','tool'];
           for(let i=0;i<16;i++){ const m=s.addLead(names[i],{instant:true,status:act[i%3],auto:true}); const subs=2+(i*3)%4; for(let k=0;k<subs;k++) s.addSub(m,{instant:true}); }
           for(let k=0;k<18;k++) window.__stepDt(0.033);""",
        """const s=window.__stage; const live=s.leads().filter(m=>!m.leaving && m.mode!=='pile');
           if(frameIdx%5===1 && frameIdx<66 && live.length){ s.report(live[(frameIdx*3)%live.length],'ok'); }
           if(frameIdx%9===4 && frameIdx<60 && live.length){ s.subDispatch(live[(frameIdx*5)%live.length]); }
           if(frameIdx===68){ s.own='thinking'; s.gather(); }
           if(frameIdx===86){ s.own='idle'; s.say('12 份并行结果已汇总'); s.react.event({kind:'complete',weight:'large',outcome:'ok'}); }""",
        "storm_dark"
    )
finally:
    driver.quit()
