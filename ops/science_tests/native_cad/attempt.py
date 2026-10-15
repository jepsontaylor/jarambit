"""Write one fresh native-CAD attempt directory.

Usage:
    python -m ops.science_tests.native_cad.attempt ATTEMPT_DIR

The directory receives receipt.json and NATIVE_CAD_VALIDATION.md.
The historical receipt is not modified. No network fetch is performed.
A candidate FAIL is still a completed diagnostic: the process exits 0
when the strict files were written, and nonzero when they were not.
"""

import sys
from pathlib import Path

from ops.science_tests.native_cad.evaluate import write_attempt


def main(argv):
    if len(argv) != 2:
        print(
            "usage: python -m ops.science_tests.native_cad.attempt ATTEMPT_DIR",
            file=sys.stderr,
        )
        return 2
    attempt_dir = Path(argv[1])
    write_attempt(attempt_dir, argv=list(argv))
    print(attempt_dir / "receipt.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
