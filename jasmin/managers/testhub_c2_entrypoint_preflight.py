"""Validate the C2 authority before the Docker entrypoint starts interceptord."""

import sys

from jasmin.bin.jasmind import JasminDaemon, Options


def main(argv=None):
    try:
        options = Options()
        options.parseOptions(sys.argv[1:] if argv is None else argv)
        JasminDaemon(options).configureTestHubC2()
    except Exception:
        # A failed factory may carry vault or DSN details: log no exception text.
        print('C2 entrypoint preflight failed', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
