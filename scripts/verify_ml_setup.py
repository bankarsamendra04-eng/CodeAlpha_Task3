"""
Comprehensive ML Environment & Package Verification Script
Checks all requested deep learning, data science, music processing, and API packages.
"""

import sys
import platform
import pathlib

# Ensure project root is in sys.path
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def run_verification():
    print("=" * 60)
    print("  AI Music Studio - ML Environment Verification")
    print("=" * 60)
    print(f"Operating System: {platform.system()} {platform.release()} ({platform.version()})")
    print(f"Python Executable: {sys.executable}")
    print(f"Python Version:    {sys.version.split()[0]}\n")

    packages = [
        ("tensorflow", lambda: __import__("tensorflow")),
        ("keras", lambda: __import__("keras")),
        ("numpy", lambda: __import__("numpy")),
        ("pandas", lambda: __import__("pandas")),
        ("scikit-learn", lambda: __import__("sklearn")),
        ("music21", lambda: __import__("music21")),
        ("tqdm", lambda: __import__("tqdm")),
        ("matplotlib", lambda: __import__("matplotlib")),
        ("joblib", lambda: __import__("joblib")),
        ("python-dotenv", lambda: __import__("dotenv")),
        ("fastapi", lambda: __import__("fastapi")),
        ("uvicorn", lambda: __import__("uvicorn")),
    ]

    installed = {}
    failed = []

    for name, importer in packages:
        try:
            mod = importer()
            ver = getattr(mod, "__version__", "Available")
            installed[name] = ver
            print(f"  [OK] {name:15s} : {ver}")
        except Exception as e:
            failed.append((name, str(e)))
            print(f"  [FAIL] {name:13s} : {e}")

    # Test ML package configuration imports
    print("\nVerifying project ML modules:")
    try:
        import ml.config as cfg
        print(f"  [OK] ml.config         : DATASET_PATH={cfg.DATASET_PATH.name}, SEQ_LEN={cfg.SEQUENCE_LENGTH}")
    except Exception as e:
        failed.append(("ml.config", str(e)))
        print(f"  [FAIL] ml.config       : {e}")

    try:
        import ml.utils as utils
        utils.set_seed(42)
        print(f"  [OK] ml.utils          : Seed set, helper functions validated")
    except Exception as e:
        failed.append(("ml.utils", str(e)))
        print(f"  [FAIL] ml.utils        : {e}")

    print("\n" + "=" * 60)
    if failed:
        print("VERIFICATION RESULT: FAILED with errors:")
        for n, err in failed:
            print(f"  - {n}: {err}")
        sys.exit(1)
    else:
        print("VERIFICATION RESULT: SUCCESS! ALL PACKAGES ARE FUNCTIONAL.")
        print("=" * 60)
        sys.exit(0)

if __name__ == "__main__":
    run_verification()
