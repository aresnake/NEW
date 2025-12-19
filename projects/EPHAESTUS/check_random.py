"""Check randomize_transform code"""
content = open(r'D:\EPHAESTUS\addon.py', 'r', encoding='utf-8').read()
idx = content.find('elif command_type == "randomize_transform"')
if idx > 0:
    section = content[idx:idx+2500]
    print(section)
else:
    print("Not found")
