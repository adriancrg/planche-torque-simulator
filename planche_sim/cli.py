"""Command line entry point: ``python -m planche_sim``."""
from __future__ import annotations

import argparse
from dataclasses import replace

from .model import PRESETS, Pose, compare, relative_to_full, solve, with_preset


def _pose_from(args) -> Pose:
    pose = Pose(weight_kg=args.weight, height_m=args.height)
    if args.preset:
        pose = with_preset(pose, args.preset)
    overrides = {k: v for k, v in dict(straddle_deg=args.straddle, hip_deg=args.hip, knee_deg=args.knee,
                                       tilt_deg=args.tilt).items() if v is not None}
    return replace(pose, **overrides)


def print_table(results) -> None:
    print(f"{'position':<10}{'lean':>8}{'d (m)':>8}{'tau/shoulder':>14}{'Nm/kg':>8}{'vs full':>9}")
    for name, r in results.items():
        flag = "  !" + ",".join(r.warnings) if r.warnings else ""
        print(f"{name:<10}{r.lean_deg:>7.1f}°{r.d_cg:>8.2f}{r.torque_per_shoulder:>12.0f} Nm"
              f"{r.torque_per_kg:>8.2f}{100 * relative_to_full(r):>8.0f}%{flag}")


def progression_chart(results, path: str, pose: Pose) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .app import BG, GRID, INK, MUTED, TRUNK

    names = list(results)
    pretty = {"tuck": "Tuck", "adv_tuck": "Advanced tuck", "straddle": "Straddle", "full": "Full"}
    vals = [results[n].torque_per_shoulder for n in names]
    fig, ax = plt.subplots(figsize=(7.5, 4.2), facecolor=BG)
    ax.set_facecolor(BG)
    bars = ax.bar([pretty[n] for n in names], vals, width=0.5, color=TRUNK)
    for b, n, v in zip(bars, names, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 3, f"{v:.0f} Nm\n{100 * relative_to_full(results[n]):.0f} %",
                ha="center", va="bottom", color=INK, fontsize=10)
    ax.set_ylim(0, max(vals) * 1.25)
    ax.set_ylabel("Torque per shoulder (Nm)", color=MUTED)
    ax.set_title(f"Planche progressions: {pose.weight_kg:g} kg, {pose.height_m:.2f} m", loc="left",
                 color=INK, fontweight="bold")
    ax.tick_params(colors=MUTED, length=0)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(MUTED)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor=BG)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="planche_sim", description="Planche torque simulator.")
    ap.add_argument("--weight", type=float, default=75.0, help="body mass in kg (default 75)")
    ap.add_argument("--height", type=float, default=1.80, help="height in m (default 1.80)")
    ap.add_argument("--preset", choices=sorted(PRESETS), help="start from a progression")
    ap.add_argument("--straddle", type=float, help="total leg opening angle (deg)")
    ap.add_argument("--hip", type=float, help="hip flexion (deg)")
    ap.add_argument("--knee", type=float, help="knee flexion (deg)")
    ap.add_argument("--tilt", type=float, help="trunk tilt, hips up = positive (deg)")
    ap.add_argument("--lang", choices=["en", "es"], default="en")
    ap.add_argument("--save", metavar="PNG", help="render the viewer to a PNG and exit (no window)")
    sub = ap.add_subparsers(dest="cmd")
    cmp_ = sub.add_parser("compare", help="print a table of all progressions")
    cmp_.add_argument("--plot", metavar="PNG", help="also save a bar chart")
    args = ap.parse_args(argv)

    pose = _pose_from(args)
    if args.cmd == "compare":
        base = Pose(weight_kg=args.weight, height_m=args.height)
        results = compare(base)
        print_table(results)
        if args.plot:
            progression_chart(results, args.plot, base)
            print(f"chart saved to {args.plot}")
        return 0

    if args.save:
        import matplotlib
        matplotlib.use("Agg")
    from .app import PlancheApp
    app = PlancheApp(pose, lang=args.lang)
    if args.save:
        app.save(args.save)
        print(f"saved {args.save}")
    else:
        app.show()
    return 0
