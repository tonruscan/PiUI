#!/usr/bin/env python3
"""
Test and demonstration of the RotatingState class.
Run this to verify the rotating state manager works correctly.
"""

import sys
sys.path.insert(0, '..')  # Allow imports from parent directory

from utils.rotating_state import RotatingState, create_simple_rotation, create_multi_button_rotation


def test_simple_rotation():
    """Test basic string-based rotation."""
    print("\n=== Test 1: Simple String Rotation ===")
    mode = create_simple_rotation(["L", "R", "LR"])
    
    print(f"Initial state: {mode.label()}")
    assert mode.label() == "L"
    assert mode.index() == 0
    
    mode.advance()
    print(f"After advance: {mode.label()}")
    assert mode.label() == "R"
    assert mode.index() == 1
    
    mode.advance()
    print(f"After advance: {mode.label()}")
    assert mode.label() == "LR"
    
    mode.advance()
    print(f"After advance (wrap): {mode.label()}")
    assert mode.label() == "L"  # Wrapped around
    assert mode.index() == 0
    
    print("✓ Simple rotation test passed")


def test_dict_rotation():
    """Test rotation with dictionary states."""
    print("\n=== Test 2: Dictionary State Rotation ===")
    stereo = RotatingState([
        {"label": "L", "channels": [17], "mode": "left"},
        {"label": "R", "channels": [16], "mode": "right"},
        {"label": "LR", "channels": [17, 16], "mode": "stereo"},
    ])
    
    print(f"Initial: {stereo.label()}, channels={stereo.get('channels')}")
    assert stereo.get("channels") == [17]
    assert stereo.get("mode") == "left"
    
    stereo.advance()
    print(f"After advance: {stereo.label()}, channels={stereo.get('channels')}")
    assert stereo.get("channels") == [16]
    assert stereo.get("mode") == "right"
    
    stereo.advance()
    print(f"After advance: {stereo.label()}, channels={stereo.get('channels')}")
    assert stereo.get("channels") == [17, 16]
    
    print("✓ Dictionary rotation test passed")


def test_serialization():
    """Test preset save/restore."""
    print("\n=== Test 3: Serialization for Presets ===")
    mode = create_simple_rotation(["Fast", "Medium", "Slow"])
    
    mode.advance()
    mode.advance()
    print(f"State before save: {mode.label()}")
    
    # Serialize
    saved = mode.to_dict()
    print(f"Serialized: {saved}")
    assert saved["index"] == 2
    assert saved["label"] == "Slow"
    
    # Create new instance and restore
    mode2 = create_simple_rotation(["Fast", "Medium", "Slow"])
    mode2.from_dict(saved)
    print(f"State after restore: {mode2.label()}")
    assert mode2.label() == "Slow"
    assert mode2.index() == 2
    
    print("✓ Serialization test passed")


def test_multi_button():
    """Test multiple buttons with different rotations."""
    print("\n=== Test 4: Multi-Button Management ===")
    buttons = create_multi_button_rotation({
        "2": ["L", "R", "LR"],
        "3": ["1x", "2x", "4x"],
        "4": ["Sine", "Triangle", "Square"],
    })
    
    print(f"Button 2: {buttons['2'].label()}")
    print(f"Button 3: {buttons['3'].label()}")
    print(f"Button 4: {buttons['4'].label()}")
    
    # Simulate button presses
    buttons["2"].advance()
    print(f"Button 2 pressed: {buttons['2'].label()}")
    
    buttons["3"].advance()
    buttons["3"].advance()
    print(f"Button 3 pressed twice: {buttons['3'].label()}")
    
    assert buttons["2"].label() == "R"
    assert buttons["3"].label() == "4x"
    assert buttons["4"].label() == "Sine"
    
    print("✓ Multi-button test passed")


def test_set_by_label():
    """Test setting state by label (useful for presets)."""
    print("\n=== Test 5: Set by Label ===")
    mode = create_simple_rotation(["Off", "On", "Auto"])
    
    mode.set_label("Auto")
    print(f"Set to 'Auto': {mode.label()}")
    assert mode.label() == "Auto"
    assert mode.index() == 2
    
    mode.set_label("Off")
    print(f"Set to 'Off': {mode.label()}")
    assert mode.label() == "Off"
    assert mode.index() == 0
    
    print("✓ Set by label test passed")


def demo_vibrato_integration():
    """Show how to integrate with vibrato module."""
    print("\n=== Demo: Vibrato Stereo Mode Integration ===")
    
    # Create the stereo mode rotator
    stereo_mode = RotatingState([
        {"label": "L", "channels": [17]},
        {"label": "R", "channels": [16]},
        {"label": "LR", "channels": [17, 16]},
    ])
    
    # Simulate button presses and show what happens
    for i in range(5):
        state = stereo_mode.current()
        print(f"Press {i+1}: Mode={state['label']}, Channels={state['channels']}")
        stereo_mode.advance()
    
    print("\n✓ Integration demo complete")


if __name__ == "__main__":
    print("=" * 60)
    print("RotatingState Test Suite")
    print("=" * 60)
    
    try:
        test_simple_rotation()
        test_dict_rotation()
        test_serialization()
        test_multi_button()
        test_set_by_label()
        demo_vibrato_integration()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
