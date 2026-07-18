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

## Experiment 1 — batch_size sweep (16/8/4, 2 reps, rupert)

| batch | warm TTFA | infer fps | delivered p95 | granularity |
|---|---|---|---|---|
| 16 | 2.09 s | ~79 | 42.4 ms | 640 ms |
| 8  | 2.03 s | ~63 | 42.7 ms | 320 ms |
| 4  | **1.51 s** | ~51 | 43.2 ms | 160 ms |

Winner: batch_size=4 (-0.6 s TTFA, still 2x fps headroom). Cold rep-1 TTFA ~4.6-5.0 s
at every batch -> first-utterance cost is TTS-side (see Experiment 3 target).
Videos: bench/runs/batch{16,8,4}_rep{1,2}.mp4

## Experiment 2 — quality A/B @ batch 4 (ctrl/gate/ema/both, 2 reps)

| variant | warm TTFA | p95 | infer fps | note |
|---|---|---|---|---|
| ctrl | 1.70 s | 44.5 ms | ~49 | |
| gate (RMS 0.005) | 1.56 s | 44.0 ms | ~50 | no onset delay; mouth rests in tail/pauses |
| ema (alpha 0.7) | 1.67 s | 44.4 ms | ~48 | frame check: no ghosting |
| both | 1.63 s | 44.9 ms | ~45 | ADOPTED as best |

All variants hold 25 fps delivery. Videos: bench/runs/q_{ctrl,gate,ema,both}_rep{1,2}.mp4

## Experiment 3 — bbox_shift (visual, 5 variants)

Mouth-activity (mean abs frame diff, speech window): default 0.657, -7: 0.632,
-4: 0.623, +4: 0.651, +7: 0.657 -> all within noise; no blending artifacts.
KEEP default bbox_shift=0. Artifacts: bench/runs/bbox_*.mp4, strip_*.jpg (filmstrips).

## Experiment 4 — TTS + first-utterance latency

- Sentence split (LT_TTS_SENTENCE_SPLIT=1): first-piece synth 2.5s -> ~0.48s;
  warm TTFA 1.63 -> 1.32-1.48s. ADOPTED.
- Prewarm (LT_TTS_PREWARM=1): edge-tts DNS/TLS + resampy numba JIT (~0.8s). ADOPTED.
- Cold-start investigation: remaining ~2.9s isolated via staged timing to the FIRST
  REAL UNet forward per process (pe 3ms / unet 2865ms / vae 52ms). Synthetic warmup
  (even exact fp16 shapes, thread-context variants) does NOT cover it — lazy init
  tied to the real execution context. FIX: bench/boot_warm.sh drives one real
  utterance through the full pipeline after boot. Validated: first user utterance
  1.33s / 1.42s (2 reps), 25 fps, p95 44 ms.

## Cross-person (identical best config)
jamie / jesse recorded: bench/runs/person_musetalk_{jamie,jesse}.mp4 — both 25 fps stable.

## FINAL BEST CONFIG
docker run ... -e LT_STUN_URL= -e LT_SILENCE_RMS=0.005 -e LT_EMA_ALPHA=0.7 \
  -e LT_TTS_PREWARM=1 -e LT_TTS_SENTENCE_SPLIT=1 ... \
  python app.py --transport webrtc --model musetalk --avatar_id musetalk_rupert --batch_size 4
# then once: bash bench/boot_warm.sh
Warm TTFA ~1.35 s | first utterance after boot ~1.33 s | 25 fps | p95 44 ms
