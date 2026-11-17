"""Run the Physical AI runtime: python -m physical_ai"""

from __future__ import annotations

import uvicorn

from physical_ai.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "physical_ai.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
