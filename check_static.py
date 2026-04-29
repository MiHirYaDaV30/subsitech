import os
import re

TEMPLATES_DIR = 'templates'
STATIC_DIR = 'static'

actual_templates = set(os.listdir(TEMPLATES_DIR))
broken_static = []

for template in actual_templates:
    if not template.endswith('.html'):
        continue
    filepath = os.path.join(TEMPLATES_DIR, template)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for href="../static/..."
    hrefs = re.findall(r'href="\.\./static/([^"]+)"', content)
    for href in hrefs:
        static_path = os.path.join(STATIC_DIR, href.replace('/', os.sep))
        if not os.path.exists(static_path):
            broken_static.append((template, f"../static/{href}"))
            
    # Check for src="../static/..."
    srcs = re.findall(r'src="\.\./static/([^"]+)"', content)
    for src in srcs:
        static_path = os.path.join(STATIC_DIR, src.replace('/', os.sep))
        if not os.path.exists(static_path):
            broken_static.append((template, f"../static/{src}"))

print("Broken Static Links:")
for b in broken_static:
    print(f"{b[0]}: {b[1]}")

print("\nAll static checks completed.")
