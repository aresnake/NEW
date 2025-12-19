"""Check addon.py syntax around line 2115"""
with open(r'D:\EPHAESTUS\addon.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Lines 2100-2125:")
for i in range(2099, 2125):
    if i < len(lines):
        print(f"{i+1}: {lines[i].rstrip()}")
