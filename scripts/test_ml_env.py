"""
ML Environment Verification Script
Verifies that all core ML and audio packages import properly and report their versions.
"""

import sys

def verify_environment():
    results = {}
    errors = []

    print("Verifying Python Machine-Learning Environment...")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version.split()[0]}\n")

    # 1. TensorFlow
    try:
        import tensorflow as tf
        results["tensorflow"] = tf.__version__
        print(f"  [OK] tensorflow: {tf.__version__}")
    except Exception as e:
        errors.append(f"tensorflow import failed: {e}")
        print(f"  [FAIL] tensorflow: {e}")

    # 2. music21
    try:
        import music21
        results["music21"] = music21.__version__
        print(f"  [OK] music21: {music21.__version__}")
    except Exception as e:
        errors.append(f"music21 import failed: {e}")
        print(f"  [FAIL] music21: {e}")

    # 3. NumPy
    try:
        import numpy as np
        results["numpy"] = np.__version__
        print(f"  [OK] numpy: {np.__version__}")
    except Exception as e:
        errors.append(f"numpy import failed: {e}")
        print(f"  [FAIL] numpy: {e}")

    # 4. Pandas
    try:
        import pandas as pd
        results["pandas"] = pd.__version__
        print(f"  [OK] pandas: {pd.__version__}")
    except Exception as e:
        errors.append(f"pandas import failed: {e}")
        print(f"  [FAIL] pandas: {e}")

    # 5. scikit-learn
    try:
        import sklearn
        results["scikit-learn"] = sklearn.__version__
        print(f"  [OK] scikit-learn: {sklearn.__version__}")
    except Exception as e:
        errors.append(f"scikit-learn import failed: {e}")
        print(f"  [FAIL] scikit-learn: {e}")

    # 6. Matplotlib
    try:
        import matplotlib
        results["matplotlib"] = matplotlib.__version__
        print(f"  [OK] matplotlib: {matplotlib.__version__}")
    except Exception as e:
        errors.append(f"matplotlib import failed: {e}")
        print(f"  [FAIL] matplotlib: {e}")

    print("\n--------------------------------------------------")
    if errors:
        print("ML Environment Verification FAILED with errors:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)
    else:
        print("ALL REQUIRED ML & AUDIO PACKAGES IMPORTED SUCCESSFULLY!")
        print("The ML environment is ready.")
        sys.exit(0)

if __name__ == "__main__":
    verify_environment()
