# Avatar Real-Time Quality Campaign — Progress Log

Goal: avatar speaks a given prompt; refined mouth effect; single-stream stays real-time (25fps).
Hardware: H20-GPU-12, GPU 0 for serving. All numbers from bench/rtc_bench.py (same-host headless client).
Details & raw numbers: bench/RESULTS.md. Video artifacts: bench/runs/*.mp4 (server, gitignored).

## CURRENT BEST
- branch/tag: `best` (git tag, moved when a config wins an A/B)
- launch: `docker run ... -e LT_STUN_URL= -e LT_SILENCE_RMS=0.005 -e LT_EMA_ALPHA=0.7 -e LT_TTS_PREWARM=1 -e LT_TTS_SENTENCE_SPLIT=1 ... python app.py --transport webrtc --model musetalk --avatar_id musetalk_rupert --batch_size 4` + `bench/boot_warm.sh` once after boot; add `-e LT_VIDEO_BITRATE=6000000` for 1080p clarity
- status: FINAL (overnight campaign complete) — batch 4 + silence gate + EMA smoothing + TTS sentence-split + prewarm + boot self-warm
- metrics: TTFA 1.33-1.42 s (from 6.6 s baseline, -80%) | 25 fps held | p95 frame interval 44 ms

## Timeline
- [x] H20 docker env (torch 2.9.1+cu130) + MuseTalk v1.5 weights + 3 avatar bundles (rupert/jamie/jesse)
- [x] Real-time WebRTC serving verified end-to-end; headless bench client built
- [x] Baseline measured (see CURRENT BEST); 2 upstream bugs found & fixed (STUN config, codec-prefs-by-kind)
- [x] batch_size sweep 16/8/4 -> winner batch 4 (warm ttfa 2.1->1.5 s)
- [x] silence gate (RMS) + causal EMA mouth smoothing behind env flags, A/B -> both adopted
- [x] bbox_shift sweep -> all variants within noise, keep default 0 (videos+filmstrips saved)
- [x] TTS sentence-split + prewarm + boot self-warm -> first utterance 4.7->1.33 s
- [x] cross-person videos (jamie/jesse) under best config for morning review
