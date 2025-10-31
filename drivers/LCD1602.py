# LCD1602.py — Raspberry Pi (CPython) shim for Waveshare LCD1602 (ST7032 @ 0x3E)
# API kept compatible with your code: init(addr), write(row,col,text), clear(), etc.

import time
from smbus2 import SMBus

# I2C addresses
LCD_ADDRESS = 0x3E          # ST7032 from your i2cdetect
SN3193_ADDR = 0x6B          # backlight driver on the same board (optional)

# ST7032 control bytes
_CTRL_CMD  = 0x00
_CTRL_DATA = 0x40

# Commands
_LCD_CLEARDISPLAY   = 0x01
_LCD_RETURNHOME     = 0x02
_LCD_ENTRYMODESET   = 0x04
_LCD_DISPLAYCONTROL = 0x08
_LCD_FUNCTIONSET    = 0x20
_LCD_SETDDRAMADDR   = 0x80

# Flags
_LCD_ENTRYLEFT      = 0x02
_LCD_ENTRYSHIFTDECR = 0x00
_LCD_DISPLAYON      = 0x04
_LCD_CURSOROFF      = 0x00
_LCD_BLINKOFF       = 0x00
_LCD_2LINE          = 0x08
_LCD_5x8DOTS        = 0x00
_LCD_8BITMODE       = 0x10  # ST7032 follows HD44780-like set

_bus = None
_inited = False

def _cmd(v: int):
    _bus.write_byte_data(LCD_ADDRESS, _CTRL_CMD, v & 0xFF)

def _data(v: int):
    _bus.write_byte_data(LCD_ADDRESS, _CTRL_DATA, v & 0xFF)

def _clear():
    _cmd(_LCD_CLEARDISPLAY)
    time.sleep(0.002)

def _home():
    _cmd(_LCD_RETURNHOME)
    time.sleep(0.002)

def _set_cursor(col: int, row: int):
    addr = (0x00 if row == 0 else 0x40) + max(0, min(15, col))
    _cmd(_LCD_SETDDRAMADDR | addr)

def init(addr: int = 0x3E):
    """Initialize LCD (and backlight) on Pi I2C-1; keeps your old function name."""
    global _bus, _inited, LCD_ADDRESS
    LCD_ADDRESS = addr
    if _bus is None:
        _bus = SMBus(1)

    # --- ST7032 init sequence (proven working) ---
    # Function set (Table 0)
    _cmd(_LCD_FUNCTIONSET | _LCD_8BITMODE | _LCD_2LINE | _LCD_5x8DOTS)
    time.sleep(0.005)
    _cmd(_LCD_FUNCTIONSET | _LCD_8BITMODE | _LCD_2LINE | _LCD_5x8DOTS)
    time.sleep(0.005)
    _cmd(_LCD_FUNCTIONSET | _LCD_8BITMODE | _LCD_2LINE | _LCD_5x8DOTS)

    # Switch to extended instruction table
    _cmd(0x39)  # Function set with IS=1 (extended)
    _cmd(0x14)  # Internal osc frequency
    _cmd(0x70 | 0x08)  # Contrast low bits (0..15) -> 8
    _cmd(0x5C | 0x00)  # Power/icon/contrast high bits
    _cmd(0x6C)         # Follower control (on)
    time.sleep(0.2)

    # Back to normal instruction table
    _cmd(0x38)
    _cmd(_LCD_DISPLAYCONTROL | _LCD_DISPLAYON | _LCD_CURSOROFF | _LCD_BLINKOFF)
    _clear()
    _cmd(_LCD_ENTRYMODESET | _LCD_ENTRYLEFT | _LCD_ENTRYSHIFTDECR)

    # Optional: turn backlight fully on (SN3193)
    try:
        _bus.write_byte_data(SN3193_ADDR, 0x00, 0x20)  # shutdown reg (required)
        _bus.write_byte_data(SN3193_ADDR, 0x02, 0x00)  # normal mode
        _bus.write_byte_data(SN3193_ADDR, 0x03, 0x00)  # current setting (Imax)
        _bus.write_byte_data(SN3193_ADDR, 0x04, 0xFF)  # PWM full
        _bus.write_byte_data(SN3193_ADDR, 0x07, 0x00)  # update
        _bus.write_byte_data(SN3193_ADDR, 0x1D, 0x0D)  # enable OUT1..3
        _bus.write_byte_data(SN3193_ADDR, 0x1C, 0x00)  # time update
    except Exception:
        pass

    _inited = True

def clear():
    if not _inited: init(LCD_ADDRESS)
    _clear()

def write(row: int, col: int, text: str):
    """Same signature you used before: write(row, col, text)."""
    if not _inited: init(LCD_ADDRESS)
    _set_cursor(col, 0 if row == 0 else 1)
    for ch in (text or "")[:16]:
        _data(ord(ch))

# (Optional helpers retained for compatibility with your old file)
def setCursor(col, row): write(row, col, "")
def printout(s): write(0, 0, str(s))
def clearDisplay(): clear()
