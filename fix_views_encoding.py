"""
Fix views.py encoding corruption by truncating and re-appending clean function
"""

# Read first 1221 lines of views.py (clean part)
with open('shop/views.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Keep only first 1221 lines
clean_lines = lines[:1221]

# Fix line 1221 if it has the malformed return statement
if clean_lines and 'return date_stats' in clean_lines[-1]:
    clean_lines[-1] = clean_lines[-1].replace('return date_stats" " "', 'return date_stats')

# Read clean function from delivery_view_temp.py
with open('delivery_view_temp.py', 'r', encoding='utf-8') as f:
    clean_function = f.read()

# Write back to views.py with UTF-8 encoding
with open('shop/views.py', 'w', encoding='utf-8') as f:
    f.writelines(clean_lines)
    f.write('\n\n')
    f.write(clean_function)

print("✅ Fixed views.py encoding corruption")
print(f"   - Kept first 1221 clean lines")
print(f"   - Removed corrupted UTF-16 section")
print(f"   - Appended clean delivery_report() function")
