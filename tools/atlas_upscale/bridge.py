#!/usr/bin/env python3
"""Command line for the Atlas Upscale game bridge (HTTP on 127.0.0.1, see Bridge.cs).

  bridge.py ping | state
  bridge.py shot NAME [--label] [--doll]     writes a PNG, prints the Linux path
  bridge.py set NAME                         switch texture set and wait for the rebuild
  bridge.py sets                             list sets
  bridge.py dump                             F9 atlas dump, prints the files
  bridge.py zoom min|max|reset|0..1 | pan X Y | pan --reset
  bridge.py aa off|smaa|taa | aa            set or read anti-aliasing
  bridge.py ui [FILTER] | click TEXT_OR_PATH [INDEX]   list or click active buttons
  bridge.py timescale [0..4]                 freeze (0) or resume (1) game time
  bridge.py loading                          prints yes while the loading screen waits for a key
  bridge.py wait FRAMES
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

PORT = 8951
PREFIX_WIN = "C:\\users\\steamuser\\"
PREFIX_LINUX = "/mnt/games/SteamLibrary/steamapps/compatdata/2186680/pfx/drive_c/users/steamuser/"
TIMEOUT = 200


def call(command, **args):
    query = urllib.parse.urlencode({k: v for k, v in args.items() if v is not None})
    url = f"http://127.0.0.1:{PORT}/{command}" + (f"?{query}" if query else "")
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as reply:
            data = json.loads(reply.read())
    except urllib.error.URLError as error:
        sys.exit(f"bridge not reachable at {url}: {error.reason}. Is the game running with the AtlasUpscale mod?")
    except urllib.error.HTTPError as error:
        data = json.loads(error.read())
    return data


def to_linux(path):
    path = path.replace("/", "\\")
    if path.lower().startswith(PREFIX_WIN.lower()):
        return PREFIX_LINUX + path[len(PREFIX_WIN):].replace("\\", "/")
    return path.replace("\\", "/")


LOADING_REGION = (3050, 1750, 3500, 2100)  # the green "Press any key" dial on the loading screen, 3840x2160
LOADING_PIXELS = 500


def is_loading_screen():
    """True while the loading screen with its green 'Press any key' dial is up (counts bright green pixels in that corner)."""
    from PIL import Image
    import numpy as np
    reply = call("shot", name="_loading_probe")
    image = np.asarray(Image.open(to_linux(reply["path"])).convert("RGB"), dtype=np.int16)
    x0, y0, x1, y1 = LOADING_REGION
    region = image[y0:y1, x0:x1]
    mask = (region[..., 1] > 150) & (region[..., 0] < 110) & (region[..., 2] < 130)
    return int(mask.sum()) > LOADING_PIXELS


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command")
    parser.add_argument("rest", nargs="*")
    parser.add_argument("--label", action="store_true")
    parser.add_argument("--doll", action="store_true")
    parser.add_argument("--reset", action="store_true")
    options = parser.parse_args()
    cmd, rest = options.command, options.rest

    if cmd in ("ping", "state"):
        reply = call(cmd)
    elif cmd == "shot":
        reply = call("shot", name=rest[0] if rest else "shot", label=int(options.label), doll=int(options.doll))
    elif cmd == "set":
        reply = call("texture_set", name=rest[0])
    elif cmd == "sets":
        reply = call("texture_set")
    elif cmd == "dump":
        reply = call("dump_atlas")
    elif cmd == "zoom":
        reply = call("zoom", mode=None if rest and rest[0].replace(".", "").isdigit() else (rest[0] if rest else None),
                     value=rest[0] if rest and rest[0].replace(".", "").isdigit() else None)
    elif cmd == "pan":
        reply = call("pan", reset=1 if options.reset else None, x=rest[0] if rest else None, y=rest[1] if len(rest) > 1 else None)
    elif cmd == "aa":
        reply = call("aa", mode=rest[0] if rest else None)
    elif cmd == "ui":
        reply = call("ui_list", filter=rest[0] if rest else None)
    elif cmd == "click":
        reply = call("ui_click", match=rest[0], index=rest[1] if len(rest) > 1 else None)
    elif cmd == "loading":
        print("yes" if is_loading_screen() else "no")
        sys.exit(0)
    elif cmd == "timescale":
        reply = call("timescale", value=rest[0] if rest else None)
    elif cmd == "wait":
        reply = call("wait", frames=rest[0])
    else:
        sys.exit(f"unknown command {cmd}\n{__doc__}")

    if reply.get("items"):
        print(reply.pop("items"))
    if reply.get("path"):
        reply["linuxPath"] = to_linux(reply["path"])
    if reply.get("files"):
        reply["linuxFiles"] = [to_linux(p) for p in reply["files"].split("|") if p]
    print(json.dumps(reply, indent=2))
    sys.exit(0 if reply.get("ok") else 1)


if __name__ == "__main__":
    main()
