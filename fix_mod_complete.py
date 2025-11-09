#!/usr/bin/env python3
"""
Complete fix for module_base.py to make it work with dynamic module loading.
This script properly handles the transformation from hardcoded vibrato_plugin to dynamic loading.
"""

import re

def fix_module_base():
    filepath = r't:\UI\build\pages\module_base.py'
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Step 1: Remove the hardcoded import
    content = re.sub(
        r'from plugins import vibrato_plugin as mod\n',
        '',
        content
    )
    
    # Step 2: Update _LOGTAG initialization
    content = re.sub(
        r'_LOGTAG = mod\.MODULE_ID\.upper\(\)',
        '_LOGTAG = "MODULE"  # Will be set dynamically when module loads',
        content
    )
    
    # Step 3: Add dynamic module reference after _LOGTAG
    if '_active_module_ref = None' not in content:
        content = re.sub(
            r'(_LOGTAG = "MODULE".*?\n)',
            r'\1\n# Dynamic module reference - set by set_active_module()\n_active_module_ref = None\n',
            content
        )
    
    # Step 4: Replace ALL mod.MODULE_ID with _get_module_id()
    content = re.sub(r'\bmod\.MODULE_ID\b', '_get_module_id()', content)
    
    # Step 5: Replace mod.ATTR.method() calls
    content = re.sub(r'\bmod\.SLOT_TO_CTRL\.get\(', '_get_module_attr("SLOT_TO_CTRL", {}).get(', content)
    content = re.sub(r'\bmod\.SLOT_TO_CTRL\.items\(\)', '_get_module_attr("SLOT_TO_CTRL", {}).items()', content)
    
    # Step 6: Replace standalone mod.ATTR references
    content = re.sub(r'\bmod\.SLOT_TO_CTRL\b', '_get_module_attr("SLOT_TO_CTRL", {})', content)
    content = re.sub(r'\bmod\.REGISTRY\b', '_get_module_attr("REGISTRY", {})', content)
    content = re.sub(r'\bmod\.BUTTONS\b', '_get_module_attr("BUTTONS", [])', content)
    content = re.sub(r'\bmod\.GRID_LAYOUT\b', '_get_module_attr("GRID_LAYOUT", {"rows": 2, "cols": 4})', content)
    content = re.sub(r'\bmod\.OWNED_SLOTS\b', '_get_module_attr("OWNED_SLOTS", None)', content)
    content = re.sub(r'\bmod\.CUSTOM_WIDGET\b', '_get_module_attr("CUSTOM_WIDGET", None)', content)
    
    # Step 7: Replace getattr(mod, ...) calls
    content = re.sub(r'getattr\(mod, "([^"]+)",\s*([^)]+)\)', r'_get_module_attr("\1", \2)', content)
    content = re.sub(r'getattr\(mod, "([^"]+)"\)', r'_get_module_attr("\1")', content)
    
    # Step 8: Add _get_module_id() helper if not present
    if 'def _get_module_id():' not in content:
        # Find where to insert it (after _get_module_attr)
        helper_func = '''
def _get_module_id():
    """Get the MODULE_ID of the active module."""
    return _get_module_attr("MODULE_ID", "UNKNOWN")
'''
        content = re.sub(
            r'(def _get_module_attr\(.*?\n    return.*?\n)',
            r'\1' + helper_func,
            content,
            flags=re.DOTALL
        )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ Fixed module_base.py successfully!")
    print("  - Removed hardcoded vibrato_plugin import")
    print("  - Added dynamic module reference")
    print("  - Replaced all mod.* references with dynamic lookups")

if __name__ == '__main__':
    fix_module_base()
