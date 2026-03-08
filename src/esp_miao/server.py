import uvicorn
import os
import logging
from .config import LOG_LEVEL
from .version import __version__

logger = logging.getLogger("esp-miao.server")

def main():
    """Run server with uvicorn."""
    # 讀取環境變數，預設關閉 reload 以節省 RPi4 資源
    reload_enabled = os.getenv("SERVER_RELOAD", "0") == "1"
    
    logger.info(f"Starting ESP-MIAO Server v{__version__} (reload={'enabled' if reload_enabled else 'disabled'})...")

    uvicorn.run(
        "esp_miao.app:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
        reload_dirs=["src"] if reload_enabled else None,
        log_level="info",
    )


if __name__ == "__main__":
    # Setup basic logging for main entry point
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()
