"""Fix delivery report permission - force line replacement"""

# Read file lines
with open('shop/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")
print(f"Line 1255 (idx 1254): {repr(lines[1254])}")
print(f"Line 1256 (idx 1255): {repr(lines[1255])}")

# Check if it's the right location
if "Employee" in lines[1254] and "pass" in lines[1255]:
    print("\n✓ Found correct location")
    # Replace line 1255 (comment)
    lines[1254] = "        # Employee бүртгэлгүй бол UserProfile-с distributor_id-г шалгах\n"
    # Replace line 1256 (pass) and insert new try-except block
    lines[1255] = "        try:\n"
    lines.insert(1256, "            profile = request.user.profile\n")
    lines.insert(1257, "            user_distributor_id = profile.distributor_id\n")
    lines.insert(1258, "        except:\n")
    lines.insert(1259, "            pass\n")
    
    # Write back
    with open('shop/views.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("✓ Successfully updated views.py")
    print("\nChanged:")
    print("  Old: pass")
    print("  New: try-except block for UserProfile.distributor_id")
else:
    print("\n✗ Lines don't match expected pattern")
    print(f"Line 1255 contains 'Employee': {'Employee' in lines[1254]}")
    print(f"Line 1256 contains 'pass': {'pass' in lines[1255]}")
