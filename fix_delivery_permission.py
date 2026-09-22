"""Fix delivery report permission check for non-Employee users"""
import sys

# Read the file
with open('shop/views.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the specific section  
old_text = """# Employee бүртгэлгүй бол хоосон өгөгдөл
        pass"""

new_text = """# Employee бүртгэлгүй бол UserProfile-с distributor_id-г шалгах
        try:
            profile = request.user.profile
            user_distributor_id = profile.distributor_id
        except:
            pass"""

if old_text in content:
    content = content.replace(old_text, new_text)
    with open('shop/views.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ Fixed delivery_report permission check")
    print("  Added UserProfile distributor_id lookup for non-Employee users")
else:
    print("✗ Could not find the target text")
    print("\nSearching for similar patterns...")
    # Try to find the location
    if "except OpenDataEmployee.DoesNotExist:" in content:
        print("Found 'except OpenDataEmployee.DoesNotExist:'")
        idx = content.find("except OpenDataEmployee.DoesNotExist:")
        print(f"Context around line:\n{content[idx:idx+200]}")
    sys.exit(1)
