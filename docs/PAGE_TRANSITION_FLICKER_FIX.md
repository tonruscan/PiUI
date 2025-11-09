# Page Transition Flicker Fix

## Date
November 1, 2025

**Last Updated**: November 1, 2025 - Applied review recommendations

## Problem Description

When transitioning from vibrato maker back to BMLPF page 2, users observed a visible flicker where page 1 dial labels (specifically "AMOUNT" on dial 5) would briefly flash on screen before the correct page 2 labels appeared. This created a jarring visual artifact during what should be a seamless page transition.

## Root Cause Analysis

### The Sequence of Events

The flicker was caused by a timing issue in the mode transition logic. Here's what was happening:

1. **Mode Switch Initiated**: User exits vibrato maker → `switch_mode("dials")` called → `_setup_dials()` executes

2. **Dial Rebuild**: `rebuild_dials(device_name)` creates 8 new Dial objects with generic properties

3. **REGISTRY Label Application**: When `device_name` was passed to `rebuild_dials()`, it triggered `_attach_state_manager_mapping()` which:
   - Loaded the device's REGISTRY (a slot-based label mapping)
   - Applied labels based on **dial position** (slot "05" = "Amount")
   - These were **page 1 labels** because the REGISTRY doesn't know about pages

4. **Race Condition**: Between steps 2-3 and step 5, the main event loop continued running and **rendered frames** showing these incorrect labels

5. **Page Configuration**: `on_button_press(2, suppress_render=True)` called `devices.update_from_device()` which:
   - Reconfigured dial labels for page 2
   - Set dial values from saved state
   - Set `is_empty` flags

6. **Frames Requested**: `request_full_frames(3)` queued redraws with correct configuration

### Why suppress_render Wasn't Enough

The `suppress_render=True` parameter only prevented `on_button_press()` from queuing a `force_redraw` message. It did NOT prevent the normal render loop from continuing to draw frames during the transition process. Since `_setup_dials()` executes synchronously within the event loop, any frames drawn during its execution would show incomplete/incorrect state.

### The Two-Stage Problem

1. **First Iteration**: REGISTRY was applying page 1 labels to dials based on slot position
2. **Second Iteration** (after fixing REGISTRY): Generic "Dial 1", "Dial 2" labels were still flashing

Both issues stemmed from the same root cause: **frames were being rendered while dials were in an intermediate configuration state**.

## Implemented Solution

### The Fix (v1 - Initial)

Added a `_transitioning` flag to `ModeManager` that blocks all rendering during mode transitions.

### Enhanced Fix (v2 - After Review)

Improved the initial solution with critical safeguards based on architectural review:

**In `managers/mode_manager.py`:**
- Changed to **mode-specific blocking**: `_transitioning_mode = "dials"` instead of global boolean
- Added **try/finally protection**: Ensures transition flag is always cleared, even on exceptions
- Added **micro-profiling**: Logs transition duration, warns if >40ms (perceptible delay)
- Added **REGISTRY bypass warning**: Explicit log when StateManager param_id mapping is skipped
- Added **page_id parameter** to `rebuild_dials()`: Groundwork for future page-aware factory pattern
- Split `_setup_dials()` into wrapper + `_setup_dials_internal()` for clean exception handling

**In `core/app.py`:**
- Changed render check to **mode-specific**: `is_mode_blocked(ui_mode)` instead of global `is_transitioning()`
- Allows other UI elements (overlays, animations) to continue rendering during dials transition

**In `managers/dial_manager.py`:**
- Added optional `page_id` parameter to `rebuild_dials()` (currently unused, documented for future use)

### How It Works

**v2 Enhanced Flow:**
```
switch_mode("dials")
  └─> _setup_dials()
        ├─> _transitioning_mode = "dials"     ← DIALS RENDERING BLOCKED (other modes can still render)
        ├─> start_time = perf_counter()       ← Begin profiling
        ├─> try:
        │     └─> _setup_dials_internal()
        │           ├─> rebuild_dials(device_name=None, page_id=None)  ← Generic labels, log warning
        │           ├─> _handle_dials_restore_last_button()
        │           │     └─> on_button_press(2, suppress_render=True)
        │           │           └─> update_from_device()  ← Applies correct page 2 labels
        │           └─> request_full_frames(3)           ← Queue redraws
        ├─> finally:
        │     ├─> _transitioning_mode = None   ← ALWAYS unblock, even on error
        │     └─> log duration (warn if >40ms)
```

**Key Improvements:**
- Mode-specific blocking prevents global render freeze
- Try/finally guarantees cleanup even if configuration fails
- Profiling detects perceptible delays (>1 frame at 25 FPS)
- Warning log tracks REGISTRY bypass for debugging
- Page-aware factory groundwork laid for future optimization

## Alternative Solutions (More Elegant)

### Option 1: Atomic State Updates with Double Buffering

**Concept**: Build the entire dial configuration in a "staging" area before swapping it into the active state atomically.

**Implementation**:
- Create a `StagedDialState` class that holds dial objects separate from the active set
- `_setup_dials()` would:
  - Create and configure dials in staging area
  - Call `update_from_device()` on staged dials
  - Load saved state into staged dials
  - Atomically swap staged → active in a single operation
- Render loop always uses active dials, never sees incomplete state

**Pros**:
- More architecturally sound (state management pattern)
- No need for blocking flags
- Could enable "preview" functionality in future
- Cleaner separation of concerns

**Cons**:
- Requires more refactoring
- Need to audit all code that accesses dials to ensure it uses active set
- Memory overhead (two sets of dials during transition)

### Option 2: Page-Aware Dial Factory

**Concept**: Make dial creation aware of the target page from the start.

**Implementation**:
- Add `page_id` parameter to `rebuild_dials()`
- Pass target page number down through the call chain
- `rebuild_dials()` creates dials with correct page-specific configuration immediately
- No intermediate "generic" or "page 1" state ever exists

**Pros**:
- Simpler than double buffering
- Dials are born correct, never need reconfiguration
- Could improve performance (one configuration pass instead of two)
- More intuitive logic flow

**Cons**:
- Still need transition blocking (frames could be drawn during dial creation)
- Requires `_setup_dials()` to know target page before calling `rebuild_dials()`
- Device-select and presets entry paths might not know page number yet

### Option 3: Deferred Rendering with Explicit Ready Signal

**Concept**: Pages explicitly signal when they're ready to render.

**Implementation**:
- Add `page_ready` flag per mode/page
- Mode transitions set `page_ready = False`
- Render loop checks `page_ready` before drawing
- Configuration completion sets `page_ready = True`
- Could be per-page rather than global

**Pros**:
- More granular than global transition flag
- Could handle partial page updates
- Explicit contract between modes and renderer
- Better for async page loading in future

**Cons**:
- More state to manage
- Need to ensure all code paths set ready flag
- Could be forgotten during development of new pages

### Option 4: Render Pipeline with Frame Queue

**Concept**: Separate state updates from rendering with explicit frame submission.

**Implementation**:
- Mode transitions don't trigger immediate renders
- Configuration completes, then submits first frame to render queue
- Render loop only displays frames from queue
- Empty queue = no render
- Could batch multiple state changes before frame submission

**Pros**:
- Clean separation of state and rendering
- Could enable render throttling, frame skipping
- More control over exactly what gets displayed when
- Could support multi-threaded rendering later

**Cons**:
- Significant architectural change
- More complex mental model
- Potential latency if not carefully implemented
- Overkill for current needs

## Recommendation

**For immediate use**: The implemented solution (transition blocking flag) is **adequate and effective**. It solves the problem with minimal code changes and is easy to understand.

**For future refactoring**: **Option 1 (Double Buffering)** or **Option 2 (Page-Aware Factory)** would be the most elegant long-term solutions:

- **Option 2** should be attempted first - it's simpler and addresses the real issue (dials being created without knowing their final configuration)
- If Option 2 still requires transition blocking, then **Option 1** provides the cleanest architectural solution
- Options 3 and 4 are more complex than needed for this specific problem

## Implementation Notes

### Current Limitations (Updated)

1. **~~Global Blocking~~** ✅ FIXED: Now mode-specific - only blocks dials mode rendering, other modes can continue

2. **REGISTRY Bypass** ⚠️ MONITORED: Passing `device_name=None` to `rebuild_dials()` means StateManager param_id mapping isn't set up until later. Now explicitly logged for debugging.

3. **Synchronous Assumption** ✅ PROTECTED: Try/finally ensures flag is cleared even if async changes are made later or exceptions occur

4. **Performance Monitoring** ✅ ADDED: Transition duration logged, warns if >40ms (perceptible at 25 FPS)

### Applied Review Recommendations

✅ **High Priority (Implemented):**
- Mode-specific blocking instead of global freeze
- Try/finally exception safety
- REGISTRY bypass warning log
- Transition duration profiling
- Groundwork for page-aware factory (page_id parameter added)

📋 **Medium Priority (Prepared):**
- Page-aware factory hooks in place (page_id parameter ready)
- Documentation for future layout epoch system
- Clear migration path to RenderContext integration

### Testing Considerations

- Test all entry paths: device_select → dials, presets → dials, vibrato → dials
- Test with different target pages (not just page 2)
- Verify no unintended side effects on other page transitions
- Check that muted dials don't flash (previous fix should still work)
- Verify empty dials (dial 8 on BMLPF) don't flash

## Related Files

- `managers/mode_manager.py` - Mode switching logic, transition flag
- `managers/dial_manager.py` - Dial creation, REGISTRY mapping
- `core/app.py` - Render loop, transition check
- `dialhandlers.py` - Button press handling, page switching
- `devices.py` - `update_from_device()` that applies page-specific configuration
- `device/bmlpf.py` - REGISTRY with slot-based label definitions

## Summary

The page transition flicker was caused by rendering frames while dials were in an intermediate configuration state. The implemented fix uses a **mode-specific transition blocking flag** with exception safety to prevent any rendering of the dials mode until configuration is complete. 

**v2 enhancements** address all high-priority review recommendations:
- Mode-specific blocking (no global freeze)
- Exception safety (try/finally)
- Performance monitoring (warns on slow transitions)
- Debug visibility (REGISTRY bypass logging)
- Future-ready (page-aware factory groundwork)

While effective and now production-hardened, more elegant solutions exist that would prevent the intermediate state from existing at all (page-aware dial factory or double-buffered state updates).

---

## Review Acknowledgment

This implementation incorporated feedback from architectural review emphasizing:
- **Scoped blocking** over global render freeze
- **Async safety** through try/finally patterns
- **Performance visibility** via micro-profiling
- **Forward compatibility** with page-aware factory hooks
- **Explicit state tracking** for debugging edge cases

The enhanced solution follows the principle: **Render only complete, versioned state** - implemented here as coarse-grained mode-specific versioning, with clear path to finer-grained epoch-based or staged state swap patterns.
