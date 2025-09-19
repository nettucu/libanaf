#!/usr/bin/env python

import os
import sys
from pathlib import Path

## need to setup paths before import or should we setup the python path accordingly ?
from libanaf.cli import app  # noqa: E402

LIBANAF_APP_HOME = Path(__file__).parent.parent.resolve().absolute()
sys.path.append(str(LIBANAF_APP_HOME / "libanaf"))
os.environ["LIBANAF_APP_HOME"] = str(LIBANAF_APP_HOME)
os.chdir(LIBANAF_APP_HOME)

os.environ["LIBANAF_CONFIG_FILE"] = str(LIBANAF_APP_HOME / "conf/config.toml")
os.environ["LIBANAF_LOGGING_CONFIG_FILE"] = str(LIBANAF_APP_HOME / "conf/logging_py.json")
os.environ["LIBANAF_SECRETS_PATH"] = str(LIBANAF_APP_HOME / "secrets")  # for storing secrets

if __name__ == "__main__":
    app()
