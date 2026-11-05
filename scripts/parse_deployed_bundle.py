import re
import os

with open("deployed_bundle.js", "r", encoding="utf-8") as f:
    c = f.read()

ls_keys = re.findall(r'localStorage\.(?:getItem|setItem|removeItem)\(["\']([^"\']+)["\']', c)
print("=== LOCALSTORAGE KEYS IN DEPLOYED BUNDLE ===")
for k in sorted(set(ls_keys)):
    print(f"  - {k}")

apis = re.findall(r'/api/v1/[a-zA-Z0-9_\-/]+', c)
print("\n=== API ENDPOINTS IN DEPLOYED BUNDLE ===")
for a in sorted(set(apis)):
    print(f"  - {a}")

ws = re.findall(r'wss?://[^\s"\'`]+|/ws[a-zA-Z0-9_\-/]*', c)
print("\n=== WEBSOCKET REFERENCES IN DEPLOYED BUNDLE ===")
for w in sorted(set(ws)):
    print(f"  - {w}")

# Check current_password presence (Fix 1)
print("\n=== FIX 1 CHECK (current_password in bundle) ===")
print("current_password found:", "current_password" in c)

# Check Access Denied presence (Fix 2)
print("\n=== FIX 2 CHECK (Access Denied in bundle) ===")
print("Access Denied found:", "Access Denied" in c)

# Check Manager technician only restrictions (Fix 3)
print("\n=== FIX 3 CHECK (Plant Personnel Directory / Target role check) ===")
print("Plant Personnel Directory found:", "Plant Personnel Directory" in c)

os.remove("deployed_bundle.js")
