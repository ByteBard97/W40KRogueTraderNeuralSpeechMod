"""Rebuild BG3 voice reference clips (ref_v2_N.wav): ~15 s of clean speech, little silence.

Reads data/bg3_voices/catalog.json.pre-v2-2026-10-12 (the pre-rebuild catalog), decodes candidate lines
from Voice.pak with vgmstream, scores them, writes new wavs plus an updated catalog.json (atomic) and
rebuild_report.json.  Nothing is deleted; old ref_N.wav stay.

Usage: python3 rebuild_refs.py [--procs 12] [--only slug,slug] [--limit N] [--dry]
"""
import sys, os, re, io, json, subprocess, itertools, argparse, time, math
import numpy as np
from math import gcd
from scipy.io import wavfile
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lspk

ROOT = '/home/geoff/projects/games/W40KRogueTraderNeuralSpeechMod'
OUT = ROOT + '/data/bg3_voices'
WORK = '/home/geoff/bg3-work/catalog'
VGM = '/home/geoff/bg3-work/vgm/vgmstream-cli'
PFX = 'Mods/Gustav/Localization/English/Soundbanks/'
TMPDIR = os.environ.get('RB_TMP', '/tmp')
SR = 24000
FR = 480  # 20 ms
FRS = FR / SR

# thresholds from the brief
MIN_DB, REL_DB = -45.0, 35.0
SINGLE_DUR = (10.0, 20.0)
SHORT_DUR = (3.0, 12.0)
MIN_RATIO, MAX_GAP = 0.85, 0.7
NOISE_MARGIN_DB = 30.0
LEVEL_TOL_DB = 6.0
F0_TOL = 0.15
GAP_S, XFADE_S = 0.35, 0.02
STITCH_TOTAL = (12.0, 20.0)
TARGET = 15.0
PAD_S = 0.02
COMP_MIN_GAP_S, COMP_KEEP_S = 0.5, 0.15
ROUND_N = 60
MAX_CAND = 240

INTERJ = set('ha hah haha hahaha heh hehe ah ahh aah oh ooh ohh uh uhh um umm hm hmm hmmm mm mmm huh eh ugh argh agh grr gah '
             'ow ahem oof phew sigh gasp yes no wow whoa hey hmph tsk psst shh shhh'.split())


def clean_text(t, narr):
    t = re.sub(r'<br\s*/?>', ' ', t)
    t = re.sub(r'</?[ibu]>', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^\(\(\*?|\*?\)\)$', '', t).strip()
    if narr:
        t = t.strip('*').strip()
    return t


def text_ok(t, min_words):
    if not t or re.search(r'[\[\]{}<>*|_#~^@]|\(|\)', t):
        return False
    words = re.findall(r"[A-Za-z']+", t)
    if len(words) < min_words:
        return False
    inter = sum(1 for w in words if w.lower() in INTERJ)
    if inter / len(words) > 0.3:
        return False
    return True


def decode(pak, src, tmpname):
    cache = None
    # prefer cached wem if present
    name = PFX + src
    if name not in pak.entries:
        return None
    with open(tmpname, 'wb') as f:
        f.write(pak.read(name))
    r = subprocess.run([VGM, '-p', '-o', '?f.wav', tmpname], capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 100:
        return None
    sr, y = wavfile.read(io.BytesIO(r.stdout))
    if y.dtype.kind == 'i':
        y = y.astype(np.float32) / np.iinfo(y.dtype).max
    else:
        y = y.astype(np.float32)
    if y.ndim > 1:
        y = y.mean(1)
    if sr != SR:
        g = gcd(sr, SR)
        y = resample_poly(y, SR // g, sr // g).astype(np.float32)
    return y


def frame_db(y):
    n = len(y) // FR
    if n == 0:
        return np.zeros(0)
    fr = y[:n * FR].reshape(n, FR).astype(np.float64)
    return 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)


def longest_run(mask):
    best = cur = 0
    for v in mask:
        cur = 0 if v else cur + 1
        best = max(best, cur)
    return best


def analyse(y):
    """Return metrics dict + trimmed audio (with small pad) or None."""
    db = frame_db(y)
    if len(db) < 10:
        return None
    thr = max(MIN_DB, db.max() - REL_DB)
    sp = db > thr
    idx = np.flatnonzero(sp)
    if len(idx) < 5:
        return None
    a, b = idx[0], idx[-1]
    seg_sp = sp[a:b + 1]
    seg_db = db[a:b + 1]
    n = len(seg_sp)
    ratio = float(seg_sp.mean())
    gap = longest_run(seg_sp) * FRS
    s0 = max(0, a * FR - int(PAD_S * SR))
    s1 = min(len(y), (b + 1) * FR + int(PAD_S * SR))
    t = y[s0:s1].copy()
    core = y[a * FR:(b + 1) * FR]
    peak = float(np.abs(core).max())
    med_sp = float(np.median(seg_db[seg_sp]))
    p10 = float(np.percentile(seg_db, 10))
    p10_full = float(np.percentile(db, 10))
    # speech rms level (dBFS) over speech frames
    fr = core[:n * FR].reshape(n, FR).astype(np.float64)
    lvl = float(20 * np.log10(np.sqrt((fr[seg_sp] ** 2).mean()) + 1e-9))
    return dict(audio=t, dur=n * FRS, speech_s=float(seg_sp.sum() * FRS), ratio=ratio, gap=gap, peak=peak,
                noise_margin=med_sp - p10, noise_margin_full=med_sp - p10_full, lvl=lvl)


def compress_gaps(y):
    """Shorten internal pauses longer than COMP_MIN_GAP_S to 2*COMP_KEEP_S. None if nothing changed."""
    db = frame_db(y)
    if len(db) < 10: return None
    sp = db > max(MIN_DB, db.max() - REL_DB)
    idx = np.flatnonzero(sp)
    if len(idx) < 5: return None
    a, b = idx[0], idx[-1]
    keep = np.ones(b + 1 - a, bool)
    i = 0
    seg = sp[a:b + 1]
    minf, kf = int(COMP_MIN_GAP_S / FRS), int(COMP_KEEP_S / FRS)
    changed = False
    while i < len(seg):
        if seg[i]:
            i += 1; continue
        j = i
        while j < len(seg) and not seg[j]: j += 1
        if j - i > minf:
            keep[i + kf:j - kf] = False; changed = True
        i = j
    if not changed: return None
    core = y[a * FR:(b + 1) * FR]
    n = len(core) // FR
    fr = core[:n * FR].reshape(n, FR)[keep[:n]]
    out = fr.reshape(-1).copy()  # seams lie inside near-silence (< -45 dBFS), no smoothing needed
    pad = int(PAD_S * SR)
    return np.concatenate([np.zeros(pad, np.float32), out.astype(np.float32), np.zeros(pad, np.float32)])


def f0_est(y):
    """Median F0 via normalised autocorrelation on voiced frames (8 kHz)."""
    z = resample_poly(y, 1, 3).astype(np.float64)
    W, H = 320, 160
    n = (len(z) - W) // H
    if n < 5:
        return None
    idx = np.arange(W)[None, :] + H * np.arange(n)[:, None]
    fr = z[idx]
    fr = fr - fr.mean(1, keepdims=True)
    en = (fr ** 2).sum(1)
    keep = en > en.max() * 0.02
    if keep.sum() < 3:
        return None
    fr = fr[keep] * np.hanning(W)
    spec = np.fft.rfft(fr, 1024, axis=1)
    ac = np.fft.irfft(np.abs(spec) ** 2, axis=1)[:, :W]
    ac = ac / (ac[:, :1] + 1e-12)
    lo, hi = int(8000 / 450), int(8000 / 60)
    seg = ac[:, lo:hi]
    pk = seg.argmax(1)
    val = seg.max(1)
    ok = val > 0.5
    if ok.sum() < 3:
        return None
    return float(np.median(8000.0 / (pk[ok] + lo)))


def meets_core(m, noise=True):
    return (m['ratio'] >= MIN_RATIO and m['gap'] <= MAX_GAP and m['peak'] < 0.99
            and (not noise or m['noise_margin'] >= NOISE_MARGIN_DB))


def fail_reasons(m, med_lvl=None, dur_range=SINGLE_DUR):
    r = []
    if not (dur_range[0] <= m['dur'] <= dur_range[1]): r.append('duration')
    if m['ratio'] < MIN_RATIO: r.append('speech_ratio')
    if m['gap'] > MAX_GAP: r.append('gap')
    if m['peak'] >= 0.99: r.append('clipping')
    if m['noise_margin'] < NOISE_MARGIN_DB: r.append('noise')
    if med_lvl is not None and abs(m['lvl'] - med_lvl) > LEVEL_TOL_DB: r.append('level')
    return r


def rank_key(m):
    return (-round(m['ratio'], 2), abs(m['dur'] - TARGET))


def spread(items, n, offset):
    if len(items) <= n:
        return list(items)
    step = len(items) / n
    return [items[min(len(items) - 1, int(i * step + offset * step))] for i in range(n)]


def build_stitch(parts):
    """parts: list of dicts with audio, lvl. Loudness-match, join. Returns audio."""
    target = float(np.mean([p['m']['lvl'] for p in parts]))
    xf = int(XFADE_S * SR)
    gap = np.zeros(int(GAP_S * SR), np.float32)
    outs = []
    for p in parts:
        g = 10 ** ((target - p['m']['lvl']) / 20)
        a = (p['m']['audio'] * g).astype(np.float32)
        a[:xf] *= np.linspace(0, 1, xf, dtype=np.float32)
        a[-xf:] *= np.linspace(1, 0, xf, dtype=np.float32)
        outs.append(a)
    segs = []
    for i, a in enumerate(outs):
        if i: segs.append(gap)
        segs.append(a)
    y = np.concatenate(segs)
    pk = np.abs(y).max()
    if pk > 0.95:
        y = y * (0.95 / pk)
    return y


def stitch_groups(shorts, used, max_groups):
    """Greedy: repeatedly pick best disjoint group of 2-4 shorts."""
    groups = []
    avail = [s for s in shorts if s['h'] not in used and s.get('f0')]
    while len(groups) < max_groups:
        avail = [s for s in avail if s['h'] not in used]
        avail.sort(key=lambda s: (-round(s['m']['ratio'], 2), abs(s['m']['dur'] - 5)))
        pool = avail[:14]
        best = None
        for k in (2, 3, 4):
            for comb in itertools.combinations(pool, k):
                tot = sum(c['m']['dur'] for c in comb) + GAP_S * (k - 1)
                if not (STITCH_TOTAL[0] <= tot <= STITCH_TOTAL[1]):
                    continue
                f = [c['f0'] for c in comb]
                if max(f) / min(f) - 1 > F0_TOL:
                    continue
                lv = [c['m']['lvl'] for c in comb]
                if max(lv) - min(lv) > 4.0:
                    continue
                dsum = sum(c['m']['dur'] for c in comb)
                ratio = sum(c['m']['ratio'] * c['m']['dur'] for c in comb) / dsum
                # prefer high ratio, near 15 s, fewer joins
                score = (-round(ratio, 2), abs(tot - TARGET), k)
                if best is None or score < best[0]:
                    best = (score, comb)
        if not best:
            break
        groups.append(list(best[1]))
        used |= {c['h'] for c in best[1]}
    return groups


def work(job):
    u, rec = job['u'], job['rec']
    slug = rec['slug']
    narr = (u == 'NARRATOR')
    t0 = time.time()
    pak = lspk.Pak(lspk.DATA + 'Localization/Voice.pak')
    tmpname = os.path.join(TMPDIR, 'rb_%d.wem' % os.getpid())
    lines = [(h, l, src) for h, l, src in job['lines'] if PFX + src in pak.entries and 3.0 <= l <= 20.0]
    loca = job['loca']
    cands = []
    for h, l, src in lines:
        t = clean_text(loca.get(h, ''), narr)
        if text_ok(t, 5 if l >= 9.5 else 3):
            cands.append((h, l, src, t))
    n_text_ok = len(cands)
    analysed = {}  # h -> dict
    done = set()
    rnd = 0
    singles, shorts, relaxed, singles_b, shorts_b, singles_c, shorts_c = [], [], [], [], [], [], []
    all_lvl = []

    def process(sel):
        for h, l, src, t in sel:
            done.add(h)
            try:
                y = decode(pak, src, tmpname)
            except Exception:
                y = None
            if y is None:
                continue
            m = analyse(y)
            if m is None:
                continue
            m['src'] = src
            all_lvl.append(m['lvl'])
            yc = compress_gaps(y)
            mc = analyse(yc) if yc is not None else None
            if mc is not None: mc['src'] = src
            analysed[h] = (m, t, mc)

    def classify():
        med = float(np.median(all_lvl)) if all_lvl else None
        for lst in (singles, shorts, relaxed, singles_b, shorts_b, singles_c, shorts_c): lst.clear()
        if med is None: return med
        for h, (m, t, mc) in analysed.items():
            if abs(m['lvl'] - med) > LEVEL_TOL_DB: continue
            for mm, comp, sl, sh in ((m, False, singles, shorts), (mc, True, singles_b, shorts_b)):
                if mm is None: continue
                if meets_core(mm):
                    if SINGLE_DUR[0] <= mm['dur'] <= SINGLE_DUR[1]:
                        sl.append(dict(h=h, m=mm, t=t, comp=comp))
                    if SHORT_DUR[0] <= mm['dur'] <= SHORT_DUR[1]:
                        sh.append(dict(h=h, m=mm, t=t, comp=comp))
                if meets_core(mm, noise=False) and not meets_core(mm):
                    if SINGLE_DUR[0] <= mm['dur'] <= SINGLE_DUR[1]:
                        singles_c.append(dict(h=h, m=mm, t=t, comp=comp, nr=True))
                    if SHORT_DUR[0] <= mm['dur'] <= SHORT_DUR[1]:
                        shorts_c.append(dict(h=h, m=mm, t=t, comp=comp, nr=True))
                if (mm['ratio'] >= MIN_RATIO and mm['gap'] <= MAX_GAP and mm['peak'] < 0.99
                        and mm['noise_margin'] >= NOISE_MARGIN_DB and 6.0 <= mm['dur'] <= 24.0
                        and not (SINGLE_DUR[0] <= mm['dur'] <= SINGLE_DUR[1])):
                    relaxed.append(dict(h=h, m=mm, t=t, comp=comp))
        return med

    def choose():
        for lst in (shorts, shorts_b, shorts_c):
            for s in lst:
                if 'f0' not in s: s['f0'] = f0_est(s['m']['audio'])
        chosen, used = [], set()
        for sl, sh in ((singles, shorts), (singles_b, shorts_b), (singles_c, shorts_c)):
            sl.sort(key=lambda s: rank_key(s['m']))
            for s in sl:
                if len(chosen) >= 3: break
                if s['h'] in used: continue
                chosen.append(('single', [s])); used.add(s['h'])
            if len(chosen) < 3:
                for g in stitch_groups(sh, used, 3 - len(chosen)):
                    chosen.append(('stitched', g)); used |= {c['h'] for c in g}
        return chosen

    chosen = []
    while True:
        remaining = [c for c in cands if c[0] not in done]
        if not remaining or len(done) >= MAX_CAND:
            break
        longs = [c for c in remaining if c[1] >= 10.0]
        shs = [c for c in remaining if c[1] < 10.0]
        if len(shs) < 20: longs = longs + shs; shs = []
        sel = spread(longs, 16, 0.37 * rnd % 1) + spread(shs, ROUND_N - min(16, len(longs)), 0.61 * rnd % 1)
        process(sel)
        rnd += 1
        classify()
        chosen = choose()
        if sum(1 for c in chosen if not c[1][0].get('nr')) >= 3:
            break
    med = classify()
    chosen = choose()
    relaxed_used = False
    if not chosen and relaxed:
        relaxed.sort(key=lambda s: (-round(s['m']['ratio'], 2), -s['m']['speech_s']))
        seen = set()
        for s in relaxed:
            if s['h'] in seen or len(seen) >= 3: continue
            seen.add(s['h']); chosen.append(('single', [s])); relaxed_used = True

    refs = []
    od = os.path.join(OUT, slug)
    for k, (kind, parts) in enumerate(chosen, 1):
        if kind == 'single':
            y = parts[0]['m']['audio']
            if np.abs(y).max() > 0.99: y = y * (0.98 / np.abs(y).max())
        else:
            y = build_stitch(parts)
        m = analyse(y)
        if m is None: continue
        if kind == 'stitched':  # the deliberate 0.35 s joins are not counted as silence in the ratio
            nj = (len(parts) - 1) * int(GAP_S / FRS)
            m['ratio'] = min(1.0, (m['speech_s'] / FRS) / max(1.0, m['dur'] / FRS - nj))
        f0s = [p.get('f0') or f0_est(p['m']['audio']) for p in parts]
        f0s = [f for f in f0s if f]
        refs.append(dict(
            wav='data/bg3_voices/%s/ref_v2_%d.wav' % (slug, k),
            text=' '.join(p['t'] for p in parts),
            seconds=round(len(y) / SR, 2), speech_seconds=round(m['speech_s'], 2), speech_ratio=round(m['ratio'], 3),
            longest_gap_s=round(m['gap'], 2), kind=kind, noise_relaxed=any(p.get('nr') for p in parts), gaps_compressed=any(p.get('comp') for p in parts), handles=[p['h'] for p in parts],
            f0_hz=round(float(np.median(f0s)), 1) if f0s else None, rms_db=round(m['lvl'], 1),
            _pcm=(np.clip(y, -1, 1) * 32767).astype(np.int16)))
    # order: singles (strict) first by rank, then stitched; already so.
    # old-ref scoring under same rules
    old = []
    for r in rec.get('refs', []):
        if not r.get('wav'):
            continue
        try:
            sr, w = wavfile.read(os.path.join(ROOT, r['wav']))
            w = w.astype(np.float32) / 32768.0
            if w.ndim > 1: w = w.mean(1)
            if sr != SR:
                g = gcd(sr, SR); w = resample_poly(w, SR // g, sr // g).astype(np.float32)
            m = analyse(w)
            if m is None:
                old.append(dict(fail=['no_speech'])); continue
            fr = fail_reasons(m, med)
            tt = clean_text(r.get('text', ''), narr)
            if not text_ok(tt, 5): fr.append('text')
            old.append(dict(fail=fr, ratio=round(m['ratio'], 3), gap=round(m['gap'], 2), dur=round(m['dur'], 2),
                            speech_s=round(m['speech_s'], 2)))
        except Exception as e:
            old.append(dict(fail=['unreadable'], err=str(e)[:60]))
    # write wavs
    if refs and not job.get('dry'):
        os.makedirs(od, exist_ok=True)
        for k, r in enumerate(refs, 1):
            wavfile.write(os.path.join(od, 'ref_v2_%d.wav' % k), SR, r['_pcm'])
    for r in refs: r.pop('_pcm')
    return dict(u=u, slug=slug, refs=refs, relaxed=relaxed_used, n_cand=len(cands), n_text_ok=n_text_ok,
                n_analysed=len(analysed), n_singles=len({s['h'] for s in singles}), n_singles_b=len({s['h'] for s in singles_b}), n_shorts=len(shorts),
                median_lvl=med, old=old, secs=round(time.time() - t0, 1))


def quality(refs):
    if not refs: return 'poor'
    r = refs[0]
    if r['speech_seconds'] >= 12 and r['speech_ratio'] >= MIN_RATIO and not r.get('noise_relaxed'): return 'good'
    if r['speech_seconds'] >= 8: return 'ok'
    return 'poor'


def atomic_json(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--procs', type=int, default=12)
    ap.add_argument('--only', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--final', action='store_true', help='write catalog.json + report (default only with full run)')
    a = ap.parse_args()
    cat = json.load(open(OUT + '/catalog.json.pre-v2-2026-10-12'))
    L = json.load(open(WORK + '/speaker_lines.json'))
    loca = json.load(open(WORK + '/loca_cache.json'))
    cast = json.load(open(ROOT + '/data/studio/casting.json'))['assignments']
    cast_slugs = {v['bg3'] for v in cast.values()}
    order = sorted([c for c in cat if c.get('slug')], key=lambda c: (c['slug'] not in cast_slugs, -c['lines']))
    if a.only:
        want = set(a.only.split(','))
        order = [c for c in order if c['slug'] in want]
    if a.limit: order = order[:a.limit]
    jobs = []
    for c in order:
        ls = L.get(c['speaker_uuid'], [])
        jobs.append(dict(u=c['speaker_uuid'], rec=c, lines=ls, dry=a.dry,
                         loca={h: loca[h] for h, _, _ in ls if h in loca}))
    from multiprocessing import Pool
    results = {}
    prog_path = OUT + '/rebuild_progress.json'
    t0 = time.time()
    with Pool(a.procs) as pool:
        for i, r in enumerate(pool.imap(work, jobs, chunksize=1), 1):
            results[r['u']] = r
            if i % 5 == 0 or i == len(jobs):
                q = {}
                for x in results.values():
                    k = quality(x['refs']); q[k] = q.get(k, 0) + 1
                atomic_json(prog_path, dict(done=i, total=len(jobs), elapsed_s=round(time.time() - t0),
                                            quality=q, last=r['slug'], results={
                    x['slug']: dict(quality=quality(x['refs']), refs=x['refs'], n_singles=x['n_singles'])
                    for x in results.values()}))
                print(i, len(jobs), r['slug'], quality(r['refs']), round(time.time() - t0), flush=True)
    atomic_json(OUT + '/rebuild_results_raw.json', results)
    if a.dry or a.only or a.limit:
        return
    finalize(cat, results, cast)


def finalize(cat, results, cast):
    new = []
    cast_by_slug = {}
    for name, v in cast.items(): cast_by_slug.setdefault(v['bg3'], []).append(name)
    counts, stitched, nrefs = {}, 0, 0
    poor_cast = []
    for c in cat:
        if not c.get('slug'):
            new.append(c); continue
        r = results.get(c['speaker_uuid'])
        c = dict(c)
        c['old_refs'] = c.get('old_refs') or c.get('refs', [])
        notes = list(c.get('notes') or [])
        if r and r['refs']:
            c['refs'] = r['refs']
            q = quality(r['refs'])
            if r['relaxed']: notes.append('v2 refs relaxed: no line met the 10-20 s rule; best shorter/longer lines used')
        else:
            c['refs'] = c['old_refs']
            q = 'poor'
            notes.append('v2 rebuild: no usable lines found (n_candidates=%d); old refs kept' % (r['n_cand'] if r else 0))
        c['refs_quality'] = q
        if notes: c['notes'] = notes
        counts[q] = counts.get(q, 0) + 1
        if r and r['refs']:
            nrefs += len(r['refs']); stitched += sum(1 for x in r['refs'] if x['kind'] == 'stitched')
        if q == 'poor' and c['slug'] in cast_by_slug:
            poor_cast.append(dict(slug=c['slug'], cast_as=cast_by_slug[c['slug']]))
        new.append(c)
    # old-ref scoring
    o_total = o_fail = s_fail = s_total = 0
    reasons = {}
    for r in results.values():
        if not r['old']: continue
        s_total += 1
        if r['old'][0]['fail']: s_fail += 1
        for o in r['old']:
            o_total += 1
            if o['fail']: o_fail += 1
            for f in o['fail']: reasons[f] = reasons.get(f, 0) + 1
    rep = dict(speakers=len(cat), quality=counts, refs_written=nrefs, stitched_refs=stitched,
               old_refs_scored=o_total, old_refs_failing=o_fail, old_ref1_scored=s_total, old_ref1_failing=s_fail,
               old_fail_reasons=reasons, cast_poor=poor_cast,
               no_single=[x['slug'] for x in results.values() if x['n_singles'] == 0][:400],
               n_no_single=sum(1 for x in results.values() if x['n_singles'] == 0))
    atomic_json(OUT + '/catalog.json', new)
    atomic_json(OUT + '/rebuild_report.json', rep)
    print(json.dumps(rep, indent=1)[:2000])


if __name__ == '__main__':
    main()
