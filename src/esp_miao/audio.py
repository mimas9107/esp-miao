import base64
import io
import time
import logging
import asyncio
from struct import pack
from typing import Optional
from faster_whisper import WhisperModel
from .config import inference_executor

logger = logging.getLogger("esp-miao.audio")

# --- ASR Pipeline (Faster-Whisper) ---
whisper_model: Optional[WhisperModel] = None

def get_whisper_model() -> WhisperModel:
    """單例模式獲取 Whisper 模型，支援延遲加載。"""
    global whisper_model
    if whisper_model is None:
        logger.info("Initializing Whisper model (base, cpu)...")
        start_time = time.perf_counter()
        whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        elapsed = time.perf_counter() - start_time
        logger.info(f"Whisper model loaded in {elapsed:.2f} seconds.")
    return whisper_model


async def transcribe_audio(
    audio_base64: str, audio_format: str = "pcm_16k_16bit"
) -> str:
    """
    Transcribe audio to text using faster-whisper.
    """
    try:
        model = get_whisper_model()
        
        # Decode base64 to bytes
        audio_bytes = base64.b64decode(audio_base64)
        
        # 使用 io.BytesIO 在記憶體中建立 WAV 格式資料，避免磁碟 I/O
        wav_buf = io.BytesIO()
        sample_rate = 16000
        bits_per_sample = 16
        channels = 1
        data_size = len(audio_bytes)
        
        wav_buf.write(b"RIFF")
        wav_buf.write(pack("<I", 36 + data_size))
        wav_buf.write(b"WAVE")
        wav_buf.write(b"fmt ")
        wav_buf.write(pack("<I", 16))
        wav_buf.write(pack("<H", 1))
        wav_buf.write(pack("<H", channels))
        wav_buf.write(pack("<I", sample_rate))
        wav_buf.write(pack("<I", sample_rate * channels * (bits_per_sample // 8)))
        wav_buf.write(pack("<H", channels * (bits_per_sample // 8)))
        wav_buf.write(pack("<H", bits_per_sample))
        wav_buf.write(b"data")
        wav_buf.write(pack("<I", data_size))
        wav_buf.write(audio_bytes)
        wav_buf.seek(0)

        # 定義阻塞推論的同步函式
        def run_transcription():
            segments, info = model.transcribe(
                wav_buf, 
                beam_size=3, # 優化：縮小 beam_size 換取速度
                language="zh",
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0
            )
            
            text_segments = []
            for segment in segments:
                if segment.no_speech_prob < 0.7:
                    clean_text = segment.text.strip()
                    # 幻聽攔截邏輯保持不變
                    if len(clean_text) >= 4:
                        half = len(clean_text) // 2
                        if clean_text[:half] == clean_text[half:]:
                            continue
                        if all(c == clean_text[0] for c in clean_text[:4]):
                            continue
                    text_segments.append(clean_text)
            return "".join(text_segments).strip(), info

        # 使用全域受限的 executor 執行阻塞式的 Whisper 推論，防止 CPU 飽和
        loop = asyncio.get_event_loop()
        text, info = await loop.run_in_executor(inference_executor, run_transcription)
        
        if text:
            logger.info(f"ASR (Whisper) [{info.language}]: {text}")
        return text

    except Exception as e:
        logger.error(f"ASR error: {e}")
        return ""
