import time
import os
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from avatars.base_avatar import BaseAvatar
from utils.logger import logger

import requests

# Local LLM (Ollama OpenAI-compatible) + Josquin KB retrieval service
LLM_BASE_URL = os.environ.get('LT_LLM_BASE_URL', 'http://127.0.0.1:11434/v1')
LLM_MODEL = os.environ.get('LT_LLM_MODEL', 'qwen2.5:14b')
KB_URL = os.environ.get('LT_KB_URL', 'http://127.0.0.1:8100/retrieve')
KB_TOP_K = int(os.environ.get('LT_KB_TOPK', '4'))

SYSTEM_PROMPT = (
    "You are an art and music knowledge assistant for the Josquin Research Project, "
    "speaking aloud as a digital human. Answer briefly and conversationally (2-4 spoken "
    "sentences), in the same language the user asked in. Ground your answer ONLY in the "
    "reference material below; if it does not contain the answer, say you are not sure. "
    "Do not read out IDs, URLs or field names verbatim; speak naturally.\n\n"
    "Reference material:\n"
)


def _get_context(query, k=KB_TOP_K):
    """Fetch grounding context from the KB service; fail soft so the avatar
    still answers (ungrounded) if the KB is down."""
    try:
        r = requests.post(KB_URL, json={"query": query, "k": k}, timeout=10)
        return r.json().get("context", "")
    except Exception:
        logger.exception('kb retrieve failed')
        return ""


def llm_response(message, avatar_session: 'BaseAvatar', datainfo: dict = {}):
    try:
        opt = avatar_session.opt
        start = time.perf_counter()
        from openai import OpenAI
        client = OpenAI(
            api_key="ollama",  # Ollama ignores it; SDK requires non-empty
            base_url=LLM_BASE_URL,
        )
        context = _get_context(message)
        end = time.perf_counter()
        logger.info(f"llm Time init+retrieve: {end-start}s,{message}")
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{'role': 'system', 'content': SYSTEM_PROMPT + context},
                      {'role': 'user', 'content': message}],
            stream=True,
            stream_options={"include_usage": True}
        )
        result = ""
        first = True
        for chunk in completion:
            if len(chunk.choices) > 0:
                if first:
                    end = time.perf_counter()
                    logger.info(f"llm Time to first chunk: {end-start}s")
                    first = False
                msg = chunk.choices[0].delta.content
                if msg is None:
                    continue
                lastpos = 0
                for i, char in enumerate(msg):
                    if char in ",.!;:，。！？：；":
                        result = result + msg[lastpos:i+1]
                        lastpos = i + 1
                        if len(result) > 10:
                            logger.info(result)
                            avatar_session.put_msg_txt(result, datainfo)
                            result = ""
                result = result + msg[lastpos:]
        end = time.perf_counter()
        logger.info(f"llm Time to last chunk: {end-start}s")
        if result:
            avatar_session.put_msg_txt(result, datainfo)

    except Exception as e:
        logger.exception('llm exceptiopn:')
        return
