"""Static biomechanical model of a straight-arm planche (side view).

Everything in this module is pure Python (no plotting), so it can be imported,
tested and reused on its own.

Coordinates
-----------
Sagittal plane, metres. The origin is the wrist (the support point), ``x`` points
towards the feet and ``y`` points up. The shoulders are therefore at negative ``x``
(ahead of the hands) and the body extends to positive ``x``.

Model in one paragraph
----------------------
The body is a chain of rigid segments (trunk, thigh, shank, foot) plus head and
arms, with segment masses and centres of mass from anthropometric tables. The
arms are straight and pivot about the wrist. In static equilibrium the common
centre of gravity (CG) of body + arms has to sit exactly above the wrist, which
fixes the lean of the arms. The net shoulder torque follows from the weight of
the body (without arms) acting at a horizontal distance ``d`` from the shoulder
joint: ``tau = m_body * g * d``. This torque is shared by two shoulders.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

G = 9.81  # m/s^2

# --- Anthropometry -----------------------------------------------------------
# Segment mass as a fraction of total body mass (Dempster, tabulated in Winter,
# "Biomechanics and Motor Control of Human Movement"). "arm" is upper arm +
# forearm + hand of ONE arm; thigh/shank/foot are for ONE leg.
MASS_FRAC = {"head": 0.081, "trunk": 0.497, "arm": 0.050,
             "thigh": 0.100, "shank": 0.0465, "foot": 0.0145}

# Segment length as a fraction of body height (Winter / Drillis & Contini).
LEN_FRAC = {"trunk": 0.288,      # shoulder joint -> hip joint
            "upper_arm": 0.186, "forearm": 0.146, "hand": 0.108,
            "thigh": 0.245, "shank": 0.246, "foot": 0.152}

# Centre of mass of each segment, as a fraction of its length from the proximal end.
COM_FRAC = {"trunk": 0.44, "thigh": 0.433, "shank": 0.433, "foot": 0.50}

# Head centre of mass ahead of the shoulder joint, as a fraction of body height.
HEAD_AHEAD = 0.0815


def _arm_com_fraction() -> float:
    """Centre of mass of a straight arm as a fraction of the shoulder-wrist distance.

    Combines upper arm (0.028 of body mass, CoM at 0.436), forearm (0.016, 0.430)
    and hand (0.006, 0.506), all in line.
    """
    ua, fa, hd = LEN_FRAC["upper_arm"], LEN_FRAC["forearm"], LEN_FRAC["hand"]
    parts = [(0.028, 0.436 * ua), (0.016, ua + 0.430 * fa), (0.006, ua + fa + 0.506 * hd)]
    com = sum(m * x for m, x in parts) / sum(m for m, _ in parts)
    return com / (ua + fa)


ARM_COM_FRAC = _arm_com_fraction()  # ~0.52

# Single-muscle model for the "equivalent muscle force" (illustrative, see README).
MUSCLE_INSERTION_FRAC = 0.43   # insertion distance from the joint, fraction of upper-arm length
MUSCLE_ANGLE_DEG = 25.0        # angle between line of action and humerus


# --- Input and output --------------------------------------------------------
@dataclass(frozen=True)
class Pose:
    """Athlete and body position. Angles in degrees."""
    weight_kg: float = 75.0
    height_m: float = 1.80
    straddle_deg: float = 0.0   # total opening angle between the legs (0 = legs together)
    hip_deg: float = 0.0        # hip flexion: legs rotate towards the floor (belly side)
    knee_deg: float = 0.0       # knee flexion: heels rotate towards the glutes (back side)
    tilt_deg: float = 0.0       # trunk inclination, hips above the shoulders = positive


# Illustrative joint angles for the usual progressions. They are a starting
# point, not measured data: match them to your own photos or video.
PRESETS: dict[str, dict[str, float]] = {
    "tuck":     dict(straddle_deg=0,  hip_deg=115, knee_deg=125, tilt_deg=15),
    "adv_tuck": dict(straddle_deg=0,  hip_deg=95,  knee_deg=110, tilt_deg=5),
    "straddle": dict(straddle_deg=90, hip_deg=0,   knee_deg=0,   tilt_deg=0),
    "full":     dict(straddle_deg=0,  hip_deg=0,   knee_deg=0,   tilt_deg=0),
}


@dataclass(frozen=True)
class Result:
    pose: Pose
    points: dict[str, tuple[float, float]]  # wrist, shoulder, hip, knee, ankle, toe, head
    cg_body: tuple[float, float]            # CG of the body without arms
    cg_arms: tuple[float, float]
    cg_total: tuple[float, float]
    d_cg: float                             # horizontal distance shoulder -> body CG (m)
    lean_deg: float                         # arm angle from the vertical
    shoulder_height: float                  # m
    mass_body: float                        # kg, without arms
    mass_arms: float                        # kg, both arms
    normal_force: float                     # N, total on both hands
    torque_total: float                     # N m, both shoulders
    torque_per_shoulder: float              # N m
    muscle_force_per_shoulder: float        # N, single-muscle equivalent
    warnings: tuple[str, ...]

    @property
    def feasible(self) -> bool:
        return not self.warnings

    @property
    def torque_per_kg(self) -> float:
        """Torque per shoulder per kg of body mass (N m / kg)."""
        return self.torque_per_shoulder / self.pose.weight_kg


def _add(p, q, k=1.0):
    return (p[0] + k * q[0], p[1] + k * q[1])


def solve(pose: Pose) -> Result:
    """Compute equilibrium lean, centres of mass and shoulder loading for ``pose``."""
    H, W = pose.height_m, pose.weight_kg
    L = {k: v * H for k, v in LEN_FRAC.items()}
    m = {k: v * W for k, v in MASS_FRAC.items()}
    l_arm = L["upper_arm"] + L["forearm"]

    psi = math.radians(pose.tilt_deg)
    hip_f, knee_f = math.radians(pose.hip_deg), math.radians(pose.knee_deg)
    cphi = math.cos(math.radians(pose.straddle_deg) / 2)  # side-view shortening from the straddle

    # --- body chain relative to the shoulder (x towards the feet, y up) ---
    t = (math.cos(psi), math.sin(psi))
    hip = (L["trunk"] * t[0], L["trunk"] * t[1])
    a1 = psi - hip_f                 # thigh direction, rotating towards the floor with hip flexion
    u1 = (math.cos(a1) * cphi, math.sin(a1))
    knee = _add(hip, u1, L["thigh"])
    a2 = a1 + knee_f                 # shank direction, rotating towards the back with knee flexion
    u2 = (math.cos(a2) * cphi, math.sin(a2))
    ankle = _add(knee, u2, L["shank"])
    toe = _add(ankle, u2, L["foot"])  # toes pointed: the foot continues the shank line
    head = (-HEAD_AHEAD * H * t[0], -HEAD_AHEAD * H * t[1])

    parts = [  # (mass, position) -- both legs coincide in the side view
        (m["head"], head),
        (m["trunk"], (COM_FRAC["trunk"] * hip[0], COM_FRAC["trunk"] * hip[1])),
        (2 * m["thigh"], _add(hip, u1, COM_FRAC["thigh"] * L["thigh"])),
        (2 * m["shank"], _add(knee, u2, COM_FRAC["shank"] * L["shank"])),
        (2 * m["foot"], _add(ankle, u2, COM_FRAC["foot"] * L["foot"])),
    ]
    m_body = sum(mi for mi, _ in parts)
    cg_rel = (sum(mi * p[0] for mi, p in parts) / m_body,
              sum(mi * p[1] for mi, p in parts) / m_body)
    d = cg_rel[0]
    m_arms = 2 * m["arm"]

    # --- lean: total CG above the wrist ---
    # x_wrist = 0, shoulder at -s, body CG at -s + d, arm CG at -(1 - c) s.
    warnings: list[str] = []
    s = m_body * d / (m_body + (1 - ARM_COM_FRAC) * m_arms)
    ratio = s / l_arm
    if abs(ratio) > 1:
        warnings.append("unreachable")
        ratio = math.copysign(1.0, ratio)
    theta = math.asin(ratio)
    s = l_arm * math.sin(theta)
    h = l_arm * math.cos(theta)
    shoulder = (-s, h)

    pts = {"wrist": (0.0, 0.0), "shoulder": shoulder,
           "hip": _add(shoulder, hip), "knee": _add(shoulder, knee),
           "ankle": _add(shoulder, ankle), "toe": _add(shoulder, toe),
           "head": _add(shoulder, head)}
    cg_body = _add(shoulder, cg_rel)
    cg_arms = (-(1 - ARM_COM_FRAC) * s, (1 - ARM_COM_FRAC) * h)
    M = m_body + m_arms
    cg_total = ((m_body * cg_body[0] + m_arms * cg_arms[0]) / M,
                (m_body * cg_body[1] + m_arms * cg_arms[1]) / M)

    if any(pts[k][1] < 0 for k in ("hip", "knee", "ankle", "toe")):
        warnings.append("below_floor")

    tau_total = m_body * G * d
    tau_sh = tau_total / 2
    r = MUSCLE_INSERTION_FRAC * L["upper_arm"] * math.sin(math.radians(MUSCLE_ANGLE_DEG))
    return Result(pose=pose, points=pts, cg_body=cg_body, cg_arms=cg_arms, cg_total=cg_total,
                  d_cg=d, lean_deg=math.degrees(theta), shoulder_height=h,
                  mass_body=m_body, mass_arms=m_arms, normal_force=W * G,
                  torque_total=tau_total, torque_per_shoulder=tau_sh,
                  muscle_force_per_shoulder=tau_sh / r, warnings=tuple(warnings))


def torque_from_lean(weight_kg: float, height_m: float, lean_deg: float) -> float:
    """Torque of both shoulders (N m) from the lean of the arms alone ("arm-bar" method).

    Free-body diagram of the arms only: the ground pushes up with the whole body
    weight at the wrist, and the arms' own weight acts at their centre of mass.
    Moments about the shoulder joint (the joint force has no moment there):

        tau = N * s - m_arms * g * c * s,     s = arm_length * sin(lean)

    No trunk or leg model is needed once the lean is known, for example measured on a
    photo. Inside ``solve`` the lean is itself computed from the body's centre of
    gravity, and both routes give the same torque (see the tests).
    """
    l_arm = (LEN_FRAC["upper_arm"] + LEN_FRAC["forearm"]) * height_m
    s = l_arm * math.sin(math.radians(lean_deg))
    m_arms = 2 * MASS_FRAC["arm"] * weight_kg
    return weight_kg * G * s - m_arms * G * ARM_COM_FRAC * s


def with_preset(pose: Pose, name: str) -> Pose:
    """Return ``pose`` with the joint angles of a named progression."""
    return replace(pose, **PRESETS[name])


def relative_to_full(res: Result) -> float:
    """Shoulder torque of ``res`` divided by the full planche of the same athlete."""
    full = solve(with_preset(res.pose, "full"))
    return res.torque_per_shoulder / full.torque_per_shoulder


def compare(pose: Pose | None = None) -> dict[str, Result]:
    """Solve every preset for one athlete."""
    base = pose or Pose()
    return {name: solve(with_preset(base, name)) for name in PRESETS}
