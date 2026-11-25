"""Tests that fail on purpose because of a known bug in the app, and who fixes each one.

conftest.py marks every test listed here as a strict xfail, so the suite stays
green and any other failure stands out. When the owner's fix lands, the test
passes, pytest reports XPASS and the run fails: delete the line then.
Keys are pytest node ids, as `pytest -q` prints them after FAILED.
"""

_SETTINGS = "tests/test_input_validation.py::test_settings_refuse_what_registration_refuses"
_PROFILE = "tests/test_input_validation.py::test_a_bad_profile_update_is_refused_without_a_server_error"
_COMMENT = "tests/test_input_validation.py::test_a_bad_comment_is_refused_without_a_server_error"
_PATH_ID = "tests/test_input_validation.py::test_a_bad_id_in_the_path_is_refused_without_a_server_error"

KNOWN_BUGS = {
    "tests/test_backend.py::test_backend_authorized[req19-exp19]":
        ("Victor", "update_profile reorders the Top 10 into a UniqueViolation on top10_entries (user_id, rank)"),
    f"{_SETTINGS}[0]": ("Victor", "POST /settings accepts an invalid email"),
    f"{_SETTINGS}[1]": ("Victor", "POST /settings accepts an empty email"),
    f"{_SETTINGS}[2]": ("Victor", "POST /settings with another user's email gives 500, not 409"),
    f"{_SETTINGS}[3]": ("Victor", "POST /settings accepts a password shorter than registration allows"),
    f"{_SETTINGS}[4]": ("Victor", "POST /settings accepts a password longer than registration allows"),
    f"{_SETTINGS}[5]": ("Victor", "POST /settings with a NUL byte in the email gives 500"),
    f"{_PROFILE}[0]": ("Victor", "POST /profiles/me accepts an empty display_name"),
    f"{_PROFILE}[1]": ("Victor", "POST /profiles/me accepts a blank display_name"),
    f"{_PROFILE}[2]": ("Victor", "POST /profiles/me with a NUL byte in display_name gives 500"),
    f"{_PROFILE}[3]": ("Victor", "POST /profiles/me with a NUL byte in bio gives 500"),
    f"{_COMMENT}[1]": ("Victor", "an empty comment body gives 500"),
    f"{_COMMENT}[2]": ("Victor", "a blank comment body gives 500"),
    f"{_COMMENT}[4]": ("Victor", "a NUL byte in a comment body gives 500"),
    f"{_PATH_ID}[GET /songs/{{id}}--1]": ("Victor", "GET /songs/-1 answers 200, not 4xx"),
    f"{_PATH_ID}[GET /songs/{{id}}-9223372036854775808]": ("Victor", "GET /songs/ with an id past BIGINT answers 200, not 4xx"),
}
