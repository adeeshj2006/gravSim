#!/usr/bin/env python3
"""
Generate a GIF of the multi-body simulation.
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
from PIL import Image

# Reuse the same classes from gravSim_v2.py to avoid duplication
import json
import sys
import itertools
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider

# ------------------------------------------------------------
# Configuration (same as gravSim_v2.py)
# ------------------------------------------------------------
CONFIG_FILE = Path(__file__).with_name("bodies.json")
G = 6.67430e-11          # gravitational constant (m³ kg⁻¹ s⁻²)
DEFAULT_DT = 60 * 60     # 1 hour in seconds (feel free to tweak)
TRAIL_LENGTH = 500       # max points to keep in the trail

# ------------------------------------------------------------
# Body definition
# ------------------------------------------------------------
class Body:
    """A point mass with position, velocity, mass and optional visuals."""
    _id_counter = itertools.count()

    def __init__(self, name, mass, pos, vel, ax, radius=5, color=None):
        self.id = next(self._id_counter)
        self.name = name
        self.mass = float(mass)
        self.pos = np.asarray(pos, dtype=float)      # shape (2,) or (3,)
        self.vel = np.asarray(vel, dtype=float)
        self.acc = np.zeros_like(self.pos)
        self.radius = radius
        self.color = color or f"C{self.id}"
        # Trail storage (fixed‑size ring buffer)
        self.maxlen = TRAIL_LENGTH
        self.trail_x = np.empty(self.maxlen)
        self.trail_y = np.empty(self.maxlen)
        self.trail_len = 0
        self.trail_idx = 0

        # Plotting objects
        self.artist, = ax.plot([], [], "o", markersize=radius,
                               color=self.color, label=self.name)
        self.trail_artist, = ax.plot([], [], "-", lw=1,
                                     alpha=0.5, color=self.color)

    # -----------------------------------------------------------------
    # Physics helpers
    # -----------------------------------------------------------------
    def compute_acceleration(self, bodies):
        """Newtonian gravity from all other bodies."""
        acc = np.zeros_like(self.pos)
        for b in bodies:
            if b is self:
                continue
            r_vec = b.pos - self.pos
            r = np.linalg.norm(r_vec)
            if r == 0:
                continue  # avoid division by zero (should not happen)
            acc += G * b.mass * r_vec / r**3
        self.acc = acc

    def leapfrog_step(self, bodies, dt):
        """Velocity‑Verlet: v ← v + a·dt/2; x ← x + v·dt; compute a; v ← v + a·dt/2"""
        # half‑kick
        self.vel += 0.5 * self.acc * dt
        # drift
        self.pos += self.vel * dt
        # (acceleration will be recomputed after all positions updated)

    # -----------------------------------------------------------------
    # Rendering helpers
    # -----------------------------------------------------------------
    def update_trail(self):
        """Append current position to the trail buffer."""
        self.trail_x[self.trail_idx] = self.pos[0]
        self.trail_y[self.trail_idx] = self.pos[1]
        self.trail_idx = (self.trail_idx + 1) % self.maxlen
        if self.trail_len < self.maxlen:
            self.trail_len += 1

    def draw(self, ax):
        """Update the matplotlib artists for this body."""
        self.artist.set_data([self.pos[0]], [self.pos[1]])
        # draw only the stored portion of the trail
        if self.trail_len > 0:
            idx = np.arange(self.trail_idx - self.trail_len,
                            self.trail_idx) % self.maxlen
            self.trail_artist.set_data(self.trail_x[idx], self.trail_y[idx])
        else:
            self.trail_artist.set_data([], [])

# ------------------------------------------------------------
# System & integration
# ------------------------------------------------------------
class System:
    def __init__(self, bodies, ax):
        self.bodies = bodies
        self.ax = ax
        self.time = 0.0

        # Energy monitoring (optional)
        self.times = []
        self.energies = []

        # Center‑of‑mass marker (for 2D)
        self.com_artist, = ax.plot([], [], "rx", markersize=8,
                                   label="Center of Mass")

    def compute_all_accelerations(self):
        for b in self.bodies:
            b.compute_acceleration(self.bodies)

    def step(self, dt):
        """Leapfrog step: kick‑drift‑kick."""
        # Kick half‑step
        for b in self.bodies:
            b.vel += 0.5 * b.acc * dt
        # Drift
        for b in self.bodies:
            b.pos += b.vel * dt
        # Re‑compute accelerations with new positions
        self.compute_all_accelerations()
        # Kick half‑step
        for b in self.bodies:
            b.vel += 0.5 * b.acc * dt
        self.time += dt

    def update_com(self):
        total_mass = sum(b.mass for b in self.bodies)
        if total_mass == 0:
            com = np.zeros_like(self.bodies[0].pos)
        else:
            com = sum(b.mass * b.pos for b in self.bodies) / total_mass
        self.com_artist.set_data([com[0]], [com[1]])

# ------------------------------------------------------------
# Load bodies from JSON
# ------------------------------------------------------------
def load_bodies_from_file(path, ax):
    """Expected JSON format:
    [
        {"name": "Sun",   "mass": 1.989e30, "pos": [0,0], "vel": [0,0], "radius": 12, "color": "#fdbb84"},
        {"name": "Earth", "mass": 5.972e24, "pos": [1.496e11,0], "vel": [0,29780], "radius": 6, "color": "#4a90e2"},
        ...
    ]
    """
    with open(path, "r") as f:
        data = json.load(f)
    bodies = []
    for spec in data:
        bodies.append(Body(
            name=spec["name"],
            mass=spec["mass"],
            pos=spec["pos"],
            vel=spec["vel"],
            ax=ax,
            radius=spec.get("radius", 5),
            color=spec.get("color")
        ))
    return bodies

# ------------------------------------------------------------
# Main GIF generation
# ------------------------------------------------------------
def main():
    print("Generating GIF of multi-body simulation...")
    # Set up the figure and axes
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_aspect('equal')
    ax.set_xlabel('x (m)')
    ax.set_ylabel('y (m)')
    ax.set_title('Gravitational N‑Body Simulation (Leapfrog)')

    # Load bodies
    bodies = load_bodies_from_file(CONFIG_FILE, ax)
    system = System(bodies, ax)

    # Set fixed axis limits to encompass all orbits with some padding
    max_dist = max(np.linalg.norm(b.pos) for b in bodies)
    padding = 1.2
    limit = max_dist * padding
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)

    # Initial draw
    for b in bodies:
        b.draw(ax)
    system.update_com()
    ax.legend(loc='upper right')

    # Prepare to capture frames
    frames = []
    n_frames = 150  # number of frames for GIF
    dt = DEFAULT_DT  # seconds per integration step

    for i in range(n_frames):
        # Render current frame to an image
        fig.canvas.draw()
        # Convert canvas to RGB image
        img = np.frombuffer(fig.canvas.tostring_rgb(), dtype='uint8')
        w, h = fig.canvas.get_width_height()
        img = img.reshape((h, w, 3))
        frames.append(Image.fromarray(img))

        # Advance simulation
        system.step(dt)
        for b in bodies:
            b.update_trail()
            b.draw(ax)
        system.update_com()

    # Save as GIF
    output_dir = Path(__file__).parent / "gifs"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "multibody.gif"
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=200,  # ms per frame (5 fps)
        loop=0
    )
    print(f"GIF saved to {output_path}")

if __name__ == "__main__":
    from PIL import Image
    main()
