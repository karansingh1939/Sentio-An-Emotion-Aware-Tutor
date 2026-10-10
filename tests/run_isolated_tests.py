import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
test_files = [str(path.relative_to(ROOT)) for path in sorted((ROOT / "tests").glob("test_*.py"))]


passed = []
failed = []

print("=== STARTING ISOLATED AUTOMATED REGRESSION SUITE ===")
for test_file in test_files:
    print(f"\nRunning {test_file}...")
    start_time = time.time()
    try:
        # Run pytest in a separate subprocess with a 90 second timeout
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", test_file],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = time.time() - start_time
        print(f"Finished in {elapsed:.2f} seconds.")
        if res.returncode == 0:
            print(f"[PASS] {test_file}")
            passed.append(test_file)
        else:
            print(f"[FAIL] {test_file} (exit code: {res.returncode})")
            print("--- STDOUT ---")
            print(res.stdout)
            print("--- STDERR ---")
            print(res.stderr)
            failed.append(test_file)
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {test_file} hung and was terminated after 120 seconds.")
        failed.append(test_file)
    except Exception as e:
        print(f"[ERROR] Failed to execute {test_file}: {e}")
        failed.append(test_file)

print("\n=== REGRESSION SUITE SUMMARY ===")
print(f"Total passed: {len(passed)}")
print(f"Total failed: {len(failed)}")
if failed:
    print("\nFailed suites:")
    for f in failed:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("\nAll automated suites passed successfully!")
    sys.exit(0)
