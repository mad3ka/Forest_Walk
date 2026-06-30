import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _data_dir():
    if getattr(sys, 'frozen', False):
        return Path.home() / 'Library' / 'Application Support' / 'Forest Walk'
    return BASE


DATA_DIR = _data_dir()
SAVE_DIR = DATA_DIR / 'saves'
SETTINGS_FILE = DATA_DIR / 'settings.json'
SLOTS = 3

ACTIONS = ['forward', 'back', 'left', 'right', 'run', 'jump', 'interact', 'camera']
DEFAULT_KEYS = {
    'forward': 'w', 'back': 's', 'left': 'a', 'right': 'd',
    'run': 'left shift', 'jump': 'space', 'interact': 'e', 'camera': 'v',
}


def default_settings():
    return {'language': 'ru', 'sensitivity': 1.0, 'invert_y': False, 'keys': dict(DEFAULT_KEYS)}


def _read_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_settings():
    settings = default_settings()
    data = _read_json(SETTINGS_FILE)
    if isinstance(data, dict):
        keys = data.pop('keys', {})
        settings.update({k: v for k, v in data.items() if k in settings})
        if isinstance(keys, dict):
            settings['keys'].update({a: k for a, k in keys.items() if a in DEFAULT_KEYS and isinstance(k, str)})
    return settings


def save_settings(settings):
    _write_json(SETTINGS_FILE, settings)


def slot_path(n):
    return SAVE_DIR / f'slot_{n}.json'


def load_slot(n):
    data = _read_json(slot_path(n))
    return data if isinstance(data, dict) else None


def write_slot(n, data):
    data = dict(data, saved_at=time.strftime('%d.%m.%Y %H:%M'))
    _write_json(slot_path(n), data)


def delete_slot(n):
    try:
        slot_path(n).unlink()
    except FileNotFoundError:
        pass
