"""Headless WebRTC benchmark client for LiveTalking.

Connects to /offer, receives audio+video, then submits a text utterance via
/human and measures:
  - idle_fps: received video fps before speaking
  - ttfa: time from /human submit to first audible audio frame (RMS gate)
  - speak_fps: received video fps while speaking
  - frame interval p50/p95/max during speaking (jitter)

Usage (inside the livetalking:h20 container, --network host):
  python bench/rtc_bench.py --url http://127.0.0.1:8010 --text "..." [--record out.mp4]
"""
import argparse
import asyncio
import logging
import os
import json
import time

import aiohttp
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from aiortc.contrib.media import MediaRecorder, MediaRelay

RMS_THRESH = 0.01  # int16-normalized loudness gate for "audible"


class Meter:
    def __init__(self):
        self.video_ts = []          # arrival time of every video frame
        self.first_video_ts = None
        self.submit_ts = None
        self.speak_start_ts = None  # first audible audio frame after submit
        self.last_audible_ts = None

    def on_video(self):
        now = time.perf_counter()
        if self.first_video_ts is None:
            self.first_video_ts = now
        self.video_ts.append(now)

    def on_audio(self, frame):
        now = time.perf_counter()
        pcm = frame.to_ndarray().astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(pcm ** 2)))
        if rms > RMS_THRESH:
            self.last_audible_ts = now
            if self.submit_ts and self.speak_start_ts is None:
                self.speak_start_ts = now

    def fps_between(self, t0, t1):
        n = sum(1 for t in self.video_ts if t0 <= t <= t1)
        return n / (t1 - t0) if t1 > t0 else 0.0

    def intervals_between(self, t0, t1):
        ts = [t for t in self.video_ts if t0 <= t <= t1]
        return np.diff(ts) if len(ts) > 2 else np.array([])


async def consume(track, meter):
    while True:
        frame = await track.recv()
        if track.kind == "video":
            meter.on_video()
        else:
            meter.on_audio(frame)


async def run(args):
    meter = Meter()
    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[]))  # host-only candidates for same-host bench
    pc.addTransceiver("audio", direction="recvonly")  # audio FIRST: server assumes transceiver[1] is video
    pc.addTransceiver("video", direction="recvonly")
    tasks = []
    relay = MediaRelay()
    recorder = MediaRecorder(args.record) if args.record else None

    @pc.on("track")
    def on_track(track):
        tasks.append(asyncio.ensure_future(consume(relay.subscribe(track), meter)))
        if recorder:
            recorder.addTrack(relay.subscribe(track))

    await pc.setLocalDescription(await pc.createOffer())
    async with aiohttp.ClientSession() as http:
        async with http.post(args.url + "/offer", json={
            "sdp": pc.localDescription.sdp, "type": pc.localDescription.type,
        }) as resp:
            ans = await resp.json()
        sessionid = ans.get("sessionid")
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=ans["sdp"], type=ans["type"]))

        if recorder:
            await recorder.start()
        # wait for first video frame (connection up)
        t0 = time.perf_counter()
        while meter.first_video_ts is None:
            if time.perf_counter() - t0 > 45:
                raise RuntimeError("no video frame within 45s of answer")
            await asyncio.sleep(0.05)
        connect_time = meter.first_video_ts - t0

        # idle measurement window
        idle_t0 = time.perf_counter()
        await asyncio.sleep(args.idle_secs)
        idle_t1 = time.perf_counter()

        # submit utterance
        meter.submit_ts = time.perf_counter()
        human_req = {"sessionid": sessionid,
                     "type": "chat" if args.chat else "echo",
                     "text": args.text, "interrupt": True}
        if args.tts_voice:
            human_req["tts"] = {"ref_file": args.tts_voice}
        async with http.post(args.url + "/human", json=human_req) as resp:
            r = await resp.json()
            assert r.get("code") == 0, f"/human failed: {r}"

        # wait for speech to start
        while meter.speak_start_ts is None:
            if time.perf_counter() - meter.submit_ts > args.speak_timeout:
                break
            await asyncio.sleep(0.02)

        result = {
            "connect_time_s": round(connect_time, 3),
            "idle_fps": round(meter.fps_between(idle_t0, idle_t1), 2),
        }
        if meter.speak_start_ts is None:
            result["error"] = f"no audible audio within {args.speak_timeout}s (TTS failed or too slow?)"
        else:
            # measure while speaking: until audio has been quiet for 1.5s or cap
            speak_t0 = meter.speak_start_ts
            cap = speak_t0 + args.measure_secs
            while time.perf_counter() < cap:
                if meter.last_audible_ts and time.perf_counter() - meter.last_audible_ts > 1.5:
                    break
                await asyncio.sleep(0.1)
            speak_t1 = meter.last_audible_ts or time.perf_counter()
            iv = meter.intervals_between(speak_t0, speak_t1)
            result.update({
                "ttfa_s": round(meter.speak_start_ts - meter.submit_ts, 3),
                "speak_secs_measured": round(speak_t1 - speak_t0, 2),
                "speak_fps": round(meter.fps_between(speak_t0, speak_t1), 2),
                "frame_interval_p50_ms": round(float(np.percentile(iv, 50)) * 1000, 1) if iv.size else None,
                "frame_interval_p95_ms": round(float(np.percentile(iv, 95)) * 1000, 1) if iv.size else None,
                "frame_interval_max_ms": round(float(iv.max()) * 1000, 1) if iv.size else None,
            })
        print(json.dumps(result, ensure_ascii=False))

    if recorder:
        await recorder.stop()
    for t in tasks:
        t.cancel()
    await pc.close()


if __name__ == "__main__":
    if os.environ.get("ICE_DEBUG"):
        logging.basicConfig(level=logging.DEBUG)
        logging.getLogger("aiortc").setLevel(logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8010")
    ap.add_argument("--text", default="你好，我是数字人。今天天气不错，我们来聊一聊人工智能的发展历史。语音合成和唇形同步技术正在快速进步。")
    ap.add_argument("--idle-secs", type=float, default=6)
    ap.add_argument("--speak-timeout", type=float, default=25)
    ap.add_argument("--measure-secs", type=float, default=25)
    ap.add_argument("--record", default="", help="record received A/V to this mp4 path")
    ap.add_argument("--tts-voice", default="", help="edge-tts voice override, e.g. en-US-GuyNeural")
    ap.add_argument("--chat", action="store_true", help="use chat mode (LLM+RAG) instead of echo")
    args = ap.parse_args()
    asyncio.run(run(args))
