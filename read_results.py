
import json
import os

target_file = "results.json"
found_path = None

print(f"Searching for {target_file} from CWD: {os.getcwd()}")

for root, dirs, files in os.walk("."):
    if target_file in files:
        if "optimization_results" in root:
             found_path = os.path.join(root, target_file)
             print(f"Found: {found_path}")
             break

if not found_path:
    # Try the specific path seen in logs
    potential = r"c:\Users\Ben\OneDrive\Desktop\SIGWork\portfolio-optimizer\lake\lake\gold\optimization_results\dt=2026-01-02\results.json"
    if os.path.exists(potential):
        found_path = potential
        print(f"Found via hardcode: {found_path}")

if not found_path:
    print("Could not find results.json")
    # debug print dirs in lake
    if os.path.exists("lake"):
        print("Contents of lake/:", os.listdir("lake"))
        if os.path.exists("lake/lake"):
            print("Contents of lake/lake/:", os.listdir("lake/lake"))
    exit(1)

print(f"Reading {found_path}...")
try:
    if os.path.isdir(found_path):
        print(f"Path is a DIRECTORY (MinIO object storage).")
        children = os.listdir(found_path)
        print(f"Contents: {children}")
        
        # internal file is likely the one that isn't xl.meta
        data_file = None
        for c in children:
            if c != "xl.meta":
                data_file = os.path.join(found_path, c)
                break
        
        if data_file:
            print(f"Reading internal data file: {data_file}")
            with open(data_file, "r") as f:
                data = json.load(f)
            
            # Print logic (reused)
            print("KEYS:", data.keys())
            metrics = data.get("metrics", {})
            print("\nMETRICS:", metrics)
            print(f"Volatility > 0? {metrics.get('volatility', 0) > 0}") # Check Volatility
            
            sharpe = data.get("sharpe")
            print(f"\nPORTFOLIO SHARPE: {sharpe}")
            print(f"Sharpe Finite? {sharpe != float('inf')}") # Check Sharpe
            
            frontier = data.get("frontier", [])
            print(f"\nFRONTIER LEN: {len(frontier)}") # Check Frontier
            if frontier:
                print("FRONTIER POINT 0:", frontier[0])
            
            holdings = data.get("holdings", [])
            print(f"\nHOLDINGS LEN: {len(holdings)}")
            if holdings:
                h0 = holdings[0]
                print("HOLDING 0 SAMPLE:", h0)
                print(f"Holding Sharpe Finite? {h0.get('sharpe') != float('inf')}") # Check Holding Sharpe
        else:
            print("No data file found inside object directory.")

    elif os.path.isfile(found_path):
        print(f"Path is a file. Size: {os.path.getsize(found_path)} bytes")
        with open(found_path, "r") as f:
            data = json.load(f)
        
        print("KEYS:", data.keys())
        # Metrics
        metrics = data.get("metrics", {})
        print("\nMETRICS:", metrics)
        print(f"Volatility > 0? {metrics.get('volatility', 0) > 0}")
        
        # Sharpe
        sharpe = data.get("sharpe")
        print(f"\nPORTFOLIO SHARPE: {sharpe}")
        
        # Frontier
        frontier = data.get("frontier", [])
        print(f"\nFRONTIER LEN: {len(frontier)}")
        if frontier:
            print("FRONTIER POINT 0:", frontier[0])
        
        # Holdings
        holdings = data.get("holdings", [])
        print(f"\nHOLDINGS LEN: {len(holdings)}")
        if holdings:
            h0 = holdings[0]
            print("HOLDING 0 SAMPLE:", h0)
            print(f"Holding Sharpe Finite? {h0.get('sharpe') != float('inf')}")
    else:
        print("Path exists but is not file or dir??")

except Exception as e:
    print(f"FULL ERROR reading path: {e}")
    import traceback
    traceback.print_exc()
