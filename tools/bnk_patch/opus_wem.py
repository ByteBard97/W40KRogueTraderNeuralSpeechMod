"""Wwise Opus wem writer (format tag 0x3041, "OPUS_WEM", Wwise 2019.2.3 and later). EXPERIMENTAL: layout taken from
vgmstream's wwise.c, not yet heard in game; prove it with a tone test (tone_test3.py) before any bulk build.

fmt (offsets from the fmt data; channels=2 only changes 0x02 to 2 and 0x14 to 0x3): 0x00 tag 0x3041, 0x02 channels, 0x04 rate 48000, 0x08 avg bytes/s, 0x0c block 0,
0x0e bits 0, 0x10 cbSize, 0x12 samples per frame, 0x14 channel mask, 0x18 num_samples, 0x1c table_count (frames),
0x20 skip, 0x22 version 1, 0x23 mapping. 'seek' chunk: u16 size of every Opus frame. 'data': the raw packets, back to back.
"""
import struct, subprocess
from wem import FFMPEG

RATE = 48000
FRAME_SAMPLES = 960            # 20 ms
MASK_MONO = 0x4
MASK_STEREO = 0x3              # front left + front right
BITRATE = "24k"


def encode_ogg_opus(wav_path, bitrate=BITRATE, gain_db=0.0, channels=1):
    """wav -> mono (or, with channels=2, stereo) 48 kHz Ogg Opus bytes with 20 ms frames."""
    af = "volume=%.2fdB" % gain_db
    return subprocess.run([FFMPEG, "-nostdin", "-hide_banner", "-i", wav_path, "-af", af, "-ac", str(channels), "-ar", str(RATE),
                           "-c:a", "libopus", "-b:a", bitrate, "-vbr", "on", "-frame_duration", "20",
                           "-application", "audio", "-f", "ogg", "-"], capture_output=True).stdout


def ogg_packets(data):
    """[(packet bytes, granule)] from an Ogg stream (single logical stream, lacing handled)."""
    out, pos, cur = [], 0, b""
    while pos < len(data):
        assert data[pos:pos + 4] == b"OggS", "not an Ogg page at %d" % pos
        gran = struct.unpack_from("<q", data, pos + 6)[0]
        nseg = data[pos + 26]
        lacing = data[pos + 27:pos + 27 + nseg]
        body = pos + 27 + nseg
        for lace in lacing:
            cur += data[body:body + lace]
            body += lace
            if lace < 255:
                out.append((cur, gran))
                cur = b""
        pos = body
    return out


def opus_wem(wav_path, bitrate=BITRATE, gain_db=0.0, cb_size=None, channels=1):
    """channels=1 is the original mono wem (unchanged); channels=2 writes a stereo one (mask 0x3). For stereo pass a
    bitrate about twice the mono one (the default 24k is shared by both sides)."""
    assert channels in (1, 2), channels
    pk = ogg_packets(encode_ogg_opus(wav_path, bitrate, gain_db, channels))
    head = pk[0][0]
    assert head[:8] == b"OpusHead", head[:8]
    assert head[9] == channels, (head[9], channels)
    skip = struct.unpack_from("<H", head, 10)[0]
    frames = [p for p, _ in pk[2:] if p]            # drop OpusHead and OpusTags
    total = pk[-1][1] - skip                        # last granule counts samples at 48 kHz including pre-skip
    extra = struct.pack("<HIiIHBB", FRAME_SAMPLES, MASK_STEREO if channels == 2 else MASK_MONO, total, len(frames), skip, 1, 0)   # fields from 0x12 on
    avg = int(sum(len(f) for f in frames) * RATE / max(1, total))
    fmt = struct.pack("<HHIIHHH", 0x3041, channels, RATE, avg, 0, 0, len(extra) if cb_size is None else cb_size) + extra
    seek = struct.pack("<%dH" % len(frames), *[len(f) for f in frames])
    data = b"".join(frames)
    body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt
    body += b"seek" + struct.pack("<I", len(seek)) + seek + (b"\0" if len(seek) % 2 else b"")
    body += b"data" + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")
    return b"RIFF" + struct.pack("<I", len(body)) + body
