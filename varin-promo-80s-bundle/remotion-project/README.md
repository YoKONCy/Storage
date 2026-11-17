# Varin B站 88秒完整版宣传片 — Remotion 工程与分轨归档说明

## 1. 目录结构
- `../varin-promo-full-88s.mp4`：已渲染完成的 88 秒 1080P 30FPS 成片（H.264 / AAC 192kbps）
- `../audio/`：独立分离式立体声音轨（44.1kHz 16-bit WAV）
  - `music_132bpm.wav`：纯 132 BPM 电子律动配乐轨（含前奏、主律动、打字机呼吸留白、暗色空间低音下潜、高潮与尾音收束）
  - `sfx_ui.wav`：纯拟真交互音效轨（机械键盘连击、打字机敲击、鼠标点击确认、横向甩镜气声、构建完成提示音）
  - `master_mix.wav`：成片最终混音母带（本片采用无口播纯音乐节奏形式，如需后期补录人声口播，可直接基于 `music_132bpm.wav` 做侧链闪避混音）
- `remotion-project/`：可直接在本地启动编辑的 Remotion 4.x TypeScript 工程
  - `src/VarinPromo88s.tsx`：全片五幕（2640 帧 @ 30fps）主时间轴与独立双音轨挂载
  - `src/components/`：`Camera3DStage`（3D 透视矩阵舞台）、`CornerPill`（极简黑底胶囊标）、`TypewriterPrompt`（白底打字机设问卡）
  - `public/assets/`：全套 2x 高分界面底板、深色实机画面、8 张全场景能力卡与官方矢量吉祥物资产

## 2. 本地运行与二次微调命令
```bash
cd remotion-project
bun install   # 或 npm install
bun run start # 打开 Remotion Studio 实时拖动时间轴预览与改字
bun run build # 重新导出 H.264 MP4
```
