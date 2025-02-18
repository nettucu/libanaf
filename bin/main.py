#!/usr/bin/env python

import os
import sys
from pathlib import Path

## need to setup paths before import or should we setup the python path accordingly ?
from libanaf.cli import app  # noqa: E402

APP_HOME = Path(__file__).parent.parent.resolve().absolute()
sys.path.append(str(APP_HOME / "libanaf"))
os.environ["APP_HOME"] = str(APP_HOME)
os.chdir(APP_HOME)

if __name__ == "__main__":
    app()

