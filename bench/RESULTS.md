# Real-time avatar experiments — results log

Server: H20-GPU-12 (8x H20-3e), image livetalking:h20, GPU 0, --network host.
Client: bench/rtc_bench.py (headless aiortc, same host, no STUN).

## Baseline (2026-07 / commit lipsync-realtime)

Config: musetalk v1.5, avatar musetalk_rupert (30s@25fps 1080p source),
batch_size=16, fps=25, l=10 r=10, tts=edgetts (zh-CN-YunxiaNeural), ~50-char text.

| metric | value |
|---|---|
| connect_time | 0.60 s |
| idle_fps (client-received) | 25.16 |
| ttfa (submit -> first audible) | 6.62 s |
| speak_fps (client-received) | 25 sustained (31.2 incl. catch-up burst) |
| frame_interval p50 / p95 / max | 39.7 / 43.1 / 86.4 ms |
| server UNet+VAE infer fps (batch 16) | 82.1 |
| edge-tts synthesis time | 2.53 s |

Findings:
- GPU has 3.3x headroom (82 fps vs 25 needed) -> room for smaller batches + quality passes.
- TTFA 6.6s breakdown: 2.5s edgetts full-utterance synth (non-streaming backend);
  remainder = pipeline fill (batch 16 = 640 ms granularity, ASR l/r context, warmup) — to instrument.
- Delivery cadence stable (p95 43 ms ~ 25fps), single 86 ms hiccup.

Known env quirks (this box):
- Expose ONE GPU per container (CUDA_VISIBLE_DEVICES=N); torch 2.9.1+cu130 asserts with all 8 visible.
- LT_STUN_URL= (empty) required: public STUN unreachable; and same-host bench needs host candidates only.
