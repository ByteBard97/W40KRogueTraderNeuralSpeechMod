// Port of tools/voice_design/fx.py (minus reverse reverb and speed, which stay offline), plus pitch, low shelf, de-esser,
// vocoder, compressor, phaser, voice-gated static, reverb and a final limiter.
// Order: highpass -> lowpass -> de-ess -> EQ -> pitch -> harmonizer -> low shelf -> vocoder -> compressor -> drive -> resonator ->
//        bitcrush -> ring mod -> tremolo -> chorus -> wow/flutter -> phaser -> dropout -> echo -> static -> reverb, then Mix, Output dB, limiter.
// De-ess goes before everything nonlinear because TTS sibilance is magnified by drive / ring mod / crush.
// "mix" blends the whole chain with the raw input: out = (1-mix)*raw + mix*chain. Zero / off settings bypass a stage.
// Pitch shift delays the wet path by about 20 ms, so keep Mix at 1 when pitch is used.
import("stdfaust.lib");

s(x) = x : si.smoo;
// Every stage has an on/off "stomp" checkbox (default on). Off = true bypass, with a short crossfade to avoid clicks.
stomp(e, f) = _ <: (*(1 - e)), (f : *(e)) :> _;
mix   = hslider("[2]Mix (0 raw, 1 processed)", 1, 0, 1, 0.001) : s;
hp    = hslider("[6]Highpass Hz (0 off)", 0, 0, 2000, 1) : s;
lp    = hslider("[10]Lowpass Hz (0 off)", 0, 0, 12000, 10) : s;
deth  = hslider("[14]De-ess threshold dB (0 off)", 0, -60, 0, 0.5) : s;
desf  = hslider("[16]De-ess frequency Hz", 6000, 3000, 9000, 50) : s;
eqlf  = hslider("[20]EQ low freq Hz", 250, 80, 1000, 1) : s;
eqlg  = hslider("[22]EQ low gain dB", 0, -18, 18, 0.1) : s;
eqlq  = hslider("[24]EQ low Q", 1, 0.3, 4, 0.01) : s;
eqmf  = hslider("[26]EQ mid freq Hz", 1000, 400, 4000, 1) : s;
eqmg  = hslider("[28]EQ mid gain dB", 0, -18, 18, 0.1) : s;
eqmq  = hslider("[30]EQ mid Q", 1, 0.3, 4, 0.01) : s;
eqhf  = hslider("[32]EQ high freq Hz", 3000, 1500, 9000, 1) : s;
eqhg  = hslider("[34]EQ high gain dB", 0, -18, 18, 0.1) : s;
eqhq  = hslider("[36]EQ high Q", 1, 0.3, 4, 0.01) : s;
eqsf  = hslider("[38]EQ shelf freq Hz", 3000, 1500, 9000, 1) : s;
eqsg  = hslider("[40]EQ shelf gain dB", 0, -18, 18, 0.1) : s;
pitch = hslider("[44]Pitch semitones", 0, -12, 12, 0.1) : s;
hm1st = hslider("[48]Harmonizer voice 1 semitones", -12, -24, 24, 0.1) : s;
hm1lv = hslider("[50]Harmonizer voice 1 level", 0, 0, 1, 0.01) : s;
hm2st = hslider("[52]Harmonizer voice 2 semitones", 7, -24, 24, 0.1) : s;
hm2lv = hslider("[54]Harmonizer voice 2 level", 0, 0, 1, 0.01) : s;
shelf = hslider("[58]Low shelf dB (200 Hz)", 0, -12, 12, 0.1) : s;
vcmix = hslider("[62]Vocoder mix (0 off)", 0, 0, 1, 0.01) : s;
vcn   = hslider("[64]Vocoder bands (8 16 24 32)", 16, 8, 32, 8);
vchz  = hslider("[66]Vocoder carrier Hz", 110, 30, 400, 1) : s;
vcpw  = hslider("[68]Vocoder pulse width", 0.3, 0.05, 0.95, 0.01) : s;
vcns  = hslider("[70]Vocoder carrier noise", 0.15, 0, 1, 0.01) : s;
vcat  = hslider("[72]Vocoder attack ms", 4, 1, 50, 0.5) : s;
vcrl  = hslider("[74]Vocoder release ms", 40, 5, 300, 1) : s;
vccp  = hslider("[76]Vocoder consonant pass (4.5 kHz+)", 0.3, 0, 1, 0.01) : s;
cth   = hslider("[80]Compressor threshold dB", -18, -60, 0, 0.5) : s;
cra   = hslider("[82]Compressor ratio (1 off)", 1, 1, 20, 0.1) : s;
cat   = hslider("[84]Compressor attack ms", 5, 0.1, 100, 0.1) : s;
crl   = hslider("[86]Compressor release ms", 80, 5, 1000, 1) : s;
cmk   = hslider("[88]Compressor makeup dB", 0, -12, 24, 0.1) : s;
drive = hslider("[92]Drive", 0, 0, 1, 0.01) : s;
rf1   = hslider("[96]Resonator freq 1 Hz", 700, 200, 8000, 1) : s;
rf2   = hslider("[98]Resonator freq 2 Hz", 1900, 200, 8000, 1) : s;
rf3   = hslider("[100]Resonator freq 3 Hz", 3100, 200, 8000, 1) : s;
rf4   = hslider("[102]Resonator freq 4 Hz", 4600, 200, 8000, 1) : s;
rqq   = hslider("[104]Resonator Q", 12, 2, 30, 0.1) : s;
rsmix = hslider("[106]Resonator mix (0 off)", 0, 0, 1, 0.01) : s;
bits  = hslider("[110]Crush bits (16 off)", 16, 2, 16, 1);
hold  = hslider("[112]Crush hold samples", 1, 1, 32, 1);
rhz   = hslider("[116]Ring Hz", 0, 0, 400, 1) : s;
rmix  = hslider("[118]Ring mix", 0, 0, 1, 0.01) : s;
thz   = hslider("[122]Tremolo Hz", 0, 0, 20, 0.1) : s;
tdep  = hslider("[124]Tremolo depth", 0, 0, 1, 0.01) : s;
chz   = hslider("[128]Chorus rate Hz", 0.8, 0.1, 6, 0.01) : s;
chdep = hslider("[130]Chorus depth ms", 3, 0, 10, 0.1) : s;
chdel = hslider("[132]Chorus delay ms", 15, 5, 30, 0.1) : s;
chmix = hslider("[134]Chorus mix (0 off)", 0, 0, 1, 0.01) : s;
wwct  = hslider("[138]Wow cents", 0, 0, 50, 0.5) : s;
wwhz  = hslider("[140]Wow rate Hz", 0.5, 0.2, 2, 0.01) : s;
flct  = hslider("[142]Flutter cents", 0, 0, 30, 0.5) : s;
flhz  = hslider("[144]Flutter rate Hz", 9, 4, 14, 0.1) : s;
phmix = hslider("[148]Phaser mix (0 off)", 0, 0, 1, 0.01) : s;
phhz  = hslider("[150]Phaser rate Hz", 0.3, 0.05, 8, 0.01) : s;
phfb  = hslider("[152]Phaser feedback", 0.4, -0.9, 0.9, 0.01) : s;
phst  = hslider("[154]Phaser stages (2 4 6 8)", 4, 2, 8, 2);
phlo  = hslider("[156]Phaser sweep low Hz", 200, 40, 1000, 10) : s;
phhi  = hslider("[158]Phaser sweep high Hz", 3500, 1000, 9000, 50) : s;
dprt  = hslider("[162]Dropout rate per s", 6, 1, 20, 0.5);
dpln  = hslider("[164]Dropout length ms", 60, 5, 400, 1);
dpamt = hslider("[166]Dropout amount (0 off)", 0, 0, 1, 0.01) : s;
ems   = hslider("[170]Echo ms", 0, 0, 500, 1) : s;
efb   = hslider("[172]Echo feedback", 0, 0, 0.9, 0.01) : s;
emix  = hslider("[174]Echo mix", 0, 0, 1, 0.01) : s;
stl   = hslider("[178]Static level dB (-60 off)", -60, -60, -6, 0.5) : s;
stlo  = hslider("[180]Static band low Hz", 300, 100, 3000, 10) : s;
sthi  = hslider("[182]Static band high Hz", 3400, 1000, 10000, 50) : s;
strl  = hslider("[184]Static tail ms", 120, 10, 3000, 5) : s;
rsize = hslider("[188]Reverb size", 0.5, 0, 0.98, 0.01) : s;
rdamp = hslider("[190]Reverb damping", 0.5, 0, 1, 0.01) : s;
rvmix = hslider("[192]Reverb mix", 0, 0, 1, 0.01) : s;
lvl   = hslider("[194]Output dB", 0, -24, 12, 0.1) : s : ba.db2linear;
lim   = hslider("[198]Limiter threshold dB (0 off)", 0, -24, 0, 0.5) : s;

hpf(x)   = ba.if(hp > 0, x : fi.highpass(2, max(20, hp)), x);
lpf(x)   = ba.if(lp > 0, x : fi.lowpass(2, max(100, lp)), x);
// De-esser: split at desf, compress only the high band (ratio 6), sum back. lo = x - hi so it is transparent when not reducing.
hiband(x) = x : fi.highpass(2, desf);
deess(x)  = ba.if(deth < 0, (x - hiband(x)) + (hiband(x) : co.compressor_mono(6, deth, 0.5, 40)), x);
shift(x) = ba.if(abs(pitch) > 0.01, ef.transpose(1024, 512, pitch, x), x);
lows(x)  = ba.if(abs(shelf) > 0.05, x : fi.low_shelf(shelf, 200), x);
// Parametric EQ: three peaking bands (gain dB, centre Hz, Q; fi.peak_eq wants a bandwidth in Hz so it is f/Q) and a high shelf.
// 0 dB is exactly unity, so there is no bypass logic. It sits right after the de-esser: shape the tone before anything nonlinear.
eq(x)    = x : fi.peak_eq(eqlg, eqlf, eqlf / eqlq) : fi.peak_eq(eqmg, eqmf, eqmf / eqmq) : fi.peak_eq(eqhg, eqhf, eqhf / eqhq) : fi.high_shelf(eqsg, eqsf);
// Harmonizer: up to two pitch-shifted copies added to the voice. ef.transpose is a pair of sweeping delay lines, so the copies are
// not time-aligned with the dry voice (the offset wanders); that is what makes them double rather than comb. Levels add, so expect more output.
harm(x)  = x + hm1lv * ef.transpose(1024, 512, hm1st, x) + hm2lv * ef.transpose(1024, 512, hm2st, x);
// Resonator: four fixed resonant peaks added to the voice, a crude stand-in for the impulse response of a small metal box (grille, tin, helmet).
res(x)   = ba.if(rsmix > 0, x + rsmix * 0.5 * (fi.resonbp(rf1, rqq, 1, x) + fi.resonbp(rf2, rqq, 1, x) + fi.resonbp(rf3, rqq, 1, x) + fi.resonbp(rf4, rqq, 1, x)), x);
// Wow and flutter: pitch wobble from a modulated delay. For a pitch deviation of C cents at rate R the delay amplitude is
// (2^(C/1200) - 1) / (2 pi R) seconds (0.5 Hz, 10 cents is about 1.9 ms). The base delay is the sum of both amplitudes plus 1 ms, which
// also delays the wet path by about that much, so keep Mix at 1 when this is used.
cams(c, r) = (2 ^ (c / 1200) - 1) / (2 * ma.PI * r);
wfbase   = cams(wwct, wwhz) + cams(flct, flhz) + 0.001;
wowfl(x) = ba.if(wwct + flct > 0, x : de.fdelay(8192, (wfbase + cams(wwct, wwhz) * os.osc(wwhz) + cams(flct, flhz) * os.osc(flhz)) * ma.SR), x);
// Dropout: every 1/rate seconds a coin flip decides (probability = amount) whether the signal is muted for the first "length" ms of that
// period, with a 2 ms fade. The coin is no.noise held on the period start; no.noise is bit-identical in FaustWasm and DawDreamer (checked).
dper     = max(1, int(ma.SR / dprt));
dph      = ba.time % dper;
dcoin    = ba.sAndH(dph == 0, no.noise * 0.5 + 0.5);
dmute    = (dcoin < dpamt) * (dph < int(dpln * ma.SR / 1000));
dgate    = 1 - (dmute : si.smooth(ba.tau2pole(0.002)));
dropout(x) = ba.if(dpamt > 0, x * dgate, x);
// Vocoder (channel vocoder): the voice is split into N log-spaced bands from 100 Hz to 7 kHz; each band's loudness drives the same
// band of a synthetic carrier (a pulse train at a fixed pitch plus noise), so the words survive but the voice is replaced by a monotone
// buzz. Few bands (8) sound crude and robotic, 16 is Cylon-like, 24-32 keeps more of the person. The carrier noise and the high-band
// "consonant pass" bring back s / t / k, which a purely pitched carrier loses. Own band layout (the library's one runs up to 12.8 kHz).
vcar     = os.pulsetrain(vchz, vcpw) * (1 - vcns) + no.noise * vcns;
vlo(n, i)  = 100 * (7000 / 100) ^ (i / n);
vhi(n, i)  = 100 * (7000 / 100) ^ ((i + 1) / n);
vband(n, i, x) = x : fi.resonbp(sqrt(vlo(n, i) * vhi(n, i)), sqrt(vlo(n, i) * vhi(n, i)) / (vhi(n, i) - vlo(n, i)), 1);
vcout(n, x) = par(i, n, ((x : vband(n, i) : an.amp_follower_ar(vcat / 1000, vcrl / 1000)), (vcar : vband(n, i))) : *) :> _ : *(vgain(n));
vgain(n) = 0.48 * pow(8 / n, 1.8);   // level-matched by measurement (no clip): resonant bands ring more as they get narrower   // level-matched by measurement: the more bands, the more carrier energy gets through
vocoder(x) = ba.if(vcmix > 0,
    (1 - vcmix) * x + vcmix * ((x <: vcout(8), vcout(16), vcout(24), vcout(32) : ba.selectn(4, int(vcn / 8 - 1 + 0.5))) + vccp * (x : fi.highpass(2, 4500))),
    x);
comp(x)  = ba.if(cra > 1.01, x : co.compressor_mono(cra, cth, cat / 1000, crl / 1000) : *(ba.db2linear(cmk)), x);
k        = 1 + drive * 9;
drv(x)   = ba.if(drive > 0, ma.tanh(k * x) / ma.tanh(k), x);
q        = 2 ^ (bits - 1) - 1;
quant(x) = ba.if(bits < 16, floor(x * q + 0.5) / q, x);
crush(x) = x : ba.sAndH(ba.pulse(hold)) : quant;
ring(x)  = (1 - rmix) * x + rmix * x * os.osc(rhz);
trem(x)  = x * (1 - tdep + tdep * (0.5 + 0.5 * os.osc(thz)));
// Two-voice chorus: the voices are modulated 90 degrees apart around the base delay.
cvoice(ph, x) = x : de.fdelay(4096, max(1, (chdel + chdep * os.oscp(chz, ph)) * ma.SR / 1000));
chorus(x) = ba.if(chmix > 0, (1 - chmix) * x + chmix * 0.5 * (cvoice(0, x) + cvoice(ma.PI / 2, x)), x);
// Phaser, guitar-pedal style: a chain of first-order allpass stages whose corner frequency is swept exponentially by a sine LFO,
// with feedback around the chain; each pair of stages makes one moving notch. Mix 1 = half dry, half allpass chain (deepest notches).
// 4 stages (2 notches) is the classic Phase 90; 8 is a Small Stone / Phase 100 style. Negative feedback gives a hollower, more nasal sweep.
phfreq   = phlo * (phhi / phlo) ^ (0.5 + 0.5 * os.osc(phhz));
phc      = tan(ma.PI * min(phfreq, ma.SR * 0.45) / ma.SR);
apc      = (phc - 1) / (phc + 1);
ap1      = fi.tf1(apc, 1, apc);
stages(n) = seq(i, n, ap1);
phsel    = int(phst / 2 - 1 + 0.5);
phchain  = (+ : (_ <: stages(2), stages(4), stages(6), stages(8) : ba.selectn(4, phsel))) ~ *(phfb);
phaser(x) = ba.if(phmix > 0, (1 - 0.5 * phmix) * x + 0.5 * phmix * (x : phchain), x);
d        = max(1, ems * ma.SR / 1000);
comb(x)  = x : de.fdelay(65536, d) : (+ ~ (de.fdelay(65536, max(0, d - 1)) * efb));
echo(x)  = ba.if(ems > 0, x + emix * comb(x), x);
// Static: band-limited noise gated by the voice's own envelope (plus a tail), so it only hisses while the character speaks.
env(x)    = x : an.amp_follower_ud(0.005, strl / 1000) : min(1) : *(8) : min(1);
stat(x)   = ba.if(stl > -59.5, x + (no.noise : fi.highpass(2, stlo) : fi.lowpass(2, sthi) : *(ba.db2linear(stl)) : *(env(x))), x);
verb(x)  = ba.if(rvmix > 0, x + rvmix * re.mono_freeverb(rsize, 0.5, rdamp, 23, x), x);

on_hpf = checkbox("[4]Highpass on") : si.smoo;
on_lpf = checkbox("[8]Lowpass on") : si.smoo;
on_deess = checkbox("[12]De-ess on") : si.smoo;
on_eq = checkbox("[18]EQ on") : si.smoo;
on_shift = checkbox("[42]Pitch on") : si.smoo;
on_harm = checkbox("[46]Harmonizer on") : si.smoo;
on_lows = checkbox("[56]Low shelf on") : si.smoo;
on_vocoder = checkbox("[60]Vocoder on") : si.smoo;
on_comp = checkbox("[78]Compressor on") : si.smoo;
on_drv = checkbox("[90]Drive on") : si.smoo;
on_res = checkbox("[94]Resonator on") : si.smoo;
on_crush = checkbox("[108]Crush on") : si.smoo;
on_ring = checkbox("[114]Ring on") : si.smoo;
on_trem = checkbox("[120]Tremolo on") : si.smoo;
on_chorus = checkbox("[126]Chorus on") : si.smoo;
on_wow = checkbox("[136]Wow flutter on") : si.smoo;
on_phaser = checkbox("[146]Phaser on") : si.smoo;
on_drop = checkbox("[160]Dropout on") : si.smoo;
on_echo = checkbox("[168]Echo on") : si.smoo;
on_static = checkbox("[176]Static on") : si.smoo;
on_verb = checkbox("[186]Reverb on") : si.smoo;
chain = stomp(on_hpf, hpf) : stomp(on_lpf, lpf) : stomp(on_deess, deess) : stomp(on_eq, eq) : stomp(on_shift, shift) : stomp(on_harm, harm) : stomp(on_lows, lows) : stomp(on_vocoder, vocoder) : stomp(on_comp, comp) : stomp(on_drv, drv) : stomp(on_res, res) : stomp(on_crush, crush) : stomp(on_ring, ring) : stomp(on_trem, trem) : stomp(on_chorus, chorus) : stomp(on_wow, wowfl) : stomp(on_phaser, phaser) : stomp(on_drop, dropout) : stomp(on_echo, echo) : stomp(on_static, stat) : stomp(on_verb, verb);
on_lim = checkbox("[196]Limiter on") : si.smoo;
// Limiter: fast compressor (ratio 20) at the threshold, no lookahead, then the hard clip stays as the last safety.
limit(x) = ba.if(lim < 0, x : co.compressor_mono(20, lim, 0.0005, 0.05), x);
process = _ <: (*(1 - mix)), (chain : *(mix)) :> *(lvl) : stomp(on_lim, limit) : max(-1) : min(1);
