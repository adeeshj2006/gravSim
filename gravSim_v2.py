#!/usr/bin/env python3
"""
gravSim_v2.py – Enhanced N‑body gravitational simulation

Features:
  • Arbitrary number of bodies loaded from JSON
  • Velocity‑Verlet (leapfrog) integrator
  • Real‑time energy (KE+PE) monitoring
  • Optional trailing trails
  • Simple keyboard controls (space = pause, '+'/'-' = speed)
Author:  (your name)
License: CC0 1.0 Universal
"""

import json
import sys
import itertools
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider

# ------------------------------------------------------------
# Configuration
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

        # Energy monitoring
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

    def compute_energy(self):
        """Returns (KE, PE, total)."""
        ke = 0.0
        pe = 0.0
        for i, b in enumerate(self.bodies):
            ke += 0.5 * b.mass * np.dot(b.vel, b.vel)
            for j in range(i + 1, len(self.bodies)):
                bj = self.bodies[j]
                r = np.linalg.norm(b.pos - bj.pos)
                pe -= G * b.mass * bj.mass / r
        return ke, pe, ke + pe

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
# Main animation setup
# ------------------------------------------------------------
def main():
    print("Starting gravSim v2 – close the window to quit.")
    # Set up the figure and axes
    fig, ax = plt.subplots(figsize=(8, 8))
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

    # Animation parameters
    dt = DEFAULT_DT  # seconds per frame
    paused = False
    speed_factor = 1.0  # multiplier for dt

    # -----------------------------------------------------------------
    # Animation update function
    # -----------------------------------------------------------------
    def update(frame):
        nonlocal dt, paused, speed_factor
        if not paused:
            # Perform multiple internal steps if sped up
            for _ in range(int(speed_factor)):
                system.step(dt)
            # Update visuals
            for b in bodies:
                b.update_trail()
                b.draw(ax)
            system.update_com()
            # Energy bookkeeping
            ke, pe, te = system.compute_energy()
            system.times.append(system.time)
            system.energies.append(te)
        # Return artists for blitting (we are not using blit for simplicity)
        artists = [b.artist for b in bodies] + [b.trail_artist for b in bodies] + [system.com_artist]
        return artists

    ani = FuncAnimation(fig, update, interval=30, blit=False)

    # -----------------------------------------------------------------
    # Interactive widgets
    # -----------------------------------------------------------------
    # Pause button
    ax_button = plt.axes([0.81, 0.02, 0.1, 0.04])
    btn_pause = Button(ax_button, 'Pause', hovercolor='0.975')
    def toggle_pause(event):
        nonlocal paused
        paused = not paused
        btn_pause.label.set_text('Resume' if paused else 'Pause')
    btn_pause.on_clicked(toggle_pause)

    # Speed slider
    ax_slider = plt.axes([0.2, 0.02, 0.5, 0.03])
    slider = Slider(ax_slider, 'Speed', 0.1, 5.0, valinit=1.0)
    def update_speed(val):
        nonlocal speed_factor
        speed_factor = val
    slider.on_changed(update_speed)

    # Legend
    ax.legend(loc='upper right')

    plt.show()


if __name__ == "__main__":
    # Ensure the JSON file exists
    if not CONFIG_FILE.is_file():
        print(f"Error: {CONFIG_FILE} not found.", file=sys.stderr)
        sys.exit(1)
    main()
