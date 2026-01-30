
import logging
from src.optimize.results import run
from src.common.io import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    print("Running optimization result generation directly...")
    try:
        run()
        print("Run complete.")
    except Exception as e:
        print(f"Run failed: {e}")
        import traceback
        traceback.print_exc()
