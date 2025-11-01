# Crash Detection Enhancement - Complete

## Overview

Enhanced crash detection and logging to capture silent startup failures that were not being logged.

## Changes Made

### 1. Enhanced `crashguard.py`

**New Features:**
- Dual logging: writes to **both** `crash.txt` and `ui_log.txt`
- Timestamps on all log entries
- Immediate flush and fsync (no buffering)
- Public API for manual checkpoints:
  - `crashguard.checkpoint(msg)` - Track initialization progress
  - `crashguard.emergency_log(msg)` - Critical failures

**Improvements:**
- Better exception formatting with full tracebacks
- Thread crash detection with thread name/ID
- Startup banner with Python version
- Automatic log file cleanup on exit
- Enhanced error messages with context

### 2. Verbose Initialization Tracking in `ui.py`

**Checkpoints Added:**
- `[CHECKPOINT] Crashguard imported`
- `[CHECKPOINT] sys imported`
- `[CHECKPOINT] UIApplication imported successfully`
- `[CHECKPOINT] Entering main()`
- `[CHECKPOINT] Creating UIApplication instance...`
- `[CHECKPOINT] UIApplication instance created`
- `[CHECKPOINT] Starting app.initialize()...`
- `[CHECKPOINT] app.initialize() complete`
- `[CHECKPOINT] Entering main event loop...`
- `[CHECKPOINT] Interrupted by user (KeyboardInterrupt)`
- `[CHECKPOINT] Entering cleanup...`
- `[CHECKPOINT] Cleanup complete`

**Emergency Logging:**
- Import failures logged with full traceback
- Application errors logged before propagation
- Cleanup errors captured

### 3. Detailed Checkpoints in `core/app.py`

**All initialization methods enhanced:**

**`_init_display()`:**
- DisplayManager import
- Instance creation
- Screen initialization
- SafeQueue creation
- Queue sharing

**`_init_logging()`:**
- showlog.init()
- showheader.init()
- showheader.init_queue()

**`_init_state_management()`:**
- state_manager import
- state_manager.init()
- RegistryInitializer creation
- CC registry initialization
- Entity registry initialization

**`_init_hardware()` (Phase 6 services):**
- Service imports (MIDIServer, CVClient, NetworkServer)
- Each service instance creation
- Service registration
- Network server start
- CV client async connection
- MIDI server initialization
- HardwareInitializer import/creation
- Final status report

## Log Files

### `crash.txt`
- Unhandled exceptions
- Thread crashes
- Segfaults (via faulthandler)
- Emergency logs
- Checkpoints

### `ui_log.txt`
- Normal application logging
- **Also receives crash information** (new!)
- Initialization checkpoints
- All emergency logs

## Usage

### Testing with Enhanced Logging

```bash
# On the Pi
cd ~/UI/build
python3 ui.py

# Check logs immediately if it crashes
cat ui_log.txt | tail -50
cat crash.txt | tail -50
```

### Expected Checkpoint Flow

```
[CHECKPOINT] Crashguard imported
[CHECKPOINT] sys imported
[CHECKPOINT] UIApplication imported successfully
[CHECKPOINT] Entering main()
[CHECKPOINT] Creating UIApplication instance...
[CHECKPOINT] UIApplication instance created
[CHECKPOINT] Starting app.initialize()...
[CHECKPOINT] _init_display: Starting (DisplayManager version)
[CHECKPOINT] _init_display: SafeQueue imported
[CHECKPOINT] _init_display: Creating DisplayManager (width=800, height=480)
[CHECKPOINT] _init_display: DisplayManager created
[CHECKPOINT] _init_display: Initializing display...
[CHECKPOINT] _init_display: Display initialized (800x480)
[CHECKPOINT] _init_display: SafeQueue created
[CHECKPOINT] _init_display: Complete
[CHECKPOINT] _init_logging: Starting
...
[CHECKPOINT] _init_hardware: Starting
[CHECKPOINT] _init_hardware: Service imports successful
[CHECKPOINT] _init_hardware: Creating MIDIServer...
[CHECKPOINT] _init_hardware: MIDIServer created
[CHECKPOINT] _init_hardware: Creating CVClient...
[CHECKPOINT] _init_hardware: CVClient created
[CHECKPOINT] _init_hardware: Creating NetworkServer...
[CHECKPOINT] _init_hardware: NetworkServer created
...
[CHECKPOINT] app.initialize() complete
[CHECKPOINT] Entering main event loop...
```

### Diagnosing Failures

1. **Find last checkpoint:**
   ```bash
   grep CHECKPOINT ui_log.txt | tail -1
   ```

2. **Look for emergency logs:**
   ```bash
   grep EMERGENCY crash.txt
   ```

3. **Check for exceptions:**
   ```bash
   grep "Unhandled Exception" crash.txt
   ```

4. **Thread crashes:**
   ```bash
   grep "THREAD CRASH" crash.txt
   ```

## Benefits

1. **Immediate visibility** - Every step logged before it happens
2. **No silent failures** - All crashes captured to files
3. **SSH-friendly** - No need for display access to debug
4. **Pinpoint accuracy** - Know exactly which line/import failed
5. **Dual logging** - Both crash.txt and ui_log.txt receive critical info
6. **Timestamps** - Track timing issues and hangs
7. **Thread-safe** - Captures crashes in background threads

## Next Steps

1. Test on Pi to capture the silent failure
2. Review logs to identify exact failure point
3. Fix root cause (likely pygame/display or service initialization)
4. Resume Phase 6 testing once stable

## Integration with Phase 6

This enhancement is **compatible** with all Phase 6 changes:
- Service classes (MIDIServer, CVClient, NetworkServer)
- ServiceRegistry lifecycle management
- All checkpoints added to service initialization

Once the issue is diagnosed and fixed, Phase 6 can continue with:
- Compatibility wrappers
- Module migration
- Global state removal
- Completion documentation
