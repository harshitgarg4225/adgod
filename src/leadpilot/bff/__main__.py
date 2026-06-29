"""`python -m leadpilot.bff` — run the BFF with uvicorn (dev / default container CMD)."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "leadpilot.bff.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("ENVIRONMENT", "development") == "development",
    )
