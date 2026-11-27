"""Tests that fail on purpose because of a known bug in the app, and who fixes each one.

conftest.py marks every test listed here as a strict xfail, so the suite stays
green and any other failure stands out. When the owner's fix lands, the test
passes, pytest reports XPASS and the run fails: delete the line then.
Keys are pytest node ids, as `pytest -q` prints them after FAILED.
"""


KNOWN_BUGS: dict[str, tuple[str, str]] = {}
