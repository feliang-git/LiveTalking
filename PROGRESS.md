# Avatar Real-Time Quality Campaign — Progress Log

Goal: avatar speaks a given prompt; refined mouth effect; single-stream stays real-time (25fps).
Hardware: H20-GPU-12, GPU 0 for serving. All numbers from bench/rtc_bench.py (same-host headless client).
Details & raw numbers: bench/RESULTS.md. Video artifacts: bench/runs/*.mp4 (server, gitignored).

## CURRENT BEST
- branch/tag: `best` (git tag, moved when a config wins an A/B)
- launch: `docker run ... -e LT_STUN_URL= -e LT_SILENCE_RMS=0.005 -e LT_EMA_ALPHA=0.7 ... python app.py --transport webrtc --model musetalk --avatar_id musetalk_rupert --batch_size 4`
- status: batch 4 + silence gate + EMA mouth smoothing (A/B validated, latency-safe)
- metrics: infer ~45 fps | delivered 25 fps | warm ttfa 1.63 s (baseline was 6.6 s)

## Timeline
- [x] H20 docker env (torch 2.9.1+cu130) + MuseTalk v1.5 weights + 3 avatar bundles (rupert/jamie/jesse)
- [x] Real-time WebRTC serving verified end-to-end; headless bench client built
- [x] Baseline measured (see CURRENT BEST); 2 upstream bugs found & fixed (STUN config, codec-prefs-by-kind)
- [x] batch_size sweep 16/8/4 -> winner batch 4 (warm ttfa 2.1->1.5 s)
- [x] silence gate (RMS) + causal EMA mouth smoothing behind env flags, A/B -> both adopted
- [ ] bbox_shift sweep for mouth alignment (visual)  <- variants built, recording next
- [ ] TTS/time-to-first-audio reduction
