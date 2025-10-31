# ht16k33_seg8.py — Raspberry Pi (CPython) HT16K33 8-digit 7-seg driver
# Minimal API to match your Pico usage: Seg8(i2c_addr).text("1234"), .brightness(0..15)

from smbus2 import SMBus
import time

SEGMENTS = {
    " ": 0x00, "-": 0x40,
    "0": 0x3F, "1": 0x06, "2": 0x5B, "3": 0x4F, "4": 0x66,
    "5": 0x6D, "6": 0x7D, "7": 0x07, "8": 0x7F, "9": 0x6F,

    "A": 0x77, "B": 0x7C, "C": 0x39, "D": 0x5E, "E": 0x79, "F": 0x71,
    "G": 0x3D, "H": 0x76, "I": 0x06, "J": 0x1E, "K": 0x75, "L": 0x38,
    "M": 0x37, "N": 0x37, "O": 0x3F, "P": 0x73, "Q": 0x67, "R": 0x50,
    "S": 0x6D, "T": 0x78, "U": 0x3E, "V": 0x3E, "W": 0x7E, "X": 0x76,
    "Y": 0x6E, "Z": 0x5
}

class Seg8:
    def __init__(self, addr=0x70, busnum=1):
        self.addr = addr
        self.bus = SMBus(busnum)
        # init
        self.bus.write_byte_data(self.addr, 0x21, 0x00)      # oscillator on
        self.bus.write_byte_data(self.addr, 0x81, 0x00)      # display on, no blink
        self.brightness(15)                                  # max bright
        self.clear()

    def brightness(self, level: int):
        lvl = max(0, min(15, int(level)))
        self.bus.write_byte_data(self.addr, 0xE0 | lvl, 0x00)

    def clear(self):
        self.bus.write_i2c_block_data(self.addr, 0x00, [0x00]*16)

    def _put_digit(self, index: int, ch: str, dot: bool=False):
        # HT16K33 8-digit boards usually map digits to even addresses 0x00,0x02,...,0x0E
        # This assumes digit 0 is the LEFTMOST. If your board is opposite, we can flip.
        if not (0 <= index <= 7):
            return
        pat = SEGMENTS.get(ch.upper(), 0x00)
        if dot:
            pat |= 0x80
        self.bus.write_byte_data(self.addr, index*2, pat)

    def text(self, s: str):
        # Right-justify into 8 columns (like many counters)
        s = (s or "")[:8]
        pad = " " * (8 - len(s))
        s = pad + s
        # write left→right
        for i, ch in enumerate(s):
            self._put_digit(i, ch, dot=False)
