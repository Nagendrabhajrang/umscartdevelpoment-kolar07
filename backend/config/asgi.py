"""UMS Mart ASGI entry point (ready for future async/websocket use)."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.asgi import get_asgi_application  # noqa: E402

application = get_asgi_application()
