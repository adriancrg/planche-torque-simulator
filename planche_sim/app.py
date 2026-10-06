"""Interactive matplotlib front end for the planche model.

The figure is built once; sliders only update the data of existing artists, so
dragging a slider is smooth (the original version cleared and redrew the axes on
every event).
"""
from __future__ import annotations

import math
import textwrap
from dataclasses import replace

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle
from matplotlib.widgets import Button, Slider, TextBox

from .i18n import STRINGS
from .model import LEN_FRAC, PRESETS, Pose, Result, relative_to_full, solve

# --- Look --------------------------------------------------------------------
BG, PANEL, GRID = "#12151A", "#1A1F27", "#2A313C"
INK, MUTED = "#E6E9EE", "#8A93A0"
TRUNK, LIMB, ARM = "#5CC8FF", "#8FA8FF", "#E6E9EE"
FORCE, GOOD, WARN = "#FFB454", "#5BE49B", "#FF6B6B"

FORCE_SCALE = 0.00042  # metres of arrow per newton

SLIDERS = [  # key, label key, min, max, step, decimals
    ("weight_kg", "weight", 40, 120, 0.5, 1),
    ("height_m", "height", 1.50, 2.10, 0.01, 2),
    ("straddle_deg", "straddle", 0, 180, 1, 0),
    ("hip_deg", "hip", 0, 135, 1, 0),
    ("knee_deg", "knee", 0, 135, 1, 0),
    ("tilt_deg", "tilt", -20, 40, 1, 0),
]
PRESET_BUTTONS = [("tuck", "tuck"), ("adv_tuck", "adv_tuck"), ("straddle", "straddle_p"), ("full", "full")]


def _arrow(ax, color, lw=2.2):
    return ax.annotate("", xy=(0, 0), xytext=(0, 0), zorder=8,
                       arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, shrinkA=0, shrinkB=0,
                                       mutation_scale=14))


class PlancheApp:
    def __init__(self, pose: Pose | None = None, lang: str = "en"):
        self.t = STRINGS[lang]
        self.pose = pose or Pose()
        self.overlays = True
        self._muted = False
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build(self):
        t = self.t
        plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
        self.fig = plt.figure(figsize=(12.5, 7.4), facecolor=BG)
        try:
            self.fig.canvas.manager.set_window_title(t["title"])
        except Exception:
            pass
        self.ax = self.fig.add_axes([0.04, 0.35, 0.60, 0.60], facecolor=BG)
        self.info = self.fig.add_axes([0.67, 0.35, 0.30, 0.60], facecolor=PANEL)
        self._build_scene()
        self._build_info()
        self._build_controls()

    def _build_scene(self):
        ax, t = self.ax, self.t
        ax.set_xlim(-1.0, 2.0)
        ax.set_ylim(-0.18, 1.12)
        ax.set_aspect("equal")
        ax.set_xticks(np.arange(-1.0, 2.01, 0.5))
        ax.set_yticks(np.arange(0.0, 1.01, 0.5))
        ax.tick_params(colors=MUTED, labelsize=8, length=0)
        ax.set_xlabel("m", color=MUTED, fontsize=8, loc="right")
        ax.grid(True, color=GRID, lw=0.6)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(t["title"], loc="left", color=INK, fontsize=13, fontweight="bold", pad=10)

        ax.axhline(0, color=MUTED, lw=1.6, zorder=2)
        ax.fill_between([-1.0, 2.0], -0.18, 0, facecolor=PANEL, hatch="///", edgecolor=GRID, lw=0, zorder=1)
        self.vline, = ax.plot([0, 0], [0, 1], color=FORCE, lw=1, ls=(0, (4, 4)), alpha=0.6, zorder=2)

        kw = dict(solid_capstyle="round", zorder=4)
        self.hand, = ax.plot([], [], color=MUTED, lw=5, solid_capstyle="round", zorder=3)
        self.arm, = ax.plot([], [], color=ARM, lw=6, **kw)
        self.trunk, = ax.plot([], [], color=TRUNK, lw=12, **kw)
        self.thigh, = ax.plot([], [], color=LIMB, lw=9, **kw)
        self.shank, = ax.plot([], [], color=LIMB, lw=7, **kw)
        self.foot, = ax.plot([], [], color=LIMB, lw=4, **kw)
        self.head = Circle((0, 0), 0.1, facecolor=PANEL, edgecolor=TRUNK, lw=3, zorder=5)
        ax.add_patch(self.head)
        self.joints, = ax.plot([], [], "o", color=INK, mec=BG, mew=1.5, ms=8, zorder=6)

        self.cg_arms_pt, = ax.plot([], [], "o", color=ARM, mec=BG, ms=6, zorder=9)
        self.cg_body_pt, = ax.plot([], [], "o", mfc=BG, mec=FORCE, mew=2, ms=9, zorder=9)
        self.cg_total_pt, = ax.plot([], [], "o", color=FORCE, mec=BG, mew=1.5, ms=13, zorder=10)
        self.cg_label = ax.text(0, 0, t["cg"], color=INK, fontsize=9, fontweight="bold", ha="left", va="bottom", zorder=10)

        self.w_arrow = _arrow(ax, FORCE)
        self.n_arrow = _arrow(ax, GOOD)
        self.f_label = ax.text(0.07, -0.09, "", color=INK, fontsize=9, ha="left", va="center", zorder=10,
                               bbox=dict(facecolor=BG, edgecolor="none", pad=2))

        self.dim = ax.annotate("", xy=(0, 0), xytext=(0, 0), zorder=8,
                               arrowprops=dict(arrowstyle="<|-|>", color=INK, lw=1.2, shrinkA=0,
                                               shrinkB=0, mutation_scale=9))
        self.dim_label = ax.text(0, 0, "", color=INK, fontsize=10, ha="center", va="bottom", zorder=10)

        self.arc, = ax.plot([], [], color=TRUNK, lw=2, zorder=7)
        self.arc_head = ax.annotate("", xy=(0, 0), xytext=(0, 0), zorder=7,
                                    arrowprops=dict(arrowstyle="-|>", color=TRUNK, lw=2, shrinkA=0,
                                                    shrinkB=0, mutation_scale=13))
        self.tau_label = ax.text(0, 0, "", color=INK, fontsize=10, fontweight="bold", ha="center", va="bottom", zorder=10)
        self.overlay_artists = [self.vline, self.cg_arms_pt, self.cg_body_pt, self.cg_total_pt, self.cg_label,
                                self.w_arrow, self.n_arrow, self.f_label, self.dim,
                                self.dim_label, self.arc, self.arc_head, self.tau_label]

    def _build_info(self):
        t, a = self.t, self.info
        a.set_xticks([])
        a.set_yticks([])
        for s in a.spines.values():
            s.set_color(GRID)
        a.text(0.06, 0.94, t["headline"], color=MUTED, fontsize=10, va="top", transform=a.transAxes)
        self.big = a.text(0.06, 0.87, "", color=TRUNK, fontsize=34, fontweight="bold", va="top",
                          transform=a.transAxes)
        self.sub = a.text(0.06, 0.755, "", color=MUTED, fontsize=10, va="top", transform=a.transAxes)
        self.rows = []
        labels = ["lean", "dist", "height_sh", "normal", "muscle", "per_kg", "vs_full"]
        for i, key in enumerate(labels):
            y = 0.60 - i * 0.07
            a.text(0.06, y, t[key], color=MUTED, fontsize=9, va="center", transform=a.transAxes)
            self.rows.append(a.text(0.94, y, "", color=INK, fontsize=10, fontweight="bold", va="center",
                                    ha="right", transform=a.transAxes))
        a.plot([0.06, 0.94], [0.645, 0.645], color=GRID, lw=1, transform=a.transAxes)
        a.text(0.06, 0.14, textwrap.fill(t["note"], 52), color=MUTED, fontsize=7.5, va="top",
               transform=a.transAxes)
        self.warn = a.text(0.06, 0.055, "", color=WARN, fontsize=8.5, fontweight="bold", va="center",
                           transform=a.transAxes)

    def _build_controls(self):
        t, fig = self.t, self.fig
        self.sliders: dict[str, Slider] = {}
        self.boxes: dict[str, TextBox] = {}
        self.specs = {k: (lo, hi, dec) for k, _, lo, hi, _, dec in SLIDERS}
        for i, (key, lab, lo, hi, step, dec) in enumerate(SLIDERS):
            y = 0.255 - i * 0.043
            sax = fig.add_axes([0.17, y, 0.31, 0.022], facecolor=GRID)
            fig.text(0.04, y + 0.011, t[lab], color=INK, fontsize=9, va="center")
            style = dict(handle_style=dict(facecolor=INK, edgecolor=BG, size=11), initcolor="none")
            try:
                sl = Slider(sax, "", lo, hi, valinit=getattr(self.pose, key), valstep=step, color=TRUNK,
                            track_color=GRID, **style)
            except TypeError:  # older matplotlib without these options
                sl = Slider(sax, "", lo, hi, valinit=getattr(self.pose, key), valstep=step, color=TRUNK)
            sl.valtext.set_visible(False)
            tb_ax = fig.add_axes([0.51, y - 0.002, 0.07, 0.026])
            tb = TextBox(tb_ax, "", initial=f"{getattr(self.pose, key):.{dec}f}", color=PANEL, hovercolor=GRID)
            tb.text_disp.set_color(INK)
            tb.text_disp.set_fontsize(9)
            sl.on_changed(lambda v, k=key: self._on_slider(k, v))
            tb.on_submit(lambda text, k=key: self._on_submit(k, text))
            self.sliders[key], self.boxes[key] = sl, tb

        fig.text(0.67, 0.275, t["presets"], color=MUTED, fontsize=9)
        self.buttons = []
        for i, (name, lab) in enumerate(PRESET_BUTTONS):
            bax = fig.add_axes([0.67 + i * 0.0765, 0.205, 0.071, 0.05])
            b = Button(bax, t[lab], color=PANEL, hovercolor=GRID)
            b.label.set_color(INK)
            b.label.set_fontsize(9)
            b.on_clicked(lambda _e, n=name: self.apply_preset(n))
            self.buttons.append(b)
        tax = fig.add_axes([0.67, 0.12, 0.15, 0.05])
        self.toggle = Button(tax, t["hide"], color=PANEL, hovercolor=GRID)
        self.toggle.label.set_color(INK)
        self.toggle.label.set_fontsize(9)
        self.toggle.on_clicked(self._on_toggle)

    # --------------------------------------------------------------- callbacks
    def _on_slider(self, key, value):
        lo, hi, dec = self.specs[key]
        self._muted_box(key, f"{value:.{dec}f}")
        self.pose = replace(self.pose, **{key: float(value)})
        if not self._muted:
            self.refresh()

    def _muted_box(self, key, text):
        # Write the text directly: TextBox.set_val() forces a synchronous full redraw
        # of the figure, which made dragging a slider laggy.
        self.boxes[key].text_disp.set_text(text)

    def _on_submit(self, key, text):
        if self._muted:
            return
        lo, hi, dec = self.specs[key]
        try:
            v = min(max(float(text.replace(",", ".")), lo), hi)
        except ValueError:
            v = getattr(self.pose, key)
        self.sliders[key].set_val(v)
        self._muted_box(key, f"{v:.{dec}f}")

    def apply_preset(self, name: str):
        """Move the joint sliders to a progression (athlete mass/height are kept)."""
        self._muted = True
        for key, val in PRESETS[name].items():
            self.sliders[key].set_val(val)
        self._muted = False
        self.refresh()

    def set_pose(self, **kw):
        self._muted = True
        for key, val in kw.items():
            self.sliders[key].set_val(val)
        self._muted = False
        self.refresh()

    def _on_toggle(self, _event):
        self.overlays = not self.overlays
        self.toggle.label.set_text(self.t["hide"] if self.overlays else self.t["show"])
        self.refresh()

    # ----------------------------------------------------------------- drawing
    def refresh(self):
        r = solve(self.pose)
        self._draw_scene(r)
        self._draw_info(r)
        self.fig.canvas.draw_idle()

    def _draw_scene(self, r: Result):
        p, H, t = r.points, r.pose.height_m, self.t
        seg = lambda a, b: ([p[a][0], p[b][0]], [p[a][1], p[b][1]])
        self.arm.set_data(*seg("wrist", "shoulder"))
        self.trunk.set_data(*seg("shoulder", "hip"))
        self.thigh.set_data(*seg("hip", "knee"))
        self.shank.set_data(*seg("knee", "ankle"))
        self.foot.set_data(*seg("ankle", "toe"))
        self.hand.set_data([0, -LEN_FRAC["hand"] * H], [0, 0])
        self.head.set_center(p["head"])
        self.head.set_radius(0.06 * H)
        names = ["wrist", "shoulder", "hip", "knee", "ankle"]
        self.joints.set_data([p[n][0] for n in names], [p[n][1] for n in names])

        for a in self.overlay_artists:
            a.set_visible(self.overlays)
        self.info.set_visible(self.overlays)
        if not self.overlays:
            return

        cx, cy = r.cg_total
        self.cg_total_pt.set_data([cx], [cy])
        self.cg_body_pt.set_data([r.cg_body[0]], [r.cg_body[1]])
        self.cg_arms_pt.set_data([r.cg_arms[0]], [r.cg_arms[1]])
        self.cg_label.set_position((cx + 0.03, cy + 0.085))
        self.vline.set_data([0, 0], [0, cy])

        L = r.normal_force * FORCE_SCALE
        self.w_arrow.xy, self.w_arrow.xyann = (cx - 0.035, cy - L), (cx - 0.035, cy)
        self.n_arrow.xy, self.n_arrow.xyann = (0.035, L), (0.035, 0)
        self.f_label.set_text(f"{t['weight_v']} = {t['normal_v']} = {r.normal_force:.0f} N")

        # horizontal lever arm: shoulder -> body CG
        yd = max(p["shoulder"][1], p["hip"][1], p["head"][1]) + 0.20
        self.dim.xy, self.dim.xyann = (r.cg_body[0], yd), (p["shoulder"][0], yd)
        self.dim_label.set_position(((r.cg_body[0] + p["shoulder"][0]) / 2, yd + 0.02))
        self.dim_label.set_text(f"d = {r.d_cg:.2f} m")

        # torque the shoulder muscles apply to the trunk (counter-clockwise: it holds the legs up)
        sx, sy = p["shoulder"]
        rad = 0.07
        ang = np.radians(np.linspace(-70, 130, 40))
        self.arc.set_data(sx + rad * np.cos(ang), sy + rad * np.sin(ang))
        a_end, a_prev = math.radians(130), math.radians(120)
        self.arc_head.xy = (sx + rad * math.cos(a_end), sy + rad * math.sin(a_end))
        self.arc_head.xyann = (sx + rad * math.cos(a_prev), sy + rad * math.sin(a_prev))
        self.tau_label.set_position((sx - 0.15, sy + 0.13))
        self.tau_label.set_text(f"τ = {r.torque_per_shoulder:.0f} Nm")

    def _draw_info(self, r: Result):
        t = self.t
        self.big.set_text(f"{r.torque_per_shoulder:.0f} {t['units_nm']}")
        self.sub.set_text(f"{r.torque_total:.0f} {t['units_nm']} {t['both']}\nτ = m·g·d / 2")
        vals = [f"{r.lean_deg:.1f}°", f"{r.d_cg:.2f} m", f"{r.shoulder_height:.2f} m",
                f"{r.normal_force:.0f} N", f"{r.muscle_force_per_shoulder / 1000:.1f} kN",
                f"{r.torque_per_kg:.2f} Nm/kg", f"{100 * relative_to_full(r):.0f} %"]
        for txt, v in zip(self.rows, vals):
            txt.set_text(v)
        self.warn.set_text("\n".join(textwrap.fill(t[w], 46) for w in r.warnings))

    def show(self):
        plt.show()

    def save(self, path: str, dpi: int = 160):
        self.fig.savefig(path, dpi=dpi, facecolor=BG)
