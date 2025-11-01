#!/usr/bin/env python3
"""
Quick test to verify vibrato rotating button works.
"""

import sys
sys.path.insert(0, '.')

# Mock the dependencies
class MockModuleBase:
    def __init__(self):
        pass

sys.modules['system.module_core'] = type(sys)('system.module_core')
sys.modules['system.module_core'].ModuleBase = MockModuleBase
sys.modules['control'] = type(sys)('control')
sys.modules['control'].vibrato_control = None
sys.modules['modules.mod_helper'] = type(sys)('modules.mod_helper')
sys.modules['modules.mod_helper'].division_label_from_index = lambda *a: "1/4"
sys.modules['modules.mod_helper'].rate_hz_from_division_label = lambda *a: 8.0

import showlog
from modules.vibrato_mod import Vibrato

def test_rotating_button():
    print("\n=== Testing Vibrato Rotating Button ===\n")
    
    # Create instance
    v = Vibrato()
    
    print(f"Initial state: {v.stereo_mode.label()}")
    print(f"Initial channels: {v._get_active_channels()}")
    assert v.stereo_mode.label() == "L"
    assert v._get_active_channels() == [17]
    
    # Press button 2 three times
    for i in range(3):
        print(f"\n--- Press button 2 (iteration {i+1}) ---")
        v.stereo_mode.advance()
        v._update_button_label("2", v.stereo_mode.label())
        print(f"Mode: {v.stereo_mode.label()}")
        print(f"Channels: {v._get_active_channels()}")
        
        # Find button 2 in BUTTONS
        btn2_label = next(b["label"] for b in v.BUTTONS if b["id"] == "2")
        print(f"Button 2 label in BUTTONS: {btn2_label}")
    
    # Verify it cycled L → R → LR → L
    print(f"\nFinal state: {v.stereo_mode.label()}")
    assert v.stereo_mode.label() == "L"  # Wrapped back to start
    
    print("\n✓ Test passed! Rotating button works correctly.")

if __name__ == "__main__":
    try:
        test_rotating_button()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
