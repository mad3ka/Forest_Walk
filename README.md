# Forest Walk

A first-person 3D exploration game written in Python with the [Ursina](https://www.ursinaengine.org/) engine.
You walk through a low-poly forest, collect coins, drive cars along winding roads, and spend coins in a
garage on new vehicles and tuning.

## Features

- **First-person 3D world**: a 300 × 300 m forest with hills, lakes, rocks, grass, flowers, clouds and smooth roads.
- **400 coins**: chains of coins along the roads (handy by car) and loose coins in the forest (on foot).
  A collected coin comes back after 3 minutes of play, so you can keep earning.
- **Driving**: enter and leave the car, drive from the driver's seat or a chase camera.
  Cars are faster on asphalt than on grass, the wheels spin and steer, and the steering wheel turns.
- **Garage and shop**: buy five vehicles and tune each one separately.
- **Menus**: main menu, three save slots, settings, and a pause menu.
- **Settings**: language (Russian / English), mouse sensitivity, invert mouse Y, and rebinding every key.
- **Saving**: progress is saved when you pause, exit to the menu, close the window, and every minute.

## Requirements

- Python 3.9 or newer
- macOS is the tested platform. The UI uses the system Arial font for Cyrillic text
  (`/System/Library/Fonts/Supplemental/Arial.ttf`). On other systems Ursina's default font is used,
  which has no Cyrillic, so the Russian interface may not display correctly.

## Installation

```bash
python3 -m pip install -r requirements.txt
```

This installs Ursina 5.2.0 (the last version that supports Python 3.9) together with Panda3D, and `screeninfo`,
which Ursina needs on macOS.

## Running

```bash
python3 main.py
```

On first launch the game generates its coin sound into `sounds/coin.wav`.

### Admin mode (for testing)

```bash
python3 main.py --admin
```

An **Admin mode** button appears on the save-slot screen. It opens a separate save (`saves/slot_admin.json`)
with unlimited coins, so you can try every car and tuning option. Normal save slots are not affected.
The button only appears when the game is started with `--admin`.

## Building a macOS app

macOS does not run `.exe` files; the equivalent is an application bundle (`Forest Walk.app`).
It is built with [PyInstaller](https://pyinstaller.org/) from `forest_walk.spec`:

```bash
python3 -m pip install --user pyinstaller
python3 -m PyInstaller --noconfirm --clean forest_walk.spec
```

The result is `dist/Forest Walk.app` (about 200 MB, because it contains Python, Ursina and Panda3D).
Double-click it to play; no Python installation is needed on the target Mac.

- The app is built for the processor of the Mac that builds it (Apple Silicon on an M-series Mac).
  An Intel Mac needs its own build.
- The packaged game stores saves and settings in `~/Library/Application Support/Forest Walk/`
  instead of the project folder, because the app bundle is read-only.
- The app is not notarized. On another Mac, Gatekeeper may refuse to open it the first time;
  right-click the app, choose **Open**, and confirm, or run `xattr -dr com.apple.quarantine "Forest Walk.app"`.
- Admin mode still works: `open "dist/Forest Walk.app" --args --admin`.

## Controls

Default keys. All of them except Esc can be rebound in **Settings → Controls**.

| Action | Key |
|---|---|
| Move / drive | W A S D |
| Look around | Mouse |
| Run | Left Shift |
| Jump (on foot) / handbrake (in a car) | Space |
| Get in / out of the car, open the garage | E |
| Switch car camera (driver's seat / behind the car) | V |
| Pause menu | Esc |

You can only get out of a car once it has almost stopped.

## Gameplay

### Coins

The top-left panel shows two numbers:

- **Coins**: your wallet, which you spend in the garage.
- **Collected N/400**: how many coins you have picked up in total. Reaching 400 shows the victory screen,
  after which you can keep playing.

The minimap in the top-right corner shows coins (yellow), your car (red), you (white arrow)
and the garage (red square).

### Garage

The garage is next to the starting point, east of the road. Walk up to its doors and press **E**.
Your car is delivered to the pad in front of the garage, and the shop opens on the right.

| Vehicle | Price | Top speed | Off-road | Notes |
|---|---|---|---|---|
| Sedan | owned from the start | 79 km/h | 39 km/h | smooth fastback sedan |
| Crossover | 40 | 75 km/h | 50 km/h | roof rails, rear spoiler, plastic cladding |
| Off-roader | 60 | 68 km/h | 61 km/h | round headlights, spare wheel, roof rack |
| Pickup | 80 | 72 km/h | 50 km/h | open cargo bed, chrome grille and bumpers |
| Semi truck | 150 | 64 km/h | 28 km/h | tractor with an articulated trailer |

### Tuning

Tuning is stored per vehicle:

- **Paint**: 10 colours, 5 coins each.
- **Rims**: silver, black or gold, 8 coins each.
- **Engine**: 3 levels for 20, 35 and 50 coins. Each level adds 12 % top speed and 20 % acceleration.

## Saves and settings

- `saves/slot_1.json` … `saves/slot_3.json`: save slots (coins, garage, car and player position, play time).
- `saves/slot_admin.json`: the admin-mode save.
- `settings.json`: language, mouse settings and key bindings.

Delete these files to reset progress or settings.

## Project structure

| File | Contents |
|---|---|
| `main.py` | Entry point: game loop, player and car control, HUD, menus, garage shop, save handling |
| `world.py` | World data: roads, lakes, trees, rocks, coin placement, ground height and collisions |
| `models.py` | Low-poly mesh builder, terrain, roads, trees, garage building, minimap image |
| `car_model.py` | Vehicle specifications and generation of all five vehicles, wheels, interiors and trailer |
| `i18n.py` | Russian and English UI text |
| `storage.py` | Reading and writing settings and save slots |
| `game_2d.py` | The original top-down 2D version (pygame), kept for reference |

The world and vehicles are generated in code. The game ships with no model or texture files.
Lighting is baked into vertex colours, so no shaders are needed.

## Tweaking

- Number of coins: `COIN_COUNT` in `world.py`
- Coin respawn time and tuning prices: `RESPAWN`, `PAINT_PRICE`, `RIM_PRICE`, `ENGINE_PRICES` in `main.py`
- Vehicle prices, speeds and handling: the `price` and `phys` entries in `SPECS` in `car_model.py`

## Known limitations

- The semi truck's trailer does not collide with trees, so it can pass through them off-road.
- Only tested on macOS.
