#!/bin/bash
# Install a freshly built AtlasUpscale.dll (optional arg), restart Rogue Trader and press Enter past the input prompt
# until the bridge sees clickable UI. Usage: restart_game.sh [path/to/AtlasUpscale.dll]
HERE="$(cd "$(dirname "$0")" && pwd)"
MOD="/mnt/games/SteamLibrary/steamapps/compatdata/2186680/pfx/drive_c/users/steamuser/AppData/LocalLow/Owlcat Games/Warhammer 40000 Rogue Trader/UnityModManager/AtlasUpscale"
pkill -f "[W]H40KRT.exe"
for i in $(seq 1 20); do pgrep -f "[W]H40KRT.exe" >/dev/null || break; sleep 1; done
[ -n "$1" ] && cp "$1" "$MOD/AtlasUpscale.dll"
(setsid nohup steam steam://rungameid/2186680 >/dev/null 2>&1 &)
for i in $(seq 1 60); do sleep 3; python3 "$HERE/bridge.py" ping >/dev/null 2>&1 && break; done
WIN=""
for i in $(seq 1 40); do
  WIN=$(xdotool search --name "^Warhammer 40000 Rogue Trader$" | head -1)
  [ -n "$WIN" ] && break; sleep 2
done
for i in $(seq 1 40); do
  sleep 4
  count=$(python3 "$HERE/bridge.py" ui 2>/dev/null | grep -o '"count": [0-9]*' | grep -o '[0-9]*$')
  [ -n "$count" ] && [ "$count" -gt 0 ] && { echo "main menu ready ($count clickables)"; exit 0; }
  [ -n "$WIN" ] && { xdotool windowactivate --sync "$WIN"; xdotool key Return; }
done
echo "gave up waiting for the menu"; exit 1
