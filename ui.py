"""
UI Application - Refactored Entry Point

This is the new, clean entry point for the UI application.
All complex logic has been moved to appropriate modules.

Original: 1000+ lines
Refactored: ~50 lines
"""

import crashguard  # Must come first
crashguard.checkpoint("Crashguard imported")

import sys
crashguard.checkpoint("sys imported")   

try:
    from core.app import UIApplication
    crashguard.checkpoint("UIApplication imported successfully")
except Exception as e:
    crashguard.emergency_log(f"FATAL: Failed to import UIApplication: {e}")
    import traceback
    crashguard.emergency_log(traceback.format_exc())
    raise


def main(): 
    """
    Application entry point.
        
    Initializes and runs the UI application.    
    All subsystem initialization and event loop management
    is handled by the UIApplication class.
    """
    crashguard.checkpoint("Entering main()")
    
    try:
        # Create application instance
        crashguard.checkpoint("Creating UIApplication instance...")
        app = UIApplication()
        crashguard.checkpoint("UIApplication instance created")
        
        # Initialize all subsystems
        # - Display/screen
        # - Hardware (MIDI, CV, network)
        # - State management
        # - Managers (dials, buttons, modes, etc.)
        # - Rendering pipeline
        crashguard.checkpoint("Starting app.initialize()...")
        app.initialize()
        crashguard.checkpoint("app.initialize() complete")
        
        # Run main event loop
        # - Process pygame events
        # - Process message queue
        # - Update state    
        # - Render frames
        # - Control frame rate
        crashguard.checkpoint("Entering main event loop...")
        app.run()
        
    except KeyboardInterrupt:
        crashguard.checkpoint("Interrupted by user (KeyboardInterrupt)")
        print("\n[EXIT] Interrupted by user")
    except Exception as e:
        crashguard.emergency_log(f"Application error: {e}")
        print(f"[ERROR] Application error: {e}")
        import traceback
        tb = traceback.format_exc()
        crashguard.emergency_log(tb)
        traceback.print_exc()
    finally:
        # Clean up resources
        crashguard.checkpoint("Entering cleanup...")
        if 'app' in locals():
            try:
                app.cleanup()
                crashguard.checkpoint("Cleanup complete")
            except Exception as e:
                crashguard.emergency_log(f"Error during cleanup: {e}")
        sys.exit()


if __name__ == "__main__":
    main()