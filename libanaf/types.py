from enum import Enum


class Filter(str, Enum):
    E = "E"
    T = "T"
    P = "P"
    R = "R"


# Canonical location is libanaf.ubl.units; re-exported here for backward compatibility.
from libanaf.ubl.units import UNIT_CODES as UNIT_CODES  # noqa: E402, F401
