"""
Compatibility wrapper for midiserver.py
Delegates to MIDIServer service in ServiceRegistry.
"""

from core.service_registry import ServiceRegistry

_registry = ServiceRegistry()
_midi = None


def _get_midi():
    global _midi
    if _midi is None:
        _midi = _registry.get('midi_server')
        if _midi is None:
            import showlog
            showlog.error("[MIDISERVER COMPAT] MIDIServer service not registered!")
    return _midi


def init(dial_cb=None, sysex_cb=None, note_cb=None):
    midi = _get_midi()
    if midi:
        midi.init(dial_cb, sysex_cb, note_cb)


def send_cc(channel, cc_num, value):
    midi = _get_midi()
    if midi:
        midi.send_cc(channel, cc_num, value)


def send_program_change(program_num, channel=None):
    midi = _get_midi()
    if midi:
        midi.send_program_change(program_num, channel)


def send_sysex(data, device=None):
    midi = _get_midi()
    if midi:
        midi.send_sysex(data, device)


def set_device_context(device_name):
    """Set current device context for automatic routing tag insertion."""
    midi = _get_midi()
    if midi:
        midi.set_device_context(device_name)


def enqueue_device_message(device_name, dial_index, value, param_range=127,
                           section_id=1, page_offset=0, dial_obj=None, cc_override=None):
    """Route device-specific MIDI message."""
    import showlog
    showlog.debug(f"[MIDISERVER WRAPPER] enqueue_device_message called with device={device_name}, dial={dial_index}, value={value}")
    
    midi = _get_midi()
    if midi:
        showlog.debug(f"[MIDISERVER WRAPPER] Got MIDI service, delegating to service.enqueue_device_message()")
        midi.enqueue_device_message(device_name, dial_index, value, param_range,
                                   section_id, page_offset, dial_obj, cc_override)
    else:
        showlog.error("[MIDISERVER WRAPPER] No MIDI service available!")


def is_connected():
    midi = _get_midi()
    return midi.is_connected() if midi else False


def __getattr__(name):
    midi = _get_midi()
    if midi and hasattr(midi, name):
        return getattr(midi, name)
    raise AttributeError(f"module 'midiserver' has no attribute '{name}'")
