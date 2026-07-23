"""Development and WSGI entry point for CryoCheck."""

from __future__ import annotations

import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")))
