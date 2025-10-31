# modules/vibrato_maker_mod.py
import pygame

class VibratoMakerWidget:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        # Normalized (0-1) coordinates for dots
        self.low_y = 0.25          # 25% from bottom
        self.high_y = 0.75         # 25% from top  (we’ll invert y later)
        self.fade_x = 0.25         # 25% from left
        self.dragging = None       # 'low' or 'high'

    def _to_screen(self, x, y):
        """Convert normalized coords to screen coords inside self.rect."""
        sx = self.rect.left + x * self.rect.width
        sy = self.rect.top + (1 - y) * self.rect.height
        return int(sx), int(sy)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._check_grab(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = None
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._drag(event.pos)

    def _check_grab(self, pos):
        for name, (cx, cy) in (("low", self._to_screen(0, self.low_y)),
                               ("high", self._to_screen(self.fade_x, self.high_y))):
            if (pos[0]-cx)**2 + (pos[1]-cy)**2 < 10**2:
                self.dragging = name
                break

    def _drag(self, pos):
        x, y = pos
        # convert to normalized
        nx = (x - self.rect.left) / self.rect.width
        ny = 1 - (y - self.rect.top) / self.rect.height
        ny = max(0.0, min(1.0, ny))
        nx = max(0.0, min(1.0, nx))

        if self.dragging == "low":
            # low moves only vertically, below high
            self.low_y = min(ny, self.high_y - 0.02)
        elif self.dragging == "high":
            # high moves both, above low
            self.high_y = max(ny, self.low_y + 0.02)
            self.fade_x = nx

    def draw(self, surf):
        r = self.rect
        pygame.draw.rect(surf, (40, 40, 40), r, border_radius=10)
        # dotted lines helper
        def dotted_line(start, end, color):
            steps = 20
            for i in range(0, steps, 2):
                x = start[0] + (end[0]-start[0])*i/steps
                y = start[1] + (end[1]-start[1])*i/steps
                nx = start[0] + (end[0]-start[0])*(i+1)/steps
                ny = start[1] + (end[1]-start[1])*(i+1)/steps
                pygame.draw.line(surf, color, (x,y), (nx,ny), 1)

        # coords
        low_pt  = self._to_screen(0, self.low_y)
        high_pt = self._to_screen(self.fade_x, self.high_y)

        # horizontal guides
        dotted_line((r.left-20, low_pt[1]), (r.right+20, low_pt[1]), (120,120,120))
        dotted_line((r.left-20, high_pt[1]), (r.right+20, high_pt[1]), (160,160,160))
        # vertical fade line
        dotted_line((high_pt[0], r.top-10), (high_pt[0], r.bottom+10), (160,160,160))

        # dots
        pygame.draw.circle(surf, (0,255,255), low_pt, 8)
        pygame.draw.circle(surf, (255,100,255), high_pt, 8)
