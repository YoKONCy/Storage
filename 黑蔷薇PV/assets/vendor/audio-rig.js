/* =========================================================
 * audio-rig.js —— 镜头内「有机反应层」读取工具（时间的纯函数）
 * 数据：window.AUDIO_EVENTS（由 analysis/onsets.py 生成的本地包）
 *
 * 三层时间结构里的「细层」：粗切点看 song.json，镜头叙事看各镜头
 * 微事件表，而画面的呼吸/微颤/冲击踩真实乐器点，全走这里。
 *
 * 注意（渲染铁律）：本文件不读音频、不 fetch、不用墙钟，
 * 同一 t 永远返回同一结果，seek 逐帧渲染可复现。
 * ========================================================= */
(function () {
  var D = window.AUDIO_EVENTS;
  if (!D) { console.warn("[audio-rig] 缺少 window.AUDIO_EVENTS，请先引入 audio-events.js"); }

  // 确定性小随机（每个起音事件的方向在其整个衰减期内保持不变）
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  var Rig = {
    /** 50fps 包络线性插值。name: rms|low|mid|high|voice|onset；越界钳制到端点。 */
    env: function (name, t) {
      if (!D) return 0;
      var v = D.env[name];
      if (!v) return 0;
      var x = Math.max(0, t) * D.fps, i = Math.floor(x), n = v.length;
      if (i >= n - 1) return v[n - 1];
      var f = x - i;
      return v[i] * (1 - f) + v[i + 1] * f;
    },

    /**
     * 离散起音的指数衰减核求和（连续脉冲，适合发光/发热/抖动强度）。
     * opts: { band:-1|0low|1mid|2high, excludeBand:2(排除纯镲片), minS:.55, half:.12, win:.6 }
     */
    hits: function (t, opts) {
      if (!D) return 0;
      opts = opts || {};
      var band = opts.band != null ? opts.band : -1;
      var exBand = opts.excludeBand != null ? opts.excludeBand : -1;
      var minS = opts.minS != null ? opts.minS : .55;
      var half = opts.half != null ? opts.half : .12;
      var win = opts.win != null ? opts.win : .6;
      var list = D.onsets, sum = 0;
      for (var i = 0; i < list.length; i++) {
        var o = list[i];
        if (o.t > t) break;
        var dt = t - o.t;
        if (dt > win) continue;
        if (band >= 0 && o.b !== band) continue;
        if (exBand >= 0 && o.b === exBand) continue;
        if (o.s < minS) continue;
        sum += o.s * Math.pow(2, -dt / half);
      }
      return Math.min(1.4, sum);
    },

    /**
     * 方向固定的冲击位移（适合镜头/元素震屏）：每次起音给一个随机角度，
     * 该角度在整个指数衰减期内不变——所以看到的是「一击弹回」而非每帧乱抖。
     * 返回 {x,y,amp}（amp 0..~1.4），方向种子按起音时间锁定。
     * opts 同 hits；调用方把 x/y 乘自己的像素量程即可。
     */
    shake: function (t, opts) {
      if (!D) return { x: 0, y: 0, amp: 0 };
      opts = opts || {};
      var band = opts.band != null ? opts.band : -1;
      var exBand = opts.excludeBand != null ? opts.excludeBand : -1;
      var minS = opts.minS != null ? opts.minS : .55;
      var half = opts.half != null ? opts.half : .10;
      var win = opts.win != null ? opts.win : .45;
      var list = D.onsets, best = null, bestW = 0;
      for (var i = 0; i < list.length; i++) {
        var o = list[i];
        if (o.t > t) break;
        var dt = t - o.t;
        if (dt > win) continue;
        if (band >= 0 && o.b !== band) continue;
        if (exBand >= 0 && o.b === exBand) continue;
        if (o.s < minS) continue;
        var w = o.s * Math.pow(2, -dt / half);
        if (w > bestW) { bestW = w; best = o; }
      }
      if (!best) return { x: 0, y: 0, amp: 0 };
      // 用起音时间（×1000 取整）做种子：同一次冲击的每一帧方向一致
      var rnd = mulberry32(Math.round(best.t * 1000) + (opts.seed || 0));
      var ang = rnd() * Math.PI * 2;
      return { x: Math.cos(ang), y: Math.sin(ang), amp: Math.min(1.4, bestW) };
    },

    /** 连续包络的「起音」：当前帧正增量放大，给连续织体一个无离散事件的刺点。 */
    envPulse: function (name, t) {
      if (!D) return 0;
      var dt = 1 / D.fps;
      var d = Rig.env(name, t) - Rig.env(name, t - dt);
      return Math.max(0, d) * 2.2;
    }
  };

  window.AudioRig = Rig;
})();
