"""Fix delivery report permission - direct line edit"""

# Read file lines
with open('shop/views.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with the comment
target_found = False
for i, line in enumerate(lines):
    if i == 1254:  # Line 1255 (0-indexed as 1254)
        print(f"Line {i+1}: {repr(line)}")
        if "хоосон өгөгдөл" in line:
            print("Found target line!")
            # Replace lines 1255-1256 with new code
            lines[1254] = "        # Employee бүртгэлгүй бол UserProfile-с distributor_id-г шалгах\n"
            lines[1255] = "        try:\n"
            # Insert new lines
            lines.insert(1256, "            profile = request.user.profile\n")
            lines.insert(1257, "            user_distributor_id = profile.distributor_id\n")
            lines.insert(1258, "        except:\n")
            lines.insert(1259, "            pass\n")
            target_found = True
            break

if target_found:
    # Write back
    with open('shop/views.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print("✓ Successfully updated delivery_report permission check")
else:
    print("✗ Target line not found at expected position")
