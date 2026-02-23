#!/usr/bin/env python
"""Deprecated.

Tests for services live in the Django test suite under
`Research_AI_Assistant/tests.py`.

This file was previously a standalone script and duplicated test coverage,
which can cause maintenance issues over time.
"""


def main() -> None:
    raise SystemExit(
        "This script is deprecated. Run Django tests instead (manage.py test)."
    )


if __name__ == "__main__":
    main()
