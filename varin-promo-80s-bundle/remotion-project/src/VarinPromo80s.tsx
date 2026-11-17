import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Camera3DStage} from './components/Camera3DStage';
import {CornerPill} from './components/CornerPill';
import {TypewriterPrompt} from './components/TypewriterPrompt';
import {VARIN_LIGHT, easeWhip} from './theme/tokens';

/**
 * Varin 80s Flagship Spectacle Master Timeline (30 FPS, 2400 Frames = 176 Beats / 44 Bars @ 132 BPM)
 * - Embeds all 7 official Chinese UI plates + live Bot Stage sequences (dispatch_light, 16-agent storm, squad finale)
 * - Independent controllable audio stems: public/audio/music_132bpm.wav & public/audio/sfx_ui.wav
 */
export const VarinPromo80s: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sec = frame / fps;

  return (
    <AbsoluteFill style={{background: VARIN_LIGHT.stageGradient}}>
      <Audio src={staticFile('audio/music_132bpm.wav')} volume={1.0} />
      <Audio src={staticFile('audio/sfx_ui.wav')} volume={0.80} />

      {/* ACT 1 (0.00 - 5.00s | Frames 0 - 150): Brand Collision, 10-Window Chaos Storm & Super Agent Implosion */}
      <Sequence from={0} durationInFrames={150} name="Act1-ChaosStormToSuperAgent">
        <Act1Intro />
      </Sequence>

      {/* ACT 2 (5.00 - 27.27s | Frames 150 - 818): Live Stage Dispatch, Radio, Chart, Choices & Live Slider Calculator */}
      <Sequence from={150} durationInFrames={668} name="Act2-LiveSessionAndCalculator">
        <Act2FullSession />
      </Sequence>

      {/* ACT 3A (27.27 - 31.82s | Frames 818 - 955): 3D Multi-Window Spatial Array */}
      <Sequence from={818} durationInFrames={137} name="Act3A-MultiWindow3DArray">
        <MultiWindowArray />
      </Sequence>

      {/* ACT 3B-C (31.82 - 45.45s | Frames 955 - 1364): Workbench Step-In -> In-Window IDE -> Dual-View Comparison */}
      <Sequence from={955} durationInFrames={409} name="Act3B-WorkbenchIDEDualView">
        <Act3WorkbenchIDEDual />
      </Sequence>

      {/* ACT 4A (45.45 - 52.73s | Frames 1364 - 1582): Diagonal Laser Wipe -> 3D Dark Codex & Claude Code */}
      <Sequence from={1364} durationInFrames={36} name="Act4A-TypewriterCodex">
        <TypewriterPrompt prefix="比如，" highlight="直接调度本机 Codex 组队攻坚？" />
      </Sequence>
      <Sequence from={1400} durationInFrames={182} name="Act4A-DarkCodexStage">
        <DarkShowcaseShot img="assets/dark_codex_workbench.png" pill="本机直调 Codex · Claude Code · ACP 协议工具" invertAngle={false} />
      </Sequence>

      {/* ACT 4B (52.73 - 61.82s | Frames 1582 - 1855): Dark Typewriter -> 2.5D Stepped DOCX/XLSX/PPTX */}
      <Sequence from={1582} durationInFrames={54} name="Act4B-TypewriterOffice">
        <TypewriterPrompt prefix="再比如，" highlight="查完文献顺手生成整套汇报？" />
      </Sequence>
      <Sequence from={1636} durationInFrames={219} name="Act4B-DarkOfficeStage">
        <DarkShowcaseShot img="assets/dark_research_office.png" pill="科研检索 + 原生导出 DOCX · XLSX · PPTX" invertAngle={true} />
      </Sequence>

      {/* ACT 5A (61.82 - 67.27s | Frames 1855 - 2018): Live 16-Agent & 12-Report Storm Hero Stage */}
      <Sequence from={1855} durationInFrames={163} name="Act5A-Live16AgentStorm">
        <Live16AgentStorm />
      </Sequence>

      {/* ACT 5B (67.27 - 72.73s | Frames 2018 - 2182): 3D 8-Card Capability Flywheel */}
      <Sequence from={2018} durationInFrames={164} name="Act5B-CapabilityFlywheel">
        <Act5OrbitRing />
      </Sequence>

      {/* ACT 5C (72.73 - 76.36s | Frames 2182 - 2291): 8-Beat Snare-Riser Rapid Climax Montage */}
      <Sequence from={2182} durationInFrames={109} name="Act5C-ClimaxRapidMontage">
        <ClimaxMontage />
      </Sequence>

      {/* ACT 5D (76.36 - 80.00s | Frames 2291 - 2400): Final Impact Hit & Living Squad Download Finale */}
      <Sequence from={2291} durationInFrames={109} name="Act5D-ImpactSquadFinale">
        <Act5DownloadFinale />
      </Sequence>
    </AbsoluteFill>
  );
};

const Act1Intro: React.FC = () => {
  const sec = useCurrentFrame() / 30;
  if (sec < 0.91) {
    return (
      <AbsoluteFill style={{background: '#121622', alignItems: 'center', justifyContent: 'center'}}>
        <div style={{color: '#f6f8fc', fontSize: 80, fontWeight: 800}}>Varin</div>
      </AbsoluteFill>
    );
  }
  if (sec < 2.75) {
    return (
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', fontSize: 64, fontWeight: 800, color: '#20272a'}}>
        还在十个窗口间来回救火？
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <div style={{fontSize: 68, fontWeight: 800, color: '#20272a'}}>
        交给 <span style={{color: '#345894', padding: '4px 18px', borderRadius: 20, background: 'rgba(62,99,158,0.14)'}}>Super Agent</span> 带队推进
      </div>
    </AbsoluteFill>
  );
};

const Act2FullSession: React.FC = () => {
  const sec = useCurrentFrame() / 30;
  if (sec < 11.25) {
    const inStage = sec >= 4.0;
    return (
      <>
        <Camera3DStage fx={inStage ? 1820 : 920} fy={inStage ? 510 : 1265} zoom={inStage ? 2.02 : 2.05} yawDeg={inStage ? 8.2 : -8.0} pitchDeg={4.5} rollDeg={inStage ? 1.6 : -2.0}>
          <Img src={staticFile('assets/varin-zh-CN.png')} style={{width: '100%', height: '100%'}} />
        </Camera3DStage>
        <CornerPill text={inStage ? 'Super Agent 实机舞台 · 自动派发多路负责人' : '一句话交办跨模块任务'} dotColor={inStage ? '#8ce071' : '#7aa7ef'} progress={1} align="left" />
      </>
    );
  }
  if (sec < 15.0) {
    return (
      <>
        <Camera3DStage fx={1065} fy={665} zoom={1.82} yawDeg={6.0} pitchDeg={4.2} rollDeg={-1.5}>
          <Img src={staticFile('assets/conversation-chart-zh-CN.png')} style={{width: '100%', height: '100%'}} />
        </Camera3DStage>
        <CornerPill text="同一会话持续深挖 · 自动生成对比图表" dotColor="#7aa7ef" progress={1} align="left" />
      </>
    );
  }
  if (sec < 18.6) {
    return (
      <>
        <Camera3DStage fx={720} fy={830} zoom={1.92} yawDeg={-6.5} pitchDeg={4.6} rollDeg={-1.4}>
          <Img src={staticFile('assets/conversation-choices-zh-CN.png')} style={{width: '100%', height: '100%'}} />
        </Camera3DStage>
        <CornerPill text="多选确认方向 · 一键生成完整稿" dotColor="#7aa7ef" progress={1} align="right" />
      </>
    );
  }
  return (
    <>
      <Camera3DStage fx={920} fy={750} zoom={1.84} yawDeg={5.8} pitchDeg={4.5} rollDeg={-1.2}>
        <Img src={staticFile('assets/conversation-zh-CN.png')} style={{width: '100%', height: '100%'}} />
      </Camera3DStage>
      <CornerPill text="对话内嵌原生交互组件 · 拖动滑块实时测算" dotColor="#7aa7ef" progress={1} align="right" />
    </>
  );
};

const MultiWindowArray: React.FC = () => {
  const lt = useCurrentFrame() / 30;
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'absolute', top: 58, fontSize: 50, fontWeight: 800, color: '#20272a', zIndex: 20}}>
        多视图同场推进 · <span style={{color: '#325a9e'}}>成员直连不黑盒</span>
      </div>
      <div style={{display: 'flex', gap: 36, alignItems: 'center', marginTop: 60, perspective: 1800}}>
        <Img src={staticFile('assets/varin-zh-CN.png')} style={{width: 520, borderRadius: 16, transform: `rotateY(18deg) translateY(${Math.sin(lt * 2) * 6}px)`}} />
        <Img src={staticFile('assets/workbench-zh-CN.png')} style={{width: 680, borderRadius: 18, boxShadow: '0 24px 60px rgba(20,30,50,0.18)', zIndex: 10}} />
        <Img src={staticFile('assets/ide-zh-CN.png')} style={{width: 520, borderRadius: 16, transform: `rotateY(-18deg) translateY(${Math.cos(lt * 2) * 6}px)`}} />
      </div>
    </AbsoluteFill>
  );
};

const Act3WorkbenchIDEDual: React.FC = () => {
  const sec = useCurrentFrame() / 30;
  if (sec < 7.73) {
    const stepIn = sec > 3.8;
    return (
      <>
        <Camera3DStage fx={stepIn ? 1805 : 1550} fy={stepIn ? 1175 : 550} zoom={stepIn ? 2.34 : 1.78} yawDeg={8.0} pitchDeg={4.2} rollDeg={stepIn ? 1.6 : -1.6}>
          <Img src={staticFile('assets/workbench-zh-CN.png')} style={{width: '100%', height: '100%'}} />
        </Camera3DStage>
        <CornerPill text={stepIn ? '定向插话 · 随时向指定成员补充要求' : '成员直连互发 · 代码改动逐轮留档'} dotColor={stepIn ? '#f4c56b' : '#8ce071'} progress={1} align="left" />
      </>
    );
  }
  if (sec < 10.91) {
    return (
      <>
        <Camera3DStage fx={650} fy={1155} zoom={2.25} yawDeg={-7.5} pitchDeg={5.5} rollDeg={-2.0}>
          <Img src={staticFile('assets/ide-zh-CN.png')} style={{width: '100%', height: '100%'}} />
        </Camera3DStage>
        <CornerPill text="同一会话直切内置 IDE · 7 门语言 LSP 秒级构建" dotColor="#8ce071" progress={1} align="right" />
      </>
    );
  }
  return (
    <>
      <Camera3DStage fx={1100} fy={580} zoom={1.66} yawDeg={4.5} pitchDeg={4.2} rollDeg={-0.8}>
        <Img src={staticFile('assets/conversation-reading-zh-CN.png')} style={{width: '100%', height: '100%'}} />
      </Camera3DStage>
      <CornerPill text="对话、工作台、IDE 无缝串联 · 随时深入细节" dotColor="#7aa7ef" progress={1} align="left" />
    </>
  );
};

const DarkShowcaseShot: React.FC<{img: string; pill: string; invertAngle: boolean}> = ({img, pill, invertAngle}) => {
  const lt = useCurrentFrame() / 30;
  const sign = invertAngle ? -1 : 1;
  const rightFocus = lt > 3.8;
  return (
    <>
      <Camera3DStage
        dark
        fx={rightFocus ? 1765 : 995}
        fy={rightFocus ? 535 : 610}
        zoom={rightFocus ? 1.96 : 1.74}
        yawDeg={(rightFocus ? -9.5 : 9.5) * sign}
        pitchDeg={4.5}
        rollDeg={-1.8 * sign}
      >
        <Img src={staticFile(img)} style={{width: '100%', height: '100%'}} />
      </Camera3DStage>
      <CornerPill text={pill} dotColor="#8ce071" progress={1} align={invertAngle ? 'right' : 'left'} />
    </>
  );
};

const Live16AgentStorm: React.FC = () => {
  const lt = useCurrentFrame() / 30;
  return (
    <AbsoluteFill style={{background: '#0d111a', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{position: 'absolute', top: 48, fontSize: 48, fontWeight: 800, color: '#f2f6fc'}}>
        16 位负责人并坐窗沿 · <span style={{color: '#7ab8ff'}}>多级子 Agent 并发风暴</span>
      </div>
      <Img
        src={staticFile('assets/stage_16_agent_storm.png')}
        style={{
          width: 1380,
          borderRadius: 28,
          border: '3px solid #6ea8fa',
          marginTop: 56,
          transform: `perspective(1800px) rotateY(${interpolate(lt, [0, 5.4], [-8, 8])}deg) rotateX(4deg)`,
        }}
      />
    </AbsoluteFill>
  );
};

const Act5OrbitRing: React.FC = () => {
  const lt = useCurrentFrame() / 30;
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <div style={{textAlign: 'center', zIndex: 10}}>
        <div style={{fontSize: 74, fontWeight: 800, color: '#20272a'}}>
          全场景，<span style={{color: '#345a9a'}}>都能带队</span>
        </div>
        <div style={{fontSize: 24, color: '#5c6672', marginTop: 14}}>
          编程工程 · 科研探索 · Office 办公 · 通用日常
        </div>
      </div>
      {Array.from({length: 8}).map((_, i) => {
        const ang = (i / 8) * Math.PI * 2 + lt * 0.95;
        const x = 960 + Math.sin(ang) * 710 - 168;
        const y = 540 + Math.cos(ang) * 220 - 103;
        return <Img key={i} src={staticFile(`assets/cap_card_${i}.png`)} style={{position: 'absolute', left: x, top: y, width: 336, height: 207}} />;
      })}
    </AbsoluteFill>
  );
};

const MONTAGE_ITEMS = [
  ['~90', '原生工具开箱即用', '读写 · 检索 · 终端 · 浏览器 · 图表 · 文档'],
  ['4 × 4', '四大模式 · 四套工作台', 'Agent · IDE · Research · Bot 自由切换'],
  ['CLI', '本机直调 Codex & Claude Code', '兼容 ACP 协议 · 多智能体混合编队'],
  ['9 种', '原生模型协议 · 本地自控', '自有 API Key · 数据留在你自己的主机'],
  ['7 门', '内置语言服务 · 秒级构建', 'TS · Python · Rust · Go · C/C++ · Java'],
  ['16 路', '团队并坐窗沿 · 不做黑盒', '多级子 Agent 并发 · 关键分歧才问你'],
  ['全平台', '桌面与容器一键部署', 'Windows · macOS · Linux · Docker'],
  ['随身连', 'Android · iOS 远程直连主机', '离开工位也能随时查看进度与拍板'],
];

const ClimaxMontage: React.FC = () => {
  const lt = useCurrentFrame() / 30;
  const idx = Math.min(7, Math.floor(lt / (60 / 132)));
  const [big, tit, sub] = MONTAGE_ITEMS[idx];
  return (
    <AbsoluteFill style={{background: '#0e1628', alignItems: 'center', justifyContent: 'center'}}>
      <div style={{padding: '44px 72px', borderRadius: 36, background: 'rgba(14,20,34,0.88)', border: '3px solid #60a5fa', textAlign: 'center'}}>
        <div style={{fontSize: 120, fontWeight: 800, color: '#76beff'}}>{big}</div>
        <div style={{fontSize: 58, fontWeight: 800, color: '#f8faff', marginTop: 8}}>{tit}</div>
        <div style={{fontSize: 26, color: '#e2eeff', marginTop: 22}}>{sub}</div>
      </div>
    </AbsoluteFill>
  );
};

const Act5DownloadFinale: React.FC = () => {
  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16}}>
      <Img src={staticFile('assets/stage_finale_squad.png')} style={{width: 560, height: 354}} />
      <div style={{fontSize: 58, fontWeight: 800, color: '#20272a'}}>Varin</div>
      <div style={{fontSize: 44, fontWeight: 800, color: '#20272a'}}>
        通用 Super Agent · <span style={{color: '#345ca2'}}>一次创新探索</span>
      </div>
      <div style={{padding: '13px 34px', borderRadius: 27, background: '#161c26', border: '2px solid #70a4f2', color: '#f6f8fc', fontSize: 21, fontWeight: 700}}>
        AGPL-3.0 开源免费 · 立即下载与源码构建 · github.com/Youzini-afk/Varin · varin.dev
      </div>
    </AbsoluteFill>
  );
};
