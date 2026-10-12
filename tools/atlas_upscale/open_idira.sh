#!/bin/bash
# From the main menu: Continue, wait for the load, open the inventory, select Idira. Needs the game running with the bridge.
B="python3 $(cd "$(dirname "$0")" && pwd)/bridge.py"
$B click "ButtonsPanel/Continue" >/dev/null
for i in $(seq 1 60); do
  sleep 4
  $B ui "InventoryButton" 2>/dev/null | grep -q "InventoryButton" && break
done
sleep 3
# the loading screen waits for "Press any key" and the HUD buttons already exist behind it: press a key only while it is up
WIN=$(xdotool search --name "^Warhammer 40000 Rogue Trader$" | head -1)
for i in $(seq 1 60); do
  [ "$($B loading)" = "yes" ] || break
  [ -n "$WIN" ] && { xdotool windowfocus "$WIN"; sleep 1; xdotool mousemove 1900 1000; xdotool key space; }
  sleep 4
done
sleep 3
$B click "BackgroundContainer/InventoryButton" >/dev/null
sleep 4
$B click "PartyCharacterPCView (5)" >/dev/null
sleep 3
echo "inventory open on the 6th party member (Idira in the current party)"
