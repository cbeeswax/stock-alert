#!/usr/bin/env python
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.data.download_data import main


if __name__ == "__main__":
    sys.exit(main())
