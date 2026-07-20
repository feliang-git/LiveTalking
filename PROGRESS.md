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

## Track B: SyncTalk_2D per-person model (Rupert) — trained
- Why: MuseTalk mouth jitter is architectural (frame-independent); per-person training is the fix. SyncTalk++ code unreleased; SyncTalk_2D (same authors, 328x328, realtime-capable) chosen over NeRF SyncTalk (no CUDA-ext/BFM blockers).
- Env: synctalk2d:h20 (torch 2.2.0+cu121). Repo at /raid/fei/workspaces/digital_human/SyncTalk_2D.
- Fixes: dataset __len__ clamp (audio feats vs frames off-by-3); inference mux moved outside container (conda ffmpeg lacks libx264).
- Trained: 100 epochs on H20 GPU 2 (~2h). Checkpoint: checkpoint/Rupert/99.pth.
- Output: result/Rupert_intro_en.mp4; side-by-side vs MuseTalk: result/compare_musetalk_vs_synctalk2d.mp4 (identical audio).
- Pending: user visual review -> if better, integrate into LiveTalking realtime (custom avatar module).

## Track B round 2: SyncTalk_2D training-code bugs found & fixed, two arms retrained
- v1 failure root causes (confirmed vs upstream issues UDH#196/#113/#90): SyncNet trained
  with positives only (degenerate, loss->0 means nothing), missing zero_grad, cosine->BCE
  range bug (2 places), audio-features/frames off-by-3 misalignment.
- Fixes in our SyncTalk_2D clone: negative sampling (50%, |offset|>10) + zero_grad +
  clamped (cos+1)/2 in both cosine_loss defs + feature tail trim to frames+1.
- Arm A (no syncnet, upstream-recommended): trained 100ep. Silence-A/B gate: audio drives
  mouth (diff 1.29 vs GT motion scale 1.77). -> synctalk2d_v2_intro_en.mp4
- Arm B (fixed syncnet, lr 1e-4; best syncnet loss ~0.39): trained 100ep. Silence-A/B:
  diff 1.80 — strongest audio response. -> synctalk2d_v2b_intro_en.mp4
- Diagnostic lesson: frame-diff/audio-envelope correlation metric was invalid (box on neck,
  and GT itself scores ~0.1); replaced with self-calibrating silent-audio A/B.
- Pending: user visual review of armA vs armB vs MuseTalk.

## Voice cloning (Rupert) — DONE
- GPT-SoVITS api_v2 on H20 GPU 1 :9880 (official docker image + HF pretrained weights).
- Zero-shot clone from a 5s lav-mic reference (auto-selected via whisper transcript).
- Wired into LiveTalking (--tts gpt-sovits); sovits client language un-hardcoded.
- Full-pipeline demo: intro_rupert_voice.mp4 (avatar + cloned voice), TTFA 1.69s,
  sovits first-chunk 0.39s (streaming, faster than edgetts), 25fps held.
- May control experiment settled the SyncTalk_2D question: same pipeline on
  spec-compliant data works (audio-response 5.10 vs 1.29/1.80 on our short data)
  -> awaiting 5-min Rupert re-recording for the stable-mouth track.

## Knowledge base: Josquin Research Project (www.josqu.in) — LIVE
- Ingested from official GitHub repos (NOT crawled; work pages are JS shells):
  jrp-scores (1387 kern scores w/ catalog metadata) + jrp-website (works/composers/
  sources/editions JSON + about/under-the-hood prose).
- Index: 1432 docs (1300+ works, 148 composers, prose chunks), bge-m3 embeddings.
- Services on H20: kb_server :8100 (retrieval, container kb_server),
  Ollama :11434 GPU3 (bge-m3 + qwen2.5:14b, keep_alive=-1 prewarmed),
  GPT-SoVITS :9880 GPU1 (Rupert voice), LiveTalking :8010 GPU0.
- E2E chat validated: question -> retrieve -> qwen -> Rupert voice -> avatar,
  3.5 s to first spoken word, 25 fps. Demo: kb_chat_demo.mp4.
- Answer grounding verified: "La Bernardina is a secular work composed by
  Josquin des Prez" (top-1 retrieval Jos2721, correct).

## Background replacement: green screen -> office — DONE
- RobustVideoMatting (GPU) alpha matte per frame; ffmpeg chromakey rejected
  (semi-transparent shirt + cloth-fold remnants). Office bg (empty modern
  office, slight gaussian depth blur). New source: source_clips/rupert_office.mp4.
- New avatar bundle: musetalk_rupert_office (green-screen original kept).
- Serving config unchanged otherwise; demo: intro_office.mp4 (Rupert voice,
  ttfa 1.72s, 25fps).
