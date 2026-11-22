"""UMS Mart WSGI entry point."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
