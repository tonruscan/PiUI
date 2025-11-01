"""
MIDI Server Service
Manages MIDI input/output ports and message handling.
Replaces global state in midiserver.py.
"""

import mido
import threading
import traceback
import showlog
import config as cfg
from core.services.base import ServiceBase


class MIDIServer(ServiceBase):
    """
    MIDI server service for handling MIDI I/O.
    Encapsulates MIDI port management, message sending, and input handling.
    """
    
    log_prefix = "[MIDI]"
    
    def __init__(self):
        """Initialize MIDI server (ports not yet opened)."""
        self.outport = None
        self.inport = None
        self.dial_handler = None
        self.sysex_handler = None
        self.running = False
        
        # Dynamic CC map for 8 dials based on config
        self.cc_map = list(range(cfg.DIAL_CC_START, cfg.DIAL_CC_START + 8))
    
    def init(self, dial_cb=None, sysex_cb=None, port_name_filter="USB MS1x1 MIDI Interface"):
        """
        Initialize MIDI ports and callbacks.
        
        Args:
            dial_cb: Callback function(dial_id, value) for CC messages
            sysex_cb: Callback function(device, layer, dial, value, cc_num) for SysEx
            port_name_filter: Port name filter string
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.dial_handler = dial_cb
        self.sysex_handler = sysex_cb
        
        try:
            ports_out = mido.get_output_names()
            ports_in = mido.get_input_names()
            showlog.debug(f"{self.log_prefix} Found OUT ports: {ports_out}")
            showlog.debug(f"{self.log_prefix} Found IN ports: {ports_in}")
            
            # Open output port
            for name in ports_out:
                if port_name_filter in name:
                    self.outport = mido.open_output(name)
                    showlog.info(f"{self.log_prefix} Output → {name}")
                    break
            
            if self.outport is None:
                showlog.warn(f"{self.log_prefix} ⚠️ No matching output port found (filter: {port_name_filter})")
            
            # Open input port with callback
            for name in ports_in:
                if port_name_filter in name:
                    self.inport = mido.open_input(name, callback=self._on_midi_in)
                    showlog.info(f"{self.log_prefix} Input ← {name}")
                    self.running = True
                    break
            
            if self.inport is None:
                showlog.warn(f"{self.log_prefix} ⚠️ No matching input port found (filter: {port_name_filter})")
            
            return self.is_connected()
            
        except Exception as e:
            showlog.error(f"{self.log_prefix} Initialization error: {e}")
            return False
    
    def _on_midi_in(self, msg):
        """
        Handle incoming MIDI messages (CC or SysEx).
        Called by mido's input port callback.
        """
        try:
            if msg.type == "control_change":
                cc_num = msg.control
                
                # Map CC → dial ID (1..8)
                if cc_num in self.cc_map:
                    dial_index = self.cc_map.index(cc_num)  # 0..7
                    dial_id = dial_index + 1                 # 1..8 for dialhandlers
                    if self.dial_handler:
                        self.dial_handler(dial_id, msg.value)
            
            elif msg.type == "sysex":
                data = list(msg.data)
                showlog.debug(f"{self.log_prefix} SYSEX RAW: {data}")
                
                if len(data) >= 6 and data[0] == 0x7D:
                    # F0 7D <device> <layer> <dial> <value> <ccnum> F7
                    device, layer, dial_id, value, cc_in = data[1:6]
                    
                    # Normalize device name/code
                    if isinstance(device, str):
                        device = device.strip().upper()
                    
                    if self.sysex_handler:
                        self.sysex_handler(device, layer, dial_id, value, cc_in)
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} Input handler error: {e}")
            showlog.debug(f"{self.log_prefix} msg={msg!r}, cc_map={self.cc_map}")
    
    def send_cc(self, target_type, index, value):
        """
        Send a MIDI CC message.
        
        Args:
            target_type: "dial" or "button"
            index: 0-based index (0..7 for dials, 0..4 for buttons)
            value: 0–127
        """
        try:
            if self.outport is None:
                showlog.error(f"{self.log_prefix} No outport available")
                return
            
            if target_type == "dial":
                cc_num = cfg.DIAL_CC_START + index
            elif target_type == "button":
                cc_num = cfg.BUTTON_CC_START + index
            else:
                showlog.warn(f"{self.log_prefix} Unknown target_type '{target_type}'")
                return
            
            msg = mido.Message(
                "control_change",
                control=cc_num,
                value=value,
                channel=cfg.CC_CHANNEL
            )
            self.outport.send(msg)
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} send_cc error: {e}")
    
    def send_cc_raw(self, cc_num, value):
        """
        Send a specific CC number directly.
        
        Args:
            cc_num: MIDI CC number (0-127)
            value: MIDI value (0-127)
        """
        try:
            if self.outport is None:
                return
            
            msg = mido.Message(
                "control_change",
                control=cc_num,
                value=value,
                channel=cfg.CC_CHANNEL
            )
            self.outport.send(msg)
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} send_cc_raw error: {e}")
    
    def send_bytes(self, data):
        """
        Send raw 3-byte MIDI message.
        
        Args:
            data: bytes or list of bytes (3 bytes)
        """
        try:
            if self.outport is None:
                showlog.error(f"{self.log_prefix} No active outport for send_bytes")
                return
            
            # Force conversion to bytes
            if isinstance(data, list):
                data = bytes(data)
            
            showlog.debug(f"{self.log_prefix} Raw bytes: {[hex(b) for b in data]}")
            
            msg = mido.Message.from_bytes(data)
            showlog.debug(f"{self.log_prefix} Mido message: {msg}")
            
            self.outport.send(msg)
            
            status = data[0]
            ch = (status & 0x0F) + 1
            msg_type = status & 0xF0
            kind = "NoteOn" if msg_type == 0x90 else f"Status {status:02X}"
            showlog.debug(f"{self.log_prefix} Send_bytes → {kind} ch{ch} {data[1]:02X} {data[2]:02X}")
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} send_bytes error: {e}")
    
    def send_program_change(self, program_num, channel=None):
        """
        Send MIDI Program Change message.
        
        Args:
            program_num: Program number (0-127)
            channel: MIDI channel (0-15), defaults to cfg.CC_CHANNEL
        """
        try:
            if self.outport is None:
                return
            
            ch = cfg.CC_CHANNEL if channel is None else channel
            msg = mido.Message("program_change", program=program_num, channel=ch)
            self.outport.send(msg)
            showlog.debug(f"{self.log_prefix} Program Change → ch{ch+1} prog={program_num}")
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} send_program_change error: {e}")
    
    def send_sysex(self, data):
        """
        Send MIDI SysEx message.
        
        Args:
            data: SysEx data (list of bytes or tuple)
        """
        try:
            if self.outport is None:
                showlog.error(f"{self.log_prefix} No outport for SysEx")
                return
            
            msg = mido.Message("sysex", data=data)
            self.outport.send(msg)
            showlog.debug(f"{self.log_prefix} SysEx sent: {len(data)} bytes")
        
        except Exception as e:
            showlog.error(f"{self.log_prefix} send_sysex error: {e}")
    
    def enqueue_device_message(self, device_name, dial_index, value, param_range=127,
                                section_id=1, page_offset=0, dial_obj=None, cc_override=None):
        """
        Route device-specific MIDI message (calls device driver).
        
        Args:
            device_name: Device name (uppercase)
            dial_index: Dial number (1-8)
            value: Dial value (0-127)
            param_range: Parameter range from device config
            section_id: Page/section ID
            page_offset: Page offset for multi-page devices
            dial_obj: Dial UI object reference
            cc_override: Override CC number (optional)
        """
        showlog.debug(f"{self.log_prefix} enqueue_device_message called: device={device_name}, dial={dial_index}, value={value}, cc_override={cc_override}")
        
        try:
            # Route to device-specific driver
            if device_name == "QUADRAVERB":
                import quadraverb_driver as qv
                showlog.debug(f"{self.log_prefix} Routing to quadraverb_driver.send_sysex()")
                qv.send_sysex(
                    self.outport,
                    section_id,
                    dial_index,
                    value,
                    param_range,
                    page_offset,
                    dial_obj
                )
            else:
                # Generic CC send for other devices
                if cc_override is not None:
                    showlog.debug(f"{self.log_prefix} Sending CC override: {cc_override} = {value}")
                    self.send_cc_raw(cc_override, value)
                else:
                    cc_num = cfg.DIAL_CC_START + (dial_index - 1)
                    showlog.debug(f"{self.log_prefix} Sending generic CC: {cc_num} = {value}")
                    self.send_cc_raw(cc_num, value)
                    
        except Exception as e:
            showlog.error(f"{self.log_prefix} enqueue_device_message error: {e}")
            import traceback
            showlog.error(traceback.format_exc())
    
    def is_connected(self):
        """Check if any MIDI ports are connected."""
        return self.outport is not None or self.inport is not None
    
    def cleanup(self):
        """Cleanup MIDI resources (close ports)."""
        self.running = False
        
        if self.inport:
            try:
                self.inport.close()
                showlog.info(f"{self.log_prefix} Input port closed")
            except Exception as e:
                showlog.error(f"{self.log_prefix} Error closing input: {e}")
            self.inport = None
        
        if self.outport:
            try:
                self.outport.close()
                showlog.info(f"{self.log_prefix} Output port closed")
            except Exception as e:
                showlog.error(f"{self.log_prefix} Error closing output: {e}")
            self.outport = None
        
        showlog.info(f"{self.log_prefix} Cleanup complete")
