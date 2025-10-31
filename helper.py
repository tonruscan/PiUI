# helper.py
import pygame

def hex_to_rgb(value):
    """Convert '#RRGGBB' hex string or RGB tuple to (r, g, b)."""
    if isinstance(value, (tuple, list)) and len(value) == 3:
        return tuple(value)
    if isinstance(value, str):
        value = value.strip().lstrip('#')
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    raise TypeError(f"Unsupported color format: {value!r}")



def render_text_with_spacing(text, font, color, spacing=0):
    """Render text surface with custom letter spacing and safe right padding."""
    surfaces = []
    total_width = 0
    max_height = 0

    for ch in text:
        ch_surf = font.render(ch, True, color)
        surfaces.append(ch_surf)
        total_width += ch_surf.get_width() + spacing
        max_height = max(max_height, ch_surf.get_height())

    # add small right-hand padding (2–4px) to prevent clipping of last glyph
    final_surf = pygame.Surface((total_width + 4, max_height), pygame.SRCALPHA)

    x = 0
    for surf in surfaces:
        final_surf.blit(surf, (x, 0))
        x += surf.get_width() + spacing

    return final_surf, final_surf.get_rect()


def apply_text_case(text: str, uppercase: bool = False) -> str:
    """Return text converted to uppercase if enabled."""
    return text.upper() if uppercase else text


# -------------------------------------------------------------------
# Device theme resolver
# -------------------------------------------------------------------
import importlib
import showlog

class device_theme:
    @staticmethod
    def get(device_name: str, key: str, fallback=None):
        """
        Safe color/setting resolver:
        Priority:
          1️⃣  device.<name>.THEME[key]
          2️⃣  config.<KEY.upper()>
          3️⃣  provided fallback argument
          4️⃣  '#FFFFFF' (final default)
        """
        # --- Step 0: safe import of config ---
        try:
            import config as cfg
        except Exception:
            cfg = None

        # --- Step 1: device THEME lookup ---
        try:
            if device_name:
                dev_module = importlib.import_module(f"device.{device_name.lower()}")
                theme = getattr(dev_module, "THEME", {})
                if key in theme:
                    val = theme[key]
                   
                    showlog.verbose2(f"[THEME] {device_name}.{key} → device")
                    return val
        except Exception as e:
            # Silently ignore missing module or bad import

            showlog.verbose2(f"[THEME] Missing or invalid THEME for {device_name}: {e}")

        # --- Step 2: config fallback ---
        if cfg:
            try:
                cfg_key = key.upper()
                if hasattr(cfg, cfg_key):
                    val = getattr(cfg, cfg_key)
                    
                    showlog.verbose2(f"[THEME] {device_name}.{key} → config")
                    return val
            except Exception as e:
                
                showlog.error(f"[THEME] Config lookup failed for {key}: {e}")

        # --- Step 3: provided fallback argument ---
        if fallback:
            
            showlog.verbose2(f"[THEME] {device_name}.{key} → fallback ({fallback})")
            return fallback

        # --- Step 4: hardcoded default ---
        
        showlog.verbose2(f"[THEME] {device_name}.{key} → default (#FFFFFF)")
        return "#FFFFFF"



def theme_rgb(device_name: str, key: str, default: str = "#FFFFFF"):
    """
    Unified theme lookup:
    - key should match config constant name (e.g. 'DIAL_MUTE_PANEL')
    - automatically looks up lowercased version in THEME (e.g. 'dial_mute_panel')
    - falls back to config.<KEY> or 'default'
    - returns RGB tuple
    """
    try:
        import config as cfg
    except Exception:
        cfg = None

    theme_key = key.lower()  # convert to match THEME dict naming
    fallback = default

    # Try to get fallback from config if present
    if cfg:
        try:
            fallback = getattr(cfg, key)
        except AttributeError:
            pass

    hex_val = device_theme.get(device_name, theme_key, fallback)
    return hex_to_rgb(hex_val)
