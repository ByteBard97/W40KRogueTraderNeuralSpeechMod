# Third-party tools and licensing detail

Dev-only tools used to extract data from your own copy of the game. Neither is bundled in any
release - see below for why.

## wwiser

[wwiser](https://github.com/bnnm/wwiser) by bnnm - used locally for Wwise bank extraction.

**Not bundled.** The repo has no LICENSE file granting redistribution rights, so contributors
must download it themselves (link above) rather than vendor the binary in a release zip.

## vgmstream

[vgmstream](https://vgmstream.org) - ISC license (permissive, bundling-safe).

Copyright (c) Adam Gashlin, Fastelbja, Ronny Elfert, bnnm, Christopher Snowhill,
NicknineTheEagle, bxaimc, Thealexbarney, CyberBotX, EdnessP, and contributors, with portions by
Marko Kreen, jagarl, Nullsoft, Paul Hsieh, Lesahde Entis, and Sun Microsystems (see vgmstream's
`COPYING`).

Official prebuilt CLI binaries exist for Windows/macOS/Linux, so per-OS bundling is viable once a
release needs it - check whether the vendored build links LGPL components (mpg123, FFmpeg)
dynamically or statically before shipping, per vgmstream's own `doc/BUILD.md`.
