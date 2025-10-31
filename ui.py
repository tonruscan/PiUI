"""
UI Application - Refactored Entry Point

This is the new, clean entry point for the UI application.
All complex logic has been moved to appropriate modules.

Original: 1000+ lines
Refactored: ~50 lines
"""

import crashguard  # Must come first
import sys

from core.app import UIApplication


def main():
    """
    Application entry point.
    
    Initializes and runs the UI application.
    All subsystem initialization and event loop management
    is handled by the UIApplication class.
    """
    try:
        # Create application instance
        app = UIApplication()
        
        # Initialize all subsystems
        # - Display/screen
        # - Hardware (MIDI, CV, network)
        # - State management
        # - Managers (dials, buttons, modes, etc.)
        # - Rendering pipeline
        app.initialize()
        
        # Run main event loop
        # - Process pygame events
        # - Process message queue
        # - Update state
        # - Render frames
        # - Control frame rate
        app.run()
        
    except KeyboardInterrupt:
        print("\n[EXIT] Interrupted by user")
    except Exception as e:
        print(f"[ERROR] Application error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up resources
        if 'app' in locals():
            app.cleanup()
        sys.exit()


if __name__ == "__main__":
    main()
