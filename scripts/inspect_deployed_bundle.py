import urllib.request
import re

url = "https://motor-guard-sandy.vercel.app/assets/index-CF8-3jUI.js"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=15) as res:
    content = res.read().decode("utf-8")

print(f"Downloaded bundle: {len(content)} characters")

# Find localStorage keys
matches = re.findall(r'localStorage\.(?:getItem|setItem|removeItem)\(["\']([^"\']+)["\']', content)
print("localStorage keys in deployed bundle:", set(matches))

# Find git commit or version strings
commit_matches = re.findall(r'[0-9a-f]{7,40}', content)
# Look for api endpoints
api_matches = re.findall(r'/api/v1/[a-zA-Z0-9_\-/]+', content)
print("\nAPI routes found in deployed bundle:", sorted(set(api_matches)))

# Look for RBAC or role definitions
role_matches = re.findall(r'(?:Admin|Manager|Technician)', content)
print("Role occurrences:", len(role_matches))
