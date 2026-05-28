# XLeRobot Dual-Arm Teleoperation

Modular teleoperation framework for **two SO-101 follower arms** on an XLeRobot, operated by one or two SO-101 leader arms.  Runs entirely locally on an internook (or any Linux SBC).

---

## Hardware

| Arm | Role | Default Port |
|---|---|---|
| `leader_right` | Leader (always required) | `/dev/ttyACM3` |
| `leader_left` | Leader (optional) | *(set in config)* |
| `follower_right` | Follower | `/dev/ttyACM1` |
| `follower_left` | Follower | `/dev/ttyACM0` |

> **Note:** `/dev/ttyACM*` assignments can change on reboot.  
> For stable names see [Persistent USB port names](#persistent-usb-port-names) below.

---

## Installation

```bash
# 1. Clone / copy this repo
cd xlerobort_teleop

# 2. Install dependencies
pip install lerobot pyyaml

# 3. (optional) check that your arms are visible
ls /dev/ttyACM*
```

---

## Quick Start

```bash
# Default: right leader → right follower, uses default.yaml
python teleop.py

# Explicit mode flags
python teleop.py --mode dual          # Two leaders → each follower (needs dual_leader.yaml)
python teleop.py --mode single_right  # Right leader → BOTH followers (same pose)
python teleop.py --mode single_left   # Left leader  → BOTH followers
python teleop.py --mode mirror        # Right leader → right follower + mirrored left follower

# Custom config
python teleop.py --mode dual --config configs/dual_leader.yaml

# Dry run (no serial ports opened)
python teleop.py --dry-run

# Debug logging
python teleop.py --verbose

# Calibrate all arms
python teleop.py --mode calibrate
```

---

## Teleoperation Modes

### `dual` — Two leaders, two followers
Each leader independently drives its matching follower.

```
leader_right ──► follower_right
leader_left  ──► follower_left
```

Requires `leader_left` port to be set.  Use `configs/dual_leader.yaml`.

---

### `single_right` / `single_left` — One leader, both followers (parallel)
A single leader arm sends the **same joint angles** to both followers simultaneously.  Useful for symmetric lifting or when only one leader is available.

```
leader_right ──► follower_right
             └──► follower_left   (identical pose)
```

---

### `mirror` — One leader drives symmetric bimanual motion
The right leader drives the right follower normally.  The left follower receives a **laterally mirrored** version of the same pose — `shoulder_pan` and `wrist_roll` are reflected about the encoder midpoint.

```
leader_right ──► follower_right         (normal)
             └──► follower_left (mirrored: pan + roll flipped)
```

Great for tasks like opening boxes or placing objects symmetrically.

---

## Configuration

All settings live in YAML files under `configs/`.

```yaml
# configs/default.yaml
devices:
  leader_right:   /dev/ttyACM3
  leader_left:    ~              # null = not connected
  follower_right: /dev/ttyACM1
  follower_left:  /dev/ttyACM0

control:
  fps:      50        # control loop Hz
  baudrate: 1000000
```

Override any value by copying the file and passing `--config`.

---

## Calibration

Calibration uses lerobot's built-in arm calibration and saves results to `configs/calibration/<arm>.json`.

```bash
python teleop.py --mode calibrate
```

You will be prompted for each arm in order.  Follow the on-screen instructions to move each joint to its min/max range.

To skip an arm (e.g. left leader not attached), press Enter at the skip prompt.

---

## Adding a New Mode

1. Open `core/teleop_modes.py`
2. Subclass `BaseTeleopMode` and implement `step()`:

```python
class MyCustomMode(BaseTeleopMode):
    def step(self):
        pos = self._safe_read("leader_right")
        # transform pos however you like …
        self._safe_write("follower_right", pos)
        self._step_count += 1
```

3. Register it in `teleop.py`:

```python
mode_map = {
    …
    "my_mode": MyCustomMode,
}
```

4. Run it:

```bash
python teleop.py --mode my_mode
```

---

## Persistent USB Port Names

To avoid port reassignment on reboot, create udev rules:

```bash
# Find your device attributes
udevadm info -a -n /dev/ttyACM3 | grep -E "serial|idVendor|idProduct"

# Create /etc/udev/rules.d/99-xlerobort.rules:
SUBSYSTEM=="tty", ATTRS{serial}=="YOUR_SERIAL_HERE", SYMLINK+="ttyLEADER_RIGHT"
```

Then use `/dev/ttyLEADER_RIGHT` etc. in your config YAML.

---

## File Layout

```
xlerobort_teleop/
├── teleop.py                 # Entry point & CLI
├── core/
│   ├── device_manager.py     # Serial bus management (lerobot wrapper)
│   ├── teleop_modes.py       # All teleoperation modes
│   └── calibration.py        # lerobot calibration wizard
├── configs/
│   ├── default.yaml          # Default ports & control params
│   ├── dual_leader.yaml      # Config for dual-leader mode
│   └── calibration/          # Per-arm calibration JSON (auto-generated)
└── logs/
    └── teleop.log            # Runtime log
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied: /dev/ttyACM*` | `sudo usermod -aG dialout $USER` then re-login |
| `lerobot not found` | `pip install lerobot` |
| Arm jerks or overshoots | Lower `fps` in config (try 20–30) |
| Wrong arm moves | Swap port assignments in config YAML |
| Loop overrun warnings | Reduce `fps` or close other CPU-heavy processes |
