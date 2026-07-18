import os
import re
import time
import asyncio
import numpy as np
import resampy
import soundfile as sf
import edge_tts
from io import BytesIO

from utils.logger import logger
from .base_tts import BaseTTS, State
from registry import register

@register("tts", "edgetts")
class EdgeTTS(BaseTTS):
    def txt_to_audio(self,msg:tuple[str, dict]):
        text,textevent = msg
        voice = self.opt.REF_FILE or "zh-CN-YunxiaNeural" 
        voicename = textevent.get('tts', {}).get('ref_file',voice) #self.opt.REF_FILE #"zh-CN-YunxiaNeural"
        # Sentence-level pipelining (LT_TTS_SENTENCE_SPLIT=1): synthesize and
        # feed one sentence at a time so time-to-first-audio ~= first-sentence
        # synthesis instead of the whole utterance. Default: previous behavior.
        if os.environ.get('LT_TTS_SENTENCE_SPLIT') == '1':
            pieces = [p for p in re.split(r'(?<=[。！？!?.；;])', text) if p.strip()]
        else:
            pieces = [text]

        t = time.time()
        started = False
        for pi, piece in enumerate(pieces):
            if self.state != State.RUNNING:
                break
            asyncio.new_event_loop().run_until_complete(self.__main(voicename, piece))
            if pi == 0:
                logger.info(f'-------edge tts time:{time.time()-t:.4f}s')
            _dt0 = time.time()
            if self.input_stream.getbuffer().nbytes<=0: #edgetts err
                logger.error('edgetts err!!!!!')
                continue

            self.input_stream.seek(0)
            stream = self.__create_bytes_stream(self.input_stream)
            if pi == 0:
                logger.info(f'[timing] tts decode+resample: {time.time()-_dt0:.3f}s')
            streamlen = stream.shape[0]
            idx=0
            last_piece = (pi == len(pieces) - 1)
            while streamlen >= self.chunk and self.state==State.RUNNING:
                eventpoint={}
                streamlen -= self.chunk
                if not started:
                    eventpoint={'status':'start','text':text}
                    started = True
                elif last_piece and streamlen<self.chunk:
                    eventpoint={'status':'end','text':text}
                eventpoint.update(**textevent) #eventpoint={'status':'end','text':text,'msgevent':textevent}
                self.parent.put_audio_frame(stream[idx:idx+self.chunk],eventpoint)
                idx += self.chunk
            self.input_stream.seek(0)
            self.input_stream.truncate() 

    def __create_bytes_stream(self,byte_stream):
        #byte_stream=BytesIO(buffer)
        stream, sample_rate = sf.read(byte_stream) # [T*sample_rate,] float64
        logger.info(f'[INFO]tts audio stream {sample_rate}: {stream.shape}')
        stream = stream.astype(np.float32)

        if stream.ndim > 1:
            logger.info(f'[WARN] audio has {stream.shape[1]} channels, only use the first.')
            stream = stream[:, 0]
    
        if sample_rate != self.sample_rate and stream.shape[0]>0:
            logger.info(f'[WARN] audio sample rate is {sample_rate}, resampling into {self.sample_rate}.')
            stream = resampy.resample(x=stream, sr_orig=sample_rate, sr_new=self.sample_rate)

        return stream
    
    async def __main(self,voicename: str, text: str):
        try:
            communicate = edge_tts.Communicate(text, voicename)

            #with open(OUTPUT_FILE, "wb") as file:
            first = True
            async for chunk in communicate.stream():
                if first:
                    first = False
                if chunk["type"] == "audio" and self.state==State.RUNNING:
                    #self.push_audio(chunk["data"])
                    self.input_stream.write(chunk["data"])
                    #file.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    pass
        except Exception as e:
            logger.exception('edgetts')
