# Phase 6: Global State Elimination - Implementation Plan

**Date:** October 31, 2025  
**Status:** READY FOR REVIEW  
**Priority:** LOW  
**Effort:** 4-5 hours  
**Risk:** HIGH (touches many files)  
**Impact:** Better architecture, testability

---

## 🎯 Objective

Eliminate global state from core service modules (`midiserver.py`, `cv_client.py`, `network.py`) by converting them to classes and managing instances through the existing ServiceRegistry.

---

## 📊 Current State Summary

### Completed Phases:
- ✅ **Phase 1:** Configuration Modularization (8 modules, 3 profiles)
- ✅ **Phase 2:** Root-Level Cleanup (duplicates removed, verified clean)
- ✅ **Phase 3:** Plugin System (PluginManager, ModuleRegistry, Vibrato migrated)
- ✅ **Phase 4:** Async Message Processing (Non-blocking queue, ~100Hz background thread)
- ❌ **Phase 5:** CLI Launcher (SKIPPED - not needed by user)

### What We Have Now:
- ServiceRegistry for dependency injection (already exists in `core/services.py`)
- Clean module structure with proper separation
- Config system with profiles
- Async message processing

---

## 🔍 The Problem

Three core modules use **global state** which makes them:
- Hard to test (can't mock)
- Tightly coupled to module-level variables
- Impossible to have multiple instances
- Difficult to track initialization state

### Current Global State Issues:

#### 1. **`midiserver.py`**
```python
# Global variables
output_port = None
input_port = None
midi_in_thread = None
running = False

def init():
    global output_port, input_port
    output_port = mido.open_output(...)
    input_port = mido.open_input(...)

def send_cc(channel, cc, value):
    global output_port
    if output_port:
        output_port.send(mido.Message('control_change', ...))
```

**Used by:** ~15+ files across the codebase

#### 2. **`cv_client.py`**
```python
# Global variables
cv_socket = None
connected = False

def connect():
    global cv_socket, connected
    cv_socket = socket.socket(...)
    cv_socket.connect(...)
    connected = True

def send_cv(channel, value):
    global cv_socket
    if cv_socket:
        cv_socket.send(...)
```

**Used by:** ~5 files (mostly control pages)

#### 3. **`network.py`**
```python
# Global variables
typing_server = None
typing_thread = None
server_running = False

def start_server():
    global typing_server, typing_thread, server_running
    typing_server = socket.socket(...)
    # ... etc
```

**Used by:** Fewer files, mostly initialization

---

## 🏗️ The Solution

Convert each module to a **class-based service** and register with ServiceRegistry.

### Architecture Pattern:

```
┌─────────────────────────────────────────┐
│         core/app.py (UIApplication)     │
│  ┌───────────────────────────────────┐  │
│  │     ServiceRegistry                │  │
│  │  ┌──────────────────────────────┐ │  │
│  │  │ 'midi_server' → MIDIServer   │ │  │
│  │  │ 'cv_client'   → CVClient     │ │  │
│  │  │ 'network'     → NetworkServer│ │  │
│  │  │ 'event_bus'   → EventBus     │ │  │
│  │  │ ... other services ...       │ │  │
│  │  └──────────────────────────────┘ │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
           ▲
           │ services.require('midi_server')
           │
    ┌──────┴───────┐
    │  Any module  │
    │  needs MIDI  │
    └──────────────┘
```

---

## 📝 Implementation Steps

### Step 1: Refactor `midiserver.py` → `MIDIServer` class

**Create:** `core/services/midi_server.py`

```python
"""
MIDI Server Service
Manages MIDI input/output ports and message handling.
"""
import mido
import threading
import showlog


class MIDIServer:
    """
    MIDI server service for handling MIDI I/O.
    Replaces global state in midiserver.py.
    """
    
    def __init__(self):
        self.output_port = None
        self.input_port = None
        self.midi_in_thread = None
        self.running = False
        self.message_callback = None
    
    def init(self, port_name=None, callback=None):
        """
        Initialize MIDI ports.
        
        Args:
            port_name: MIDI port name (auto-detect if None)
            callback: Function to call on incoming MIDI messages
        """
        try:
            # Open output port
            if port_name:
                self.output_port = mido.open_output(port_name)
            else:
                ports = mido.get_output_names()
                if ports:
                    self.output_port = mido.open_output(ports[0])
            
            # Open input port
            if port_name:
                self.input_port = mido.open_input(port_name)
            else:
                ports = mido.get_input_names()
                if ports:
                    self.input_port = mido.open_input(ports[0])
            
            self.message_callback = callback
            
            # Start input thread if we have input port
            if self.input_port:
                self.running = True
                self.midi_in_thread = threading.Thread(
                    target=self._input_loop,
                    daemon=True
                )
                self.midi_in_thread.start()
            
            showlog.info(f"[MIDI] Initialized: {self.output_port.name if self.output_port else 'No output'}")
            return True
            
        except Exception as e:
            showlog.error(f"[MIDI] Failed to initialize: {e}")
            return False
    
    def _input_loop(self):
        """Background thread for receiving MIDI messages."""
        while self.running and self.input_port:
            try:
                msg = self.input_port.receive()
                if self.message_callback:
                    self.message_callback(msg)
            except Exception as e:
                showlog.error(f"[MIDI] Input error: {e}")
                break
    
    def send_cc(self, channel, cc, value):
        """Send MIDI CC message."""
        if self.output_port:
            try:
                msg = mido.Message('control_change', 
                                   channel=channel, 
                                   control=cc, 
                                   value=value)
                self.output_port.send(msg)
            except Exception as e:
                showlog.error(f"[MIDI] Send error: {e}")
    
    def send_program_change(self, channel, program):
        """Send MIDI program change."""
        if self.output_port:
            try:
                msg = mido.Message('program_change', 
                                   channel=channel, 
                                   program=program)
                self.output_port.send(msg)
            except Exception as e:
                showlog.error(f"[MIDI] Send error: {e}")
    
    def cleanup(self):
        """Cleanup MIDI resources."""
        self.running = False
        
        if self.midi_in_thread and self.midi_in_thread.is_alive():
            self.midi_in_thread.join(timeout=1.0)
        
        if self.input_port:
            self.input_port.close()
            self.input_port = None
        
        if self.output_port:
            self.output_port.close()
            self.output_port = None
        
        showlog.info("[MIDI] Cleanup complete")
    
    def is_connected(self):
        """Check if MIDI ports are connected."""
        return self.output_port is not None or self.input_port is not None
```

---

### Step 2: Refactor `cv_client.py` → `CVClient` class

**Create:** `core/services/cv_client.py`

```python
"""
CV Client Service
Manages CV (Control Voltage) communication with hardware.
"""
import socket
import showlog


class CVClient:
    """
    CV client service for hardware communication.
    Replaces global state in cv_client.py.
    """
    
    def __init__(self):
        self.socket = None
        self.connected = False
        self.host = "192.168.1.100"  # Default, can be configurable
        self.port = 5000
    
    def connect(self, host=None, port=None):
        """
        Connect to CV hardware.
        
        Args:
            host: CV server host (optional)
            port: CV server port (optional)
        """
        if host:
            self.host = host
        if port:
            self.port = port
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            showlog.info(f"[CV] Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            showlog.error(f"[CV] Connection failed: {e}")
            self.connected = False
            return False
    
    def send_cv(self, channel, value):
        """
        Send CV value to hardware.
        
        Args:
            channel: CV channel (0-7)
            value: CV value (0-4095 for 12-bit DAC)
        """
        if not self.connected or not self.socket:
            return False
        
        try:
            # Format: "CV<channel>:<value>\n"
            message = f"CV{channel}:{value}\n"
            self.socket.send(message.encode())
            return True
        except Exception as e:
            showlog.error(f"[CV] Send error: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from CV hardware."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        self.connected = False
        showlog.info("[CV] Disconnected")
    
    def is_connected(self):
        """Check if connected to CV hardware."""
        return self.connected
```

---

### Step 3: Refactor `network.py` → `NetworkServer` class

**Create:** `core/services/network_server.py`

```python
"""
Network Server Service
Manages remote typing server and network services.
"""
import socket
import threading
import showlog


class NetworkServer:
    """
    Network server service for remote typing and network features.
    Replaces global state in network.py.
    """
    
    def __init__(self):
        self.server_socket = None
        self.server_thread = None
        self.running = False
        self.port = 8888
        self.clients = []
    
    def start(self, port=None):
        """
        Start network server.
        
        Args:
            port: Server port (default 8888)
        """
        if port:
            self.port = port
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            
            self.running = True
            self.server_thread = threading.Thread(
                target=self._server_loop,
                daemon=True
            )
            self.server_thread.start()
            
            showlog.info(f"[NETWORK] Server started on port {self.port}")
            return True
            
        except Exception as e:
            showlog.error(f"[NETWORK] Failed to start server: {e}")
            return False
    
    def _server_loop(self):
        """Background thread for accepting connections."""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                showlog.info(f"[NETWORK] Client connected: {addr}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    showlog.error(f"[NETWORK] Server error: {e}")
    
    def _handle_client(self, client_socket):
        """Handle individual client connection."""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                # Process received data
                # (implement your protocol here)
                
        except Exception as e:
            showlog.error(f"[NETWORK] Client error: {e}")
        finally:
            client_socket.close()
    
    def stop(self):
        """Stop network server."""
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)
        
        showlog.info("[NETWORK] Server stopped")
    
    def is_running(self):
        """Check if server is running."""
        return self.running
```

---

### Step 4: Register Services in `core/app.py`

**Modify:** `core/app.py` in the hardware initialization section:

```python
def _init_hardware(self):
    """Initialize hardware connections (MIDI, CV, Network)."""
    # Import new service classes
    from core.services.midi_server import MIDIServer
    from core.services.cv_client import CVClient
    from core.services.network_server import NetworkServer
    
    # Create and register MIDI server
    midi_server = MIDIServer()
    if not cfg.DISABLE_MIDI:
        midi_server.init(callback=self._handle_midi_input)
    self.services.register('midi_server', midi_server)
    showlog.info("[SERVICES] Registered: midi_server")
    
    # Create and register CV client
    cv_client = CVClient()
    if not cfg.DISABLE_NETWORK:
        cv_client.connect()
    self.services.register('cv_client', cv_client)
    showlog.info("[SERVICES] Registered: cv_client")
    
    # Create and register network server
    network_server = NetworkServer()
    if not cfg.DISABLE_NETWORK:
        network_server.start()
    self.services.register('network_server', network_server)
    showlog.info("[SERVICES] Registered: network_server")

def _handle_midi_input(self, msg):
    """Callback for incoming MIDI messages."""
    # Forward to message queue
    self.msg_queue.safe_put(("midi_input", msg))
```

---

### Step 5: Update All Callers

**Find and replace pattern across codebase:**

#### Before (global imports):
```python
import midiserver

midiserver.send_cc(channel, cc, value)
```

#### After (ServiceRegistry):
```python
# In classes that have access to app or services
midi_server = self.services.require('midi_server')
midi_server.send_cc(channel, cc, value)

# In standalone functions, pass services as parameter
def some_function(services):
    midi_server = services.require('midi_server')
    midi_server.send_cc(1, 10, 64)
```

---

### Step 6: Update All Files Using These Services

**Files to update (estimated ~20 files):**

#### MIDI Users:
- `control/dials_control.py`
- `control/global_control.py`
- `control/mixer_control.py`
- `control/patchbay_control.py`
- `control/presets_control.py`
- `device/quadraverb.py`
- `device/bmlpf.py`
- `device/pogolab.py`
- `handlers/midi_handler.py`
- `pages/mixer.py`
- `pages/patchbay.py`
- `dialhandlers.py`
- `preset_manager.py`

#### CV Users:
- `control/dials_control.py`
- `cv_client.py` (keep as compatibility wrapper or remove)

#### Network Users:
- `remote_typing_server.py` (refactor or remove)
- `network.py` (keep as compatibility wrapper or remove)

---

### Step 7: Create Compatibility Wrappers (Optional)

To minimize changes, create thin wrappers that delegate to ServiceRegistry:

**Keep:** `midiserver.py` as compatibility layer:
```python
"""
MIDI Server - Compatibility Wrapper
Delegates to core.services.midi_server.MIDIServer via ServiceRegistry.
"""
import showlog

# Module-level reference (set by app during init)
_midi_server = None

def _get_server():
    """Get MIDI server instance from ServiceRegistry."""
    if _midi_server is None:
        raise RuntimeError("MIDI server not initialized. Call set_instance() first.")
    return _midi_server

def set_instance(midi_server):
    """Set MIDI server instance (called by app during init)."""
    global _midi_server
    _midi_server = midi_server

# Compatibility functions
def send_cc(channel, cc, value):
    """Send MIDI CC (compatibility wrapper)."""
    _get_server().send_cc(channel, cc, value)

def send_program_change(channel, program):
    """Send program change (compatibility wrapper)."""
    _get_server().send_program_change(channel, program)

def is_connected():
    """Check connection (compatibility wrapper)."""
    return _get_server().is_connected()

# ... etc for other functions
```

**Then in app.py:**
```python
# After creating MIDIServer instance
import midiserver
midiserver.set_instance(midi_server)
```

This allows gradual migration without breaking existing code.

---

## 🧪 Testing Strategy

### Phase 1: Create Services
1. Create new service classes
2. Write unit tests for each service
3. Verify they work in isolation

### Phase 2: Register & Test
1. Register services in app.py
2. Test with compatibility wrappers
3. Verify existing code still works

### Phase 3: Gradual Migration
1. Update one control module at a time
2. Test after each change
3. Remove compatibility wrappers last

### Phase 4: Cleanup
1. Remove old global-state files
2. Remove compatibility wrappers
3. Update documentation

---

## 📊 Benefits vs Risks

### Benefits:
✅ **Testability** - Can mock services in tests  
✅ **Isolation** - Services don't depend on globals  
✅ **Flexibility** - Can swap implementations  
✅ **Clarity** - Explicit dependencies via ServiceRegistry  
✅ **Multiple Instances** - Could have test MIDI + real MIDI  

### Risks:
⚠️ **High Touch** - ~20 files need updates  
⚠️ **Breaking Changes** - If done incorrectly  
⚠️ **Testing Overhead** - Need comprehensive tests  
⚠️ **Runtime Errors** - ServiceRegistry.require() can raise if service missing  

---

## 🚀 Migration Path

### Option A: Big Bang (Fast but Risky)
1. Create all 3 service classes
2. Update all 20 files at once
3. Remove old files
4. Test everything

**Timeline:** 4-5 hours  
**Risk:** HIGH

### Option B: Gradual (Slower but Safer) ⭐ RECOMMENDED
1. Create MIDIServer class
2. Add compatibility wrapper
3. Test existing code works
4. Migrate files one-by-one
5. Repeat for CVClient and NetworkServer

**Timeline:** 6-8 hours (over multiple sessions)  
**Risk:** LOW

### Option C: Hybrid (Balanced)
1. Create all 3 service classes
2. Add compatibility wrappers for all
3. Test existing code works
4. Migrate critical files
5. Remove wrappers later

**Timeline:** 5-6 hours  
**Risk:** MEDIUM

---

## 📋 Checklist

### Preparation:
- [ ] Review current usage of midiserver/cv_client/network
- [ ] Create git branch: `phase6-global-state`
- [ ] Backup current working state

### Implementation:
- [ ] Create `core/services/midi_server.py`
- [ ] Create `core/services/cv_client.py`
- [ ] Create `core/services/network_server.py`
- [ ] Register services in `core/app.py`
- [ ] Create compatibility wrappers (if using gradual approach)
- [ ] Test basic functionality

### Migration:
- [ ] Update control modules (7 files)
- [ ] Update device modules (4 files)
- [ ] Update page modules (2 files)
- [ ] Update handlers (1 file)
- [ ] Update root-level files (3 files)

### Cleanup:
- [ ] Remove compatibility wrappers
- [ ] Remove old global-state files
- [ ] Update imports across codebase
- [ ] Run full test suite
- [ ] Update documentation

### Verification:
- [ ] All MIDI functions work
- [ ] All CV functions work
- [ ] All network functions work
- [ ] No global state remains
- [ ] ServiceRegistry correctly manages all services

---

## 💭 Decision Point

**Should we proceed with Phase 6?**

**Arguments FOR:**
- Better architecture
- Easier testing
- Cleaner code
- Aligns with existing ServiceRegistry pattern

**Arguments AGAINST:**
- High risk (many files)
- Time investment (4-8 hours)
- Current code works
- Could break things

**Recommendation:** If system is stable and working, consider this a **"nice to have"** for future work. Focus on features/fixes first, then tackle this when you have dedicated time for a refactor.

---

## 📝 Questions Before Starting

1. **Is the current global state causing actual problems?** (If not, maybe skip)
2. **Do you need better testability right now?** (If not, maybe defer)
3. **Are you comfortable with a high-risk refactor?** (If not, use gradual approach)
4. **How much time can you dedicate to this?** (Pick appropriate migration path)

---

**Status:** ⏸️ **AWAITING YOUR DECISION**

Please review and decide:
- ✅ Proceed with Phase 6 (specify migration path: A, B, or C)
- 🔄 Modify the plan (what changes?)
- ❌ Skip Phase 6 for now (focus on features)

---

**End of Document**
