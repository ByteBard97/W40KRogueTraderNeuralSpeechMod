# MacBook Pro M4 as a render node

What the MacBook needs so Claude can use it as a third render worker next to the 5080 and the Windows 4070.

## How the rendering works (why the Mac needs little)

Workers pull. `tools/render_corpus/queue_server.py` runs on the Linux box (port 8946 for the current `extra` run).
`tools/render_corpus/worker.py` on each render machine leases jobs over HTTP, fetches reference clips from the server,
renders with VoxCPM2, optionally checks the take with Whisper, and uploads the WAV and a manifest row.

So the Mac does not need to expose a render port. It needs to make **outbound** HTTP requests to the Linux box, and
it needs to accept **SSH** so Claude can sync the code, start and stop the worker, and read logs.

## Required

1. **SSH from the Linux box, key auth, no password prompts.**
   - Remote Login on (System Settings > General > Sharing).
   - The Linux box's public key (`~/.ssh/id_*.pub` for user `geoff`) in `~/.ssh/authorized_keys` on the Mac.
   - A stable address: a DHCP reservation on the router, or a `.local` name that resolves from Linux. Tell Claude the
     address and username; Claude adds an `ssh macbook` alias in `~/.ssh/config`.
2. **Same network as the Linux box (192.168.0.200, Wi-Fi) with nothing blocking traffic between them.** The Mac must
   reach `http://192.168.0.200:8946` (one port per run: 8943 to 8947 have been used). Client isolation / guest Wi-Fi
   will break this. The macOS firewall only matters for inbound, so it can stay on.
3. **Stay awake while rendering.** Plugged into power, lid open or clamshell with an external display, and sleep
   prevented. Claude launches the worker under `caffeinate -dimsu` so a long run is not suspended.
4. **Package tooling on PATH for non-interactive ssh.** Homebrew at `/opt/homebrew/bin` is not on the PATH of an ssh
   session unless set in `~/.zshenv`. Put `export PATH=/opt/homebrew/bin:$PATH` there (or tell Claude to export it
   every time). Needed: `uv` (or Python 3.12) and `ffmpeg`.
5. **Python environment** at `~/rt-tts/.venv-vox` (Python 3.12), with:
   - PyTorch with MPS support (the Mac mini used torch 2.14.1; any current release works),
   - `voxcpm` (VoxCPM2),
   - `numpy`, `soundfile`,
   - `transformers` (for the Whisper check).
   Claude can build this over ssh if Python 3.12 and `uv` are installed. The first run downloads `openbmb/VoxCPM2`
   from Hugging Face (several GB), so the Mac needs internet access, and a Hugging Face login only if the model ever
   becomes gated.
6. **Disk and memory.** About 20 GB free for the model cache, venv and reference-clip cache
   (`data/render/_refcache`). VoxCPM2 in fp32 on MPS used about 12.7 GB on the Mac mini, and Whisper-small adds about
   1 GB, so 16 GB of unified memory is a squeeze and 24 GB or more is comfortable. Tell Claude how much RAM it has.
   Close memory-heavy apps during a run.
7. **Repo subset at `~/rt-tts/repo`**, synced by Claude with rsync over ssh (no git needed). Contents:
   `tools/` (the Python files only), `src/TtsSidecar/`, `data/lexicon/`. Reference clips are fetched from the queue
   server on demand, so no audio data needs to be copied by hand. Claude re-syncs after any planner or lexicon change.

## Known gap: Whisper device

`worker.py` defaults `--asr-device` to `cuda:0`, and there is no CUDA on a Mac. Claude will pass `--asr-device mps`
(or `cpu`), and may need a small change in `asr_check.make_asr` to accept it. Without the check the worker still
renders, but `asr_bad` flags are then missing from the manifest and those takes cannot be auto-accepted by the
stitcher, so the check should stay on.

## Expected speed

Measured on the Mac mini M5 Pro (MPS): VoxCPM2 real-time factor about 0.75 to 0.8, versus 0.32 on the 5080 and roughly
0.75 on the 4070 in tonight's run. An M4 (Pro or Max) should land near the 4070, about 1 to 1.5 audio-hours per hour.
A base M4 will be slower. Adding it to the current two-GPU rate (about 28 jobs a minute) should give roughly 10 to 25
percent more throughput. Claude will measure on a few jobs first and report the real number.

## Not needed

- No inbound ports, no web server, no Docker.
- No game files, no Wwise tooling, no audio copied from the user's install.
- No GPU drivers (MPS ships with PyTorch).
- No credentials stored on the Mac for this project. The queue token (`valtok`) only guards the LAN queue and is passed
  on the command line.

## What to tell Claude when it is ready

1. The Mac's address and username.
2. Chip variant and RAM (M4, M4 Pro or Max, how many GB).
3. Confirmation that ssh works from the Linux box and that the Mac is on the same Wi-Fi or wired network.
4. Whether it can stay awake and plugged in for the run.

Claude then does the rest: checks the toolchain, builds the venv, syncs the repo, runs the `--engine fake` worker as a
plumbing test, benchmarks a few real jobs, and (once the user approves GPU use on it) starts a worker named
`macbook-m4` against the active queue. The pause and resume steps in the newest `HANDOFF-*.md` get one extra line
for stopping this worker by pid.
