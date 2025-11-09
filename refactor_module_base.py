#!/usr/bin/env python3
"""
Refactor module_base.py to decouple it from hardcoded vibrato_plugin.

Strategy:
1. Remove: from plugins import vibrato_plugin as mod
2. Add: _ACTIVE_MODULE global that gets set by plugins when they register
3. Replace all mod.ATTR references with _get_module_attr("ATTR")
4. Replace all f"...{mod.ATTR}..." with f"...{_get_module_attr('ATTR')}..."
5. Handle _LOGTAG separately since it's initialized at module level
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
    _LOGTAG = _get_module_attr("MODULE_ID", "MODULE").upper()
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
    
    # Step 3: Fix _LOGTAG initialization (it's used before set_active_module is called)
    print("\n[3] Fixing _LOGTAG initialization...")
    old_logtag = '_LOGTAG = mod.MODULE_ID.upper()'
    new_logtag = '_LOGTAG = "MODULE"  # Updated when set_active_module() is called'
    content = content.replace(old_logtag, new_logtag)
    print("    ✓ Fixed _LOGTAG")
    
    # Step 4: Replace simple mod.ATTR references (not in f-strings)
    print("\n[4] Replacing simple mod.ATTR references...")
    
    # Patterns to replace with helper function
    simple_patterns = [
        (r'\bmod\.MODULE_ID\b', '_get_module_attr("MODULE_ID")'),
        (r'\bmod\.REGISTRY\b', '_get_module_attr("REGISTRY")'),
        (r'\bmod\.SLOT_TO_CTRL\b', '_get_module_attr("SLOT_TO_CTRL", {})'),
        (r'\bmod\.OWNED_SLOTS\b', '_get_module_attr("OWNED_SLOTS")'),
    ]
    
    for pattern, replacement in simple_patterns:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            content = re.sub(pattern, replacement, content)
            print(f"    ✓ Replaced {matches} occurrences of {pattern}")
    
    # Step 5: Handle mod references that are attribute access on the module itself
    # These need special handling - looking for getattr(mod, ...) patterns
    print("\n[5] Replacing getattr(mod, ...) patterns...")
    
    # Pattern: getattr(mod, "ATTR", default)
    def replace_getattr(match):
        attr_name = match.group(1)
        default = match.group(2) if match.group(2) else 'None'
        return f'_get_module_attr({attr_name}, {default})'
    
    # getattr(mod, "...", ...)
    pattern = r'getattr\(\s*mod\s*,\s*("[\w_]+")\s*,\s*([^)]+)\)'
    content = re.sub(pattern, replace_getattr, content)
    
    # getattr(mod, "...")
    pattern = r'getattr\(\s*mod\s*,\s*("[\w_]+")\s*\)'
    matches = len(re.findall(pattern, content))
    if matches > 0:
        content = re.sub(pattern, r'_get_module_attr(\1)', content)
        print(f"    ✓ Replaced {matches} getattr patterns")
    
    # Step 6: Handle references in f-strings - these are the tricky ones
    print("\n[6] Handling f-string references...")
    
    # We need to find f"...{mod.ATTR}..." and convert to f"...{_get_module_attr('ATTR')}..."
    # This is complex because f-strings can have nested braces
    
    # Simpler approach: Look for {mod.ATTR} patterns specifically
    fstring_patterns = [
        (r'\{mod\.MODULE_ID\}', r'{_get_module_attr("MODULE_ID")}'),
        (r'\{mod\.REGISTRY\}', r'{_get_module_attr("REGISTRY")}'),
        (r'\{mod\.SLOT_TO_CTRL\}', r'{_get_module_attr("SLOT_TO_CTRL")}'),
    ]
    
    for pattern, replacement in fstring_patterns:
        matches = len(re.findall(pattern, content))
        if matches > 0:
            content = re.sub(pattern, replacement, content)
            print(f"    ✓ Replaced {matches} f-string occurrences of {pattern}")
    
    # Step 7: Handle hasattr(mod, ...) and isinstance checks
    print("\n[7] Fixing hasattr and dir(mod) patterns...")
    
    # hasattr(mod, "...")
    content = re.sub(
        r'hasattr\(\s*mod\s*,\s*"([\w_]+)"\s*\)',
        r'hasattr(_ACTIVE_MODULE, "\1") if _ACTIVE_MODULE else False',
        content
    )
    
    # isinstance checks with mod
    content = re.sub(
        r'issubclass\(\s*obj\s*,\s*ModuleBase\s*\)',
        r'issubclass(obj, ModuleBase)',
        content
    )
    
    # dir(mod)
    content = re.sub(
        r'\bdir\(mod\)',
        r'dir(_ACTIVE_MODULE) if _ACTIVE_MODULE else []',
        content
    )
    
    # for name in dir(mod)
    content = re.sub(
        r'for\s+(\w+)\s+in\s+dir\(mod\)',
        r'for \1 in (dir(_ACTIVE_MODULE) if _ACTIVE_MODULE else [])',
        content
    )
    
    # getattr(mod, name)  <- variable name, not string
    content = re.sub(
        r'getattr\(\s*mod\s*,\s*(\w+)\s*\)',
        r'getattr(_ACTIVE_MODULE, \1, None) if _ACTIVE_MODULE else None',
        content
    )
    
    print("    ✓ Fixed hasattr/dir patterns")
    
    # Step 8: Check if obj is ModuleBase in _get_mod_instance
    print("\n[8] Fixing _get_mod_instance logic...")
    
    # The function tries to find ModuleBase subclass
    # Need to update it to work with _ACTIVE_MODULE
    old_get_instance = '''def _get_mod_instance():
    """Create/cache the active module instance (class discovered dynamically)."""
    global _MOD_INSTANCE
    if _MOD_INSTANCE is not None:
        return _MOD_INSTANCE
    try:
        # 1) explicit factory wins
        factory = getattr(_ACTIVE_MODULE, "get_instance", None) if _ACTIVE_MODULE else None
        if callable(factory):
            _MOD_INSTANCE = factory()
            return _MOD_INSTANCE

        target_id = _get_module_attr("MODULE_ID")

        # 2) find a real subclass (not the base) with matching MODULE_ID
        candidates = []
        for name in (dir(_ACTIVE_MODULE) if _ACTIVE_MODULE else []):
            obj = getattr(_ACTIVE_MODULE, name, None) if _ACTIVE_MODULE else None
            if not (isinstance(obj, type) and issubclass(obj, ModuleBase)):
                continue
            if obj is ModuleBase:
                continue  # skip the base class re-exported by the module
            mid = getattr(obj, "MODULE_ID", None)
            score = 0
            if mid and target_id and mid == target_id:
                score += 10
            if name.lower() == "vibrato":  # friendly hint
                score += 1
            candidates.append((score, obj))

        if candidates:
            candidates.sort(reverse=True)
            cls = candidates[0][1]
            _MOD_INSTANCE = cls()
            return _MOD_INSTANCE

        showlog.warn(f"[{_LOGTAG}] No ModuleBase subclass found in module.")
    except Exception as e:
        showlog.warn(f"[{_LOGTAG}] _get_mod_instance failed: {e}")'''
    
    if 'def _get_mod_instance():' in content:
        # Find the function and update it
        func_pattern = r'def _get_mod_instance\(\):.*?(?=\ndef |\nclass |\Z)'
        
        new_get_instance = '''def _get_mod_instance():
    """Create/cache the active module instance (class discovered dynamically)."""
    global _MOD_INSTANCE
    if _MOD_INSTANCE is not None:
        return _MOD_INSTANCE
    try:
        # 1) explicit factory wins
        factory = _get_module_attr("get_instance")
        if callable(factory):
            _MOD_INSTANCE = factory()
            return _MOD_INSTANCE

        target_id = _get_module_attr("MODULE_ID")

        # 2) find a real subclass (not the base) with matching MODULE_ID
        candidates = []
        for name in (dir(_ACTIVE_MODULE) if _ACTIVE_MODULE else []):
            obj = getattr(_ACTIVE_MODULE, name, None) if _ACTIVE_MODULE else None
            if not (isinstance(obj, type) and issubclass(obj, ModuleBase)):
                continue
            if obj is ModuleBase:
                continue  # skip the base class re-exported by the module
            mid = getattr(obj, "MODULE_ID", None)
            score = 0
            if mid and target_id and mid == target_id:
                score += 10
            candidates.append((score, obj))

        if candidates:
            candidates.sort(reverse=True)
            cls = candidates[0][1]
            _MOD_INSTANCE = cls()
            return _MOD_INSTANCE

        showlog.warn(f"[{_LOGTAG}] No ModuleBase subclass found in module.")
    except Exception as e:
        showlog.warn(f"[{_LOGTAG}] _get_mod_instance failed: {e}")'''
        
        content = re.sub(func_pattern, new_get_instance, content, flags=re.DOTALL)
        print("    ✓ Updated _get_mod_instance()")
    
    # Step 9: Write the result
    print("\n[9] Writing refactored file...")
    
    # Create backup
    backup_path = file_path.with_suffix('.py.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    print(f"    ✓ Backup created: {backup_path}")
    
    # Write new content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"    ✓ Refactored file written")
    
    # Step 10: Show summary
    print("\n" + "="*60)
    print("REFACTORING COMPLETE")
    print("="*60)
    print(f"Changes made:")
    print(f"  • Removed hardcoded import")
    print(f"  • Added _ACTIVE_MODULE global")
    print(f"  • Added set_active_module() function")
    print(f"  • Added _get_module_attr() helper")
    print(f"  • Replaced all mod.ATTR references")
    print(f"  • Fixed f-string references")
    print(f"  • Updated _get_mod_instance()")
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
