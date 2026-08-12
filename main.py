import marshal
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PYC = os.path.join(_HERE, "app.pyc")

with open(_PYC, "rb") as f:
    f.read(16)  # bo qua pyc header (PEP 552, Python 3.7+)
    _code = marshal.load(f)

exec(_code, {"__name__": "__main__", "__file__": _PYC})
