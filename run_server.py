"""Server runner script for Loan Easier web application."""

import sys
import uvicorn
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import HOST, PORT

def main():
    print(f"Starting Loan Easier server on http://{HOST}:{PORT}")
    uvicorn.run(
        "src.api.app:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )

if __name__ == "__main__":
    main()
