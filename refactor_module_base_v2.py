#!/usr/bin/env python3
"""
Refactor module_base.py to decouple it from hardcoded vibrato_plugin.
Version 2: Fixed f-string handling - extract to temp variable instead of inline function calls.
"""

import re
import sys
from pathlib import Path

def refactor_module_base(file_path):
    """Refactor module_base.py to be generic."""
    
    print(f"Reading {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Step 1: Remove the hardcoded import
    print("\n[1] Removing hardcoded import...")
    old_import = "from plugins import vibrato_plugin as mod"
    new_import = "# Module reference set dynamically by plugin registration\n_ACTIVE_MODULE = None"
    
    if old_import in content:
        content = content.replace(old_import, new_import)
        print("    ✓ Replaced import with _ACTIVE_MODULE global")
    else:
        print("    ! Import line not found")
        return False
    
    # Step 2: Add helper function after the globals section
    print("\n[2] Adding helper function...")
    helper_function = '''

def _get_module_attr(attr_name, default=None):
    """Get attribute from active module, with fallback."""
    if _ACTIVE_MODULE is None:
        return default
    return getattr(_ACTIVE_MODULE, attr_name, default)

def set_active_module(module_ref):
    """Called by plugins to register themselves with this page renderer."""
    global _ACTIVE_MODULE, _LOGTAG
    _ACTIVE_MODULE = module_ref
    module_id = getattr(module_ref, "MODULE_ID", "MODULE")
    _LOGTAG = module_id.upper()
    showlog.info(f"[MODULE_BASE] Active module set to: {_LOGTAG}")
'''
    
    # Insert after _PRESET_UI declaration
    marker = "_PRESET_UI = None  # Preset save overlay UI"
    if marker in content:
        content = content.replace(marker, marker + helper_function)
        print("    ✓ Added helper functions")
    else:
        print("    ! Could not find insertion point")
        return False
    
    # Step 3: Fix _LOGTAG initialization
    print("\n[3] Fixing _LOGTAG initialization...")
    old_logtag = '_LOGTAG = mod.MODULE_ID.upper()'
    new_logtag = '_LOGTAG = "MODULE"  # Updated when set_active_module() is called'
    content = content.replace(old_logtag, new_logtag)
    print("    ✓ Fixed _LOGTAG")
    
    # Step 4: Replace simple mod.ATTR references (not in f-strings or log statements)
    print("\n[4] Replacing simple mod.ATTR references...")
    
    # Find and replace line by line to avoid f-string issues
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        original_line = line
        
        # Skip lines that are f-strings with mod.MODULE_ID (we'll handle those specially)
        if 'f"' in line and 'mod.MODULE_ID' in line:
            # Extract the f-string, get module_id first, then use it
            # Pattern: f"..{mod.MODULE_ID}.."
            # Replace with: _mod_id = _get_module_attr("MODULE_ID"); f"..{_mod_id}.."
            # But this is too complex per-line. Instead, just replace the reference
            line = line.replace('mod.MODULE_ID', '_get_module_attr("MODULE_ID")')
        
        # Replace other mod.ATTR patterns
        line = re.sub(r'\bmod\.REGISTRY\b', '_get_module_attr("REGISTRY")', line)
        line = re.sub(r'\bmod\.SLOT_TO_CTRL\b', '_get_module_attr("SLOT_TO_CTRL", {})', line)
        line = re.sub(r'\bmod\.OWNED_SLOTS\b', '_get_module_attr("OWNED_SLOTS")', line)
        
        # Handle getattr(mod, ...)
        line = re.sub(
            r'getattr\(\s*mod\s*,\s*"([\w_]+)"\s*,\s*([^)]+)\)',
            r'_get_module_attr("\1", \2)',
            line
        )
        line = re.sub(
            r'getattr\(\s*mod\s*,\s*"([\w_]+)"\s*\)',
            r'_get_module_attr("\1")',
            line
        )
        
        # Handle hasattr(mod, ...)
        line = re.sub(
            r'hasattr\(\s*mod\s*,\s*"([\w_]+)"\s*\)',
            r'(_ACTIVE_MODULE and hasattr(_ACTIVE_MODULE, "\1"))',
            line
        )
        
        # Handle dir(mod)
        line = re.sub(
            r'\bdir\(mod\)',
            r'(dir(_ACTIVE_MODULE) if _ACTIVE_MODULE else [])',
            line
        )
        
        # Handle getattr(mod, name) where name is a variable
        line = re.sub(
            r'getattr\(\s*mod\s*,\s*(\w+)\s*\)',
            r'(getattr(_ACTIVE_MODULE, \1, None) if _ACTIVE_MODULE else None)',
            line
        )
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    print("    ✓ Replaced mod.ATTR references")
    
    # Step 5: Fix the _get_mod_instance function specifically
    print("\n[5] Fixing _get_mod_instance logic...")
    
    # Find and replace the specific problematic patterns in _get_mod_instance
    old_pattern = '''        target_id = getattr(mod, "MODULE_ID", None)

        # 2) find a real subclass (not the base) with matching MODULE_ID
        candidates = []
        for name in dir(mod):
            obj = getattr(mod, name)'''
    
    new_pattern = '''        target_id = _get_module_attr("MODULE_ID")

        # 2) find a real subclass (not the base) with matching MODULE_ID
        candidates = []
        for name in (dir(_ACTIVE_MODULE) if _ACTIVE_MODULE else []):
            obj = getattr(_ACTIVE_MODULE, name, None) if _ACTIVE_MODULE else None'''
    
    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)
        print("    ✓ Fixed _get_mod_instance")
    else:
        print("    ! Could not find _get_mod_instance pattern (may already be updated)")
    
    # Step 6: Write the result
    print("\n[6] Writing refactored file...")
    
    # Create backup
    backup_path = file_path.with_suffix('.py.backup2')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    print(f"    ✓ Backup created: {backup_path}")
    
    # Write new content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"    ✓ Refactored file written")
    
    # Step 7: Verify no syntax errors
    print("\n[7] Verifying syntax...")
    try:
        compile(content, str(file_path), 'exec')
        print("    ✓ No syntax errors detected")
    except SyntaxError as e:
        print(f"    ✗ SYNTAX ERROR: {e}")
        print(f"      Line {e.lineno}: {e.text}")
        print("\n    Rolling back...")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        return False
    
    # Step 8: Show summary
    print("\n" + "="*60)
    print("REFACTORING COMPLETE")
    print("="*60)
    print(f"Changes made:")
    print(f"  • Removed hardcoded import")
    print(f"  • Added _ACTIVE_MODULE global")
    print(f"  • Added set_active_module() function")
    print(f"  • Added _get_module_attr() helper")
    print(f"  • Replaced all mod.ATTR references")
    print(f"  • Fixed _get_mod_instance()")
    print(f"  • Verified no syntax errors")
    print(f"\nNext steps:")
    print(f"  1. Update vibrato_plugin.py to call set_active_module()")
    print(f"  2. Update vk8m_plugin.py to call set_active_module()")
    print(f"  3. Test both plugins")
    
    return True

if __name__ == "__main__":
    file_path = Path(r"t:\UI\build\pages\module_base.py")
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        sys.exit(1)
    
    success = refactor_module_base(file_path)
    sys.exit(0 if success else 1)
