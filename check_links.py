import os
import re

TEMPLATES_DIR = 'templates'
APP_FILE = 'app.py'

# 1. Gather all actual templates
actual_templates = set(os.listdir(TEMPLATES_DIR))

# 2. Extract routes from app.py
with open(APP_FILE, 'r') as f:
    app_content = f.read()

# Routes are defined as @app.route("/path")
routes = set(re.findall(r'@app\.route\("([^"]+)"\)', app_content))
# Also endpoints (functions)
endpoints = set(re.findall(r'def (\w+)\(', app_content))

broken_links = []
missing_templates = []

for template in actual_templates:
    if not template.endswith('.html'):
        continue
    filepath = os.path.join(TEMPLATES_DIR, template)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for href="..."
    hrefs = re.findall(r'href="([^"]+)"', content)
    for href in hrefs:
        if href.startswith('http') or href.startswith('#') or href.startswith('mailto:') or href.startswith('../static/'):
            continue
        # If it's a template link, strip query params and check if it exists in templates
        base_href = href.split('?')[0].split('#')[0]
        if base_href.endswith('.html') and base_href not in actual_templates:
            broken_links.append((template, href, 'Template not found'))
            
    # Check for url_for('...')
    url_fors = re.findall(r"url_for\(['\"]([^'\"]+)['\"]", content)
    for endpoint in url_fors:
        if endpoint not in endpoints and endpoint != 'static':
            broken_links.append((template, endpoint, 'Endpoint not found'))

print("Broken Links/Endpoints:")
for b in broken_links:
    print(f"{b[0]}: {b[1]} - {b[2]}")

print("\nAll checks completed.")
