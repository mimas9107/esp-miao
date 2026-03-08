import asyncio
import logging
from .config import LOCAL_SOUND_DIR

logger = logging.getLogger("esp-miao.utils")

async def play_local_sound(filename: str):
    """Play a sound file locally on the server using non-blocking subprocess."""
    if not filename:
        return

    sound_path = LOCAL_SOUND_DIR / filename
    if not sound_path.exists():
        logger.warning(f"Local sound file not found: {sound_path}")
        return

    try:
        logger.info(f"Playing local sound: {filename}")
        # 使用 asyncio 的子進程管理，能自動處理收割 (reap) 以防止殭屍進程 <defunct>
        proc = await asyncio.create_subprocess_exec(
            "aplay", str(sound_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        # 在背景等待進程結束，不阻塞當前的 WebSocket 任務
        asyncio.create_task(proc.wait())
    except Exception as e:
        logger.error(f"Failed to play local sound {filename}: {e}")


def get_action_sound(target: str, value: str) -> str:
    """Determine the sound file to play based on the action target and value."""
    if target == "light":
        return "lightopen.wav" if value == "on" else "lightclose.wav"
    
    # Default success sound for other devices
    return "success.wav"
