import signal
import sys

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

fig, ax = plt.subplots()
ax.set_aspect('equal')

G = 6.674e-11

class Body():
    id = 0
    def __init__(self, name, mass, posns, vels, ax, ax_marker, radius=5):
        self.id = Body.id
        self.name = name
        Body.id += 1
        self.mass = mass
        self.posns = np.array(posns, dtype=float)
        self.vels = np.array(vels, dtype=float)
        self.acc = np.zeros(2)
        self.radius = radius
        self.time_step = 0.1

        # Marker for the body itself
        self.artist, = ax.plot([self.posns[0]], [self.posns[1]], marker=ax_marker, 
                               markersize=radius, label=self.name)
        # Line for the trail
        self.trail, = ax.plot([], [], lw=1, alpha=0.6)

        # Store history of positions (in local coords)
        self.xdata, self.ydata = [], []

    def calculateAccDueToGrav(self, bodies):
        self.acc = np.zeros(2)
        for body in bodies:
            if body.id == self.id:
                continue

            r_vec = body.posns - self.posns
            r = np.linalg.norm(r_vec)
            acc_mag = G * body.mass / (r**2)
            r_hat = r_vec / r
            self.acc += acc_mag * r_hat

    def updateVel(self):
        self.vels += self.acc * self.time_step

    def updatePosn(self):
        self.posns += self.vels * self.time_step

    def render(self, reference=None):
        # Relative position
        if reference is not None:
            rel_x = self.posns[0] - reference.posns[0]
            rel_y = self.posns[1] - reference.posns[1]
        else:
            rel_x = self.posns[0]
            rel_y = self.posns[1]

        # Update marker
        self.artist.set_data([rel_x], [rel_y])

        # Update trail
        self.xdata.append(rel_x)
        self.ydata.append(rel_y)
        self.trail.set_data(self.xdata, self.ydata)

    def run(self, bodies):
        self.calculateAccDueToGrav(bodies=bodies)
        self.updateVel()
        self.updatePosn()

def update(frame):
    focus = Earth   # focus body

    # Physics updates
    for body in bodies:
        body.run(bodies)

    # Rendering updates (relative to focus)
    for body in bodies:
        body.render(reference=focus)

    # Compute center of mass relative to focus
    total_mass = sum(b.mass for b in bodies)
    com = sum(b.mass * b.posns for b in bodies) / total_mass
    com_artist.set_data([com[0] - focus.posns[0]], [com[1] - focus.posns[1]])

    # Re-center the axes
    view_range = 100
    ax.set_xlim(-view_range, view_range)
    ax.set_ylim(-view_range, view_range)

    return [body.artist for body in bodies] + [body.trail for body in bodies] + [com_artist]

# For clean exit upon Keyboard Exception
def handle_signal(sig, frame):
    print("KeyboardInterrupt: Exiting")
    plt.close('all')
    print("Matlab window closed")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)

# Create planets
Sun   = Body("Sun",   3.0e13, [0.0, 0.0], [0.0, -0.06465792296], ax, 'o', radius=8)
Earth = Body("Earth", 3.0e11, [50.0, 0.0], [0.0,  6.3595943267], ax, 'o', radius=5)
Moon  = Body("Moon",  3.7e9,  [54.0, 0.0], [0.0,  8.6106461919], ax, 'o', radius=3)
bodies = [Sun, Earth, Moon]

# Center of mass marker (relative coords)
com_artist, = ax.plot([], [], 'rx', markersize=8, label="Center of Mass")

ani = FuncAnimation(fig, update, frames=200, interval=10, blit=False)
plt.legend()
plt.show()