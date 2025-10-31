# get_patch_and_send_local.py
# Local output (Pi 3B) for your displays using drivers in build/drivers/.
# EXACT protocol:
#   DEV1 TXT:<text>            -> HT16K33 8-digit 7-seg (right-justified)
#   DEV2 TXT:<line1[|line2]>   -> LCD1602 (ST7032). '|' or '\n' splits to line2.
#
# Brightness:
#   - LED 7-seg brightness: SEG_BRIGHT (0..15) in config.py
#   - LCD backlight (SN3193): LCD_BRIGHT (0..100) in config.py
#
# Addresses (override in config.py if different):
#   HT16K33_ADDR = 0x70
#   LCD1602_ADDR = 0x3E
#   LCD_BACKLIGHT_ADDR = 0x6B   (SN3193 on your Waveshare board)

from typing import Optional
import showlog
import helper

# --- your drivers (now in build/drivers) ---
from drivers import LCD1602 as lcd
from drivers.ht16k33_seg8 import Seg8

# --- config (optional overrides) ---
try:
    import config as cfg
except Exception:
    class _Cfg: pass
    cfg = _Cfg()

_last_msg: Optional[str] = None

HT16K33_ADDR       = getattr(cfg, "HT16K33_ADDR", 0x70)
LCD1602_ADDR       = getattr(cfg, "LCD1602_ADDR", 0x3E)
LCD_BACKLIGHT_ADDR = getattr(cfg, "LCD_BACKLIGHT_ADDR", 0x6B)

SEG_BRIGHT = int(getattr(cfg, "SEG_BRIGHT", 15))   # 0..15
LCD_BRIGHT = int(getattr(cfg, "LCD_BRIGHT", 100))  # 0..100 (%)

# --- lazy singletons ---
_seg: Optional[Seg8] = None
_lcd_inited = False
_bkl_ready = None    # None=unknown, True/False after first try

# --- availability flags (None=unknown, True=ok, False=unavailable) ---
_seg_ok: Optional[bool] = None
_lcd_ok: Optional[bool] = None

# --- caches (if you later want incremental updates) ---
_last_led_text: Optional[str] = None
_last_lcd_line0: Optional[str] = None
_last_lcd_line1: Optional[str] = None


def _seg_init_once():
    """Init the HT16K33 8-digit 7-seg once and set brightness."""
    global _seg, _seg_ok
    if _seg_ok is False:
        return
    if _seg is not None:
        _seg_ok = True
        return
    try:
        _seg = Seg8(addr=HT16K33_ADDR)
        _seg.brightness(max(0, min(15, SEG_BRIGHT)))
        _seg_ok = True
        showlog.log(None, "[LED] HT16K33 ready")
    except Exception as e:
        _seg = None
        _seg_ok = False
        showlog.log(None, f"[LED] unavailable (skip): {type(e).__name__}: {e}")


def _lcd_init_once():
    """Init the ST7032 LCD and set backlight brightness if controller present."""
    global _lcd_inited, _lcd_ok
    if _lcd_ok is False:
        return
    if _lcd_inited:
        _lcd_ok = True
        return
    try:
        lcd.init(LCD1602_ADDR)
        _apply_lcd_backlight(LCD_BRIGHT)
        _lcd_inited = True
        _lcd_ok = True
        showlog.log(None, "[LCD] LCD1602 ready")
    except Exception as e:
        _lcd_inited = False
        _lcd_ok = False
        showlog.log(None, f"[LCD] unavailable (skip): {type(e).__name__}: {e}")


def _apply_lcd_backlight(percent: int):
    """
    Best-effort backlight control for SN3193 @ LCD_BACKLIGHT_ADDR.
    Safe to call even if the chip isn't there — it will just no-op.
    """
    global _bkl_ready
    if _bkl_ready is False:
        return

    try:
        from smbus2 import SMBus
        bus = SMBus(1)
        p = max(0, min(100, int(percent)))
        pwm = int(round(p * 255 / 100))

        # Minimal init sequence (same style as your earlier Pico-side logic)
        bus.write_byte_data(LCD_BACKLIGHT_ADDR, 0x00, 0x20)  # device enable
        bus.write_byte_data(LCD_BACKLIGHT_ADDR, 0x02, 0x00)  # normal mode
        bus.write_byte_data(LCD_BACKLIGHT_ADDR, 0x03, 0x00)  # current setting
        bus.write_byte_data(LCD_BACKLIGHT_ADDR, 0x04, pwm)   # PWM duty 0..255
        bus.write_byte_data(LCD_BACKLIGHT_ADDR, 0x07, 0x00)  # update
        bus.write_byte_data(LCD_BACKLIGHT_ADDR, 0x1D, 0x0D)  # enable OUT1..3
        bus.write_byte_data(LCD_BACKLIGHT_ADDR, 0x1C, 0x00)  # time update

        _bkl_ready = True
    except Exception:
        # silently mark unavailable; avoids spam on each call
        _bkl_ready = False


def set_led_brightness(level: int):
    """Public helper: set HT16K33 brightness 0..15."""
    _seg_init_once()
    if _seg_ok:
        try:
            _seg.brightness(max(0, min(15, int(level))))
        except Exception as e:
            showlog.log(None, f"[LED] brightness skipped: {type(e).__name__}: {e}")
    else:
        showlog.log(None, f"[LED] brightness skipped: device not present")


def set_lcd_brightness(percent: int):
    """Public helper: set LCD backlight 0..100%."""
    _lcd_init_once()
    if _lcd_ok:
        try:
            _apply_lcd_backlight(max(0, min(100, int(percent))))
        except Exception as e:
            showlog.log(None, f"[LCD] backlight skipped: {type(e).__name__}: {e}")
    else:
        showlog.log(None, f"[LCD] backlight skipped: device not present")
import time

def output_msg(msg: str):
    """
    Public entrypoint. Takes EXACT 'DEVx TXT:...' lines and updates local devices.

    DEV1 -> 8-digit 7-seg (right-justified by driver)
    DEV2 -> LCD1602 (line1[|line2])
    """
    global _last_led_text, _last_lcd_line0, _last_lcd_line1

    if not msg or "TXT:" not in msg:
        return

    try:
        head, body = msg.split("TXT:", 1)
        dev = head.strip().upper()
        body = body.strip()
    except ValueError:
        return

    if dev.startswith("DEV1"):
        # --- LED 7-seg ---
        _seg_init_once()
        if not _seg_ok:
            showlog.log(None, f"[LED] SKIP (not present) → {body!r}")
            return
        try:
            # NEW: duplicate guard for LED
            if body == _last_led_text:
                return
            _last_led_text = body
            _seg.text(body)
        except Exception as e:
            showlog.log(None, f"[LED] write skipped: {type(e).__name__}: {e}")
        return
    #sleep to allow preset buttons to keep up
    time.sleep(0.03)
    if dev.startswith("DEV2"):
        # --- LCD1602 ---
        _lcd_init_once()
        if not _lcd_ok:
            showlog.log(None, f"[LCD] SKIP (not present) → {body!r}")
            return

        try:
            body = helper.apply_text_case(body, uppercase=True)

            # split '|' or '\n' into up to two lines
            parts = body.split('|') if '|' in body else body.split('\n')
            line0 = (parts[0] if parts else "").strip()[:16]
            line1 = (parts[1].strip()[:16] if len(parts) > 1 else "")

            # NEW: duplicate guard for LCD (both lines unchanged)
            if line0 == _last_lcd_line0 and line1 == _last_lcd_line1:
                return

            _last_lcd_line0, _last_lcd_line1 = line0, line1

            # Clear then write (mirrors your Pico behavior)
            lcd.clear()
            lcd.write(0, 0, line0)
            if line1:
                lcd.write(1, 0, line1)
        except Exception as e:
            showlog.log(None, f"[LCD] write skipped: {type(e).__name__}: {e}")
        return

    # DEV3 not handled locally here (your TFT handled elsewhere)
    return
