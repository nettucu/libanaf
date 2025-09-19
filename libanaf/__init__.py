import logging

"""
Disable logging for the library by default
Users of the library can configure logging as needed
For example, in their application code, they can do:
"""

log = logging.getLogger(__name__)

log.addHandler(logging.NullHandler())
