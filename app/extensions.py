"""Application extension registration.

The function is intentionally empty until CryoCheck needs shared Flask
extensions. Keeping the hook in the factory avoids coupling future extensions
to a global application instance.
"""

from __future__ import annotations

from flask import Flask


def init_extensions(app: Flask) -> None:
    """Initialize Flask extensions for an application instance."""
    pass
