# assets/ui_button.py
import pygame
import helper
import config as cfg

def draw_button(screen, rect, display_label, font,
                pressed_button=None, selected_buttons=None,
                button_id=None, disabled=False,
                fill_color=(60, 60, 60), outline_color=(100, 100, 100), text_color=(255, 255, 255),
                disabled_fill=(30, 30, 30), disabled_text=(100, 100, 100),
                active_fill=(150, 0, 150), active_text=(255, 255, 255)):

    """
    Draw one rectangular UI button with proper colors and text.
    'display_label' is what appears visually (e.g. R, D, P, E),
    while 'button_id' is the logical ID used for highlighting (e.g. "1", "2", etc.).
    """
    if selected_buttons is None:
        selected_buttons = set()

    btn_id = button_id or display_label  # internal ID for state logic

    # --- choose colour scheme (theme-aware) ---
    if disabled:
        bg = helper.hex_to_rgb(disabled_fill)
        text_col = helper.hex_to_rgb(disabled_text)
    elif btn_id in selected_buttons or btn_id == pressed_button:
        bg = helper.hex_to_rgb(active_fill)
        text_col = helper.hex_to_rgb(active_text)
    else:
        bg = helper.hex_to_rgb(fill_color)
        text_col = helper.hex_to_rgb(text_color)


    # --- draw background + border ---
    pygame.draw.rect(screen, bg, rect, border_radius=10)
    pygame.draw.rect(screen, helper.hex_to_rgb(outline_color), rect, width=2, border_radius=10)

    # --- render text label ---
    text_surf = font.render(str(display_label), True, text_col)
    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)
