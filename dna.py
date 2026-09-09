#!/usr/bin/env python
"""零安裝啟動器：python dna.py <command>

不想 pip install 也能直接用。裝過之後 `python -m design_dna` 等效。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from design_dna.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
