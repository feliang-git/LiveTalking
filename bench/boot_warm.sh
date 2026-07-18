#!/bin/bash
# Boot self-warm: after server start, drive ONE real utterance through the full
# pipeline (session + TTS + UNet). The first real UNet batch per process pays a
# one-time ~2.9s lazy-init cost on H20 that synthetic warmup does not cover;
# this pays it before any user connects. Run after "start http server" appears.
REPO=${REPO:-/raid/fei/workspaces/digital_human/LiveTalking}
docker run --rm --network host -v $REPO:/workspace livetalking:h20 \
  python bench/rtc_bench.py --idle-secs 1 --measure-secs 4 --text "你好。" >/dev/null 2>&1
echo "boot warm done"
