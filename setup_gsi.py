import os
import shutil
import sys

GSI_FILENAME = "gamestate_integration_coach.cfg"

STEAM_PATHS = [
    os.path.expandvars(r"%ProgramFiles(x86)%\Steam"),
    os.path.expandvars(r"%ProgramFiles%\Steam"),
    r"C:\Steam",
    r"D:\Steam",
    r"D:\SteamLibrary",
]

CS2_CSGO_RELATIVE = os.path.join(
    "steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo"
)


def find_cs2_csgo_dir() -> str | None:
    if sys.platform != "win32":
        return None

    for steam_path in STEAM_PATHS:
        csgo_dir = os.path.join(steam_path, CS2_CSGO_RELATIVE)
        if os.path.isdir(csgo_dir):
            return csgo_dir

    libraryfolders = os.path.join(STEAM_PATHS[0], "steamapps", "libraryfolders.vdf")
    if os.path.isfile(libraryfolders):
        try:
            with open(libraryfolders) as f:
                for line in f:
                    line = line.strip()
                    if '"path"' in line:
                        path = line.split('"')[3]
                        csgo_dir = os.path.join(path, CS2_CSGO_RELATIVE)
                        if os.path.isdir(csgo_dir):
                            return csgo_dir
        except (IndexError, OSError):
            pass

    return None


def find_cs2_cfg_dir() -> str | None:
    csgo_dir = find_cs2_csgo_dir()
    if csgo_dir:
        cfg_dir = os.path.join(csgo_dir, "cfg")
        if os.path.isdir(cfg_dir):
            return cfg_dir
    return None


def install_gsi_config() -> bool:
    cfg_dir = find_cs2_cfg_dir()
    if not cfg_dir:
        print("Could not find CS2 cfg directory.", flush=True)
        print(f"Manually copy {GSI_FILENAME} to your CS2 cfg/ folder.", flush=True)
        return False

    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(__file__)
    src = os.path.join(base, GSI_FILENAME)
    dst = os.path.join(cfg_dir, GSI_FILENAME)

    if os.path.isfile(dst):
        try:
            with open(src, "rb") as f:
                src_content = f.read()
            with open(dst, "rb") as f:
                dst_content = f.read()
            if src_content == dst_content:
                return True
        except OSError:
            pass

    try:
        shutil.copy2(src, dst)
        print(f"Installed GSI config to {dst}", flush=True)
        return True
    except OSError as e:
        print(f"Failed to install GSI config: {e}", flush=True)
        return False
