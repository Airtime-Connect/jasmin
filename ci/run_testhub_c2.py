"""Run the protected C2 contract suite without accepting empty or skipped work."""

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


TEST_MODULES = (
    'tests.managers.test_testhub_c2_sovereign',
    'tests.managers.test_testhub_c2_pg',
    'tests.managers.test_testhub_c2_bootstrap',
    'tests.managers.test_testhub_c2',
    'tests.managers.test_testhub_c2_hooks',
    'tests.managers.test_testhub_c2_pre_deserialize',
)
MINIMUM_TESTS = 63


def main():
    suite = unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)
    discovered = suite.countTestCases()
    print(f'C2 discovered={discovered}; required>={MINIMUM_TESTS}', flush=True)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(f'C2 ran={result.testsRun}; skipped={len(result.skipped)}; '
          f'failures={len(result.failures)}; errors={len(result.errors)}', flush=True)
    return 0 if (discovered >= MINIMUM_TESTS and result.wasSuccessful()
                 and not result.skipped
                 and result.testsRun == discovered) else 1


if __name__ == '__main__':
    sys.exit(main())
