// Port of tools/voice_design/fx.py (minus reverse reverb and speed, which stay offline), plus pitch, low shelf, de-esser,
// vocoder, compressor, phaser, voice-gated static, reverb and a final limiter.
// Order: highpass -> lowpass -> de-ess -> EQ -> pitch -> harmonizer -> freq shift -> low shelf -> vocoder -> compressor -> drive -> resonator ->
//        metal bank -> comb -> bitcrush -> ring mod -> tremolo -> chorus -> wow/flutter -> phaser -> dropout -> echo -> static -> reverb, then Mix, Output dB, limiter.
// De-ess goes before everything nonlinear because TTS sibilance is magnified by drive / ring mod / crush.
// After Mix and Output dB the signal becomes two channels (left = right while the stereo blocks are off): auto-pan, stereo chorus, stereo phaser,
// bass spread, then the limiter and clip on each channel. The game's own processed voices are stereo files (Pasqal, Ulfar, Trazyn), so the
// stereo movement is part of the effect, not a nicety.
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
fshz  = hslider("[202]Freq shift Hz (negative shifts down)", 0, -400, 400, 0.5) : s;
fsmix = hslider("[204]Freq shift mix (0 off)", 0, 0, 1, 0.01) : s;
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
mbhz  = hslider("[212]Metal base Hz", 300, 80, 1200, 1) : s;
mbin  = hslider("[214]Metal inharmonicity (0 harmonic, 1 metal bar)", 1, 0, 1, 0.01) : s;
mbq   = hslider("[216]Metal Q (ring length)", 30, 5, 80, 0.5) : s;
mbmix = hslider("[218]Metal mix (0 off)", 0, 0, 1, 0.01) : s;
cbms  = hslider("[222]Comb delay ms", 3, 0.3, 12, 0.05) : s;
cbfb  = hslider("[224]Comb feedback", 0.5, -0.9, 0.9, 0.01) : s;
cbmix = hslider("[226]Comb mix (0 off)", 0, 0, 1, 0.01) : s;
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
aph   = hslider("[232]Auto pan rate Hz", 0.5, 0.05, 8, 0.01) : s;
apd   = hslider("[234]Auto pan depth (0 off)", 0, 0, 1, 0.01) : s;
sch   = hslider("[242]Stereo chorus rate Hz", 0.6, 0.05, 6, 0.01) : s;
schd  = hslider("[244]Stereo chorus depth ms", 3, 0, 10, 0.1) : s;
schb  = hslider("[246]Stereo chorus delay ms", 14, 5, 30, 0.1) : s;
scho  = hslider("[248]Stereo chorus right offset deg", 180, 0, 360, 1) : s;
schm  = hslider("[250]Stereo chorus mix (0 off)", 0, 0, 1, 0.01) : s;
sphm  = hslider("[252]Stereo phaser mix (0 off)", 0, 0, 1, 0.01) : s;
sphz  = hslider("[254]Stereo phaser rate Hz", 0.3, 0.05, 8, 0.01) : s;
sphf  = hslider("[256]Stereo phaser feedback", 0.4, -0.9, 0.9, 0.01) : s;
sphs  = hslider("[258]Stereo phaser stages (2 4 6 8)", 4, 2, 8, 2);
sphl  = hslider("[260]Stereo phaser sweep low Hz", 200, 40, 1000, 10) : s;
sphh  = hslider("[262]Stereo phaser sweep high Hz", 3500, 1000, 9000, 50) : s;
spho  = hslider("[264]Stereo phaser right offset deg", 180, 0, 360, 1) : s;
bsx   = hslider("[272]Bass spread crossover Hz", 300, 60, 800, 1) : s;
bsd   = hslider("[274]Bass spread delay ms", 4, 1, 15, 0.1) : s;
bsdp  = hslider("[276]Bass spread motion depth", 0.5, 0, 1, 0.01) : s;
bshz  = hslider("[278]Bass spread motion rate Hz", 0.7, 0.05, 6, 0.01) : s;
bsmix = hslider("[280]Bass spread mix (0 off)", 0, 0, 1, 0.01) : s;
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
// Every band is exactly unity at 0 dB (the shelf is bypassed there, see hshelf). It sits right after the de-esser: shape the tone before anything nonlinear.
// fi.high_shelf at 0 dB is flat in level but rotates the phase around its corner, which colours the sound when Mix blends raw with the chain; so the shelf is bypassed at 0 dB.
hshelf(x) = ba.if(abs(eqsg) > 0.01, x : fi.high_shelf(eqsg, eqsf), x);
eq(x)    = x : fi.peak_eq(eqlg, eqlf, eqlf / eqlq) : fi.peak_eq(eqmg, eqmf, eqmf / eqmq) : fi.peak_eq(eqhg, eqhf, eqhf / eqhq) : hshelf;
// Harmonizer: up to two pitch-shifted copies added to the voice. ef.transpose is a pair of sweeping delay lines, so the copies are
// not time-aligned with the dry voice (the offset wanders); that is what makes them double rather than comb. Levels add, so expect more output.
harm(x)  = x + hm1lv * ef.transpose(1024, 512, hm1st, x) + hm2lv * ef.transpose(1024, 512, hm2st, x);
// Resonator: four fixed resonant peaks added to the voice, a crude stand-in for the impulse response of a small metal box (grille, tin, helmet).
res(x)   = ba.if(rsmix > 0, x + rsmix * 0.5 * (fi.resonbp(rf1, rqq, 1, x) + fi.resonbp(rf2, rqq, 1, x) + fi.resonbp(rf3, rqq, 1, x) + fi.resonbp(rf4, rqq, 1, x)), x);
// Frequency shifter (single sideband): every partial moves by the same number of Hz, so a harmonic voice turns inharmonic (metallic, eerie)
// without the mirrored copy that ring mod adds. The Hilbert pair is two allpass chains whose phases stay 90 degrees apart within 0.7 degrees
// from 0.002 to 0.998 of Nyquist (coefficients from Olli Niemitalo's IIR design, section (a - z^-2)/(1 - a z^-2) with a = c^2, second path
// delayed one sample; checked numerically: +100 Hz moves a 1 kHz tone to 1.1 kHz with the 900 Hz image 45 dB down). The dry side of the mix goes
// through the I chain so dry and shifted stay time-aligned (a shift of 0 with mix 1 is then an allpass, not a comb).
hsec(c)  = fi.tf2(c * c, 0, -1, 0, 0 - c * c);
hilI(x)  = x : hsec(0.4021921162426) : hsec(0.8561710882420) : hsec(0.9722909545651) : hsec(0.9952884791278);
hilQ(x)  = x : hsec(0.6923878) : hsec(0.9360654322959) : hsec(0.9882295226860) : hsec(0.9987488452737) : mem;
fsph     = os.phasor(1, fshz);
fshift(x) = ba.if(fsmix > 0, (1 - fsmix) * hilI(x) + fsmix * (hilI(x) * cos(2 * ma.PI * fsph) - hilQ(x) * sin(2 * ma.PI * fsph)), x);
// Metal bank: six narrow resonators whose frequencies sit at base * r(k), added to the voice, as if the voice were striking a metal object.
// r(k) slides from the harmonic series 1..6 (inharmonicity 0) to the modes of a free metal bar, 1 : 2.756 : 5.404 : 8.933 : 13.344 : 18.64 (1).
// Q sets how long they ring. fi.resonbp's peak gain is about Q times its gain argument, so each mode is scaled by 1/Q: unit peak gain,
// i.e. up to +8 dB over the dry at a mode with Mix 1. Partials above 0.45 of the sample rate are held there.
barr(k)  = ba.take(k + 1, (1.0, 2.756, 5.404, 8.933, 13.344, 18.64));
mbf(k)   = min(0.45 * ma.SR, mbhz * ((1 - mbin) * (k + 1) + mbin * barr(k)));
metalb(x) = ba.if(mbmix > 0, x + mbmix * 1.5 * sum(k, 6, fi.resonbp(mbf(k), mbq, 1 / mbq, x)), x);
// Comb (tube): a feedback comb filter with a delay of a few ms. Peaks fall at multiples of 1000/delay Hz, a hollow pipe or robot "flange";
// negative feedback moves the peaks to the odd multiples (a hollower, clarinet-like tube). Gain is normalised by sqrt(1 - feedback^2), so the
// overall level of noise stays put while the peaks rise and the valleys fall.
cbd      = max(1, cbms * ma.SR / 1000);
cbwet(x) = (x : (+ ~ (de.fdelay(1024, max(0, cbd - 1)) * cbfb))) * sqrt(1 - cbfb * cbfb);
tube(x)  = ba.if(cbmix > 0, (1 - cbmix) * x + cbmix * cbwet(x), x);
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

// ---- Stereo stage. Each block is a 2-in 2-out stage (left, right); with its mix or depth at 0 it passes both channels untouched. ----
// Auto pan: an equal-power balance swept by a sine LFO. Depth 1 swings from hard left to hard right; centre gain is exactly unity.
apos     = apd * os.osc(aph);
apang    = (apos + 1) * ma.PI / 4;
autopan  = ba.if(apd > 0, *(sqrt(2) * cos(apang)), _), ba.if(apd > 0, *(sqrt(2) * sin(apang)), _);
// Stereo chorus: each side has its own modulated delay, the right LFO offset from the left by "right offset" degrees (180 = opposite ways).
schch(i, x) = ba.if(schm > 0, (1 - schm) * x + schm * de.fdelay(2048, max(1, (schb + schd * os.oscp(sch, i * scho * ma.PI / 180)) * ma.SR / 1000), x), x);
schorus  = par(i, 2, schch(i));
// Stereo phaser: the allpass-chain phaser (see the mono one) run per side with the sweep of the right side offset by "right offset" degrees.
sphfreq(i) = sphl * (sphh / sphl) ^ (0.5 + 0.5 * os.oscp(sphz, i * spho * ma.PI / 180));
sphc(i)  = tan(ma.PI * min(sphfreq(i), ma.SR * 0.45) / ma.SR);
sapc(i)  = (sphc(i) - 1) / (sphc(i) + 1);
sap1(i)  = fi.tf1(sapc(i), 1, sapc(i));
sstg(i, n) = seq(j, n, sap1(i));
sphsel   = int(sphs / 2 - 1 + 0.5);
sphchain(i) = (+ : (_ <: sstg(i, 2), sstg(i, 4), sstg(i, 6), sstg(i, 8) : ba.selectn(4, sphsel))) ~ *(sphf);
sphase(i, x) = ba.if(sphm > 0, (1 - 0.5 * sphm) * x + 0.5 * sphm * (x : sphchain(i)), x);
sphaser  = par(i, 2, sphase(i));
// Bass spread: below the crossover each side's low band goes through a delay that swings around "delay ms" in opposite directions (left
// longer while right is shorter), so the bass differs between the ears and moves, while the highs stay put (delayed by the centre value so
// highs and lows still line up on average). The game's Pasqal differs left to right mostly below 300 Hz (coherence 0.44 there, 0.8 above 5 kHz).
bsmod(i) = bsd * (1 + bsdp * os.oscp(bshz, i * ma.PI));
bsch(i, x) = ba.if(bsmix > 0, (1 - bsmix) * x + bsmix * (de.fdelay(2048, max(1, bsd * ma.SR / 1000), x - lo) + de.fdelay(2048, max(1, bsmod(i) * ma.SR / 1000), lo)), x)
  with { lo = x : fi.lowpass(2, bsx); };
bspread  = par(i, 2, bsch(i));
// A 2-channel footswitch: blends the stage with the bypassed pair, like stomp for one channel.
stomp2(e, f) = (_, _) <: ((*(1 - e), *(1 - e)), (f : *(e), *(e))) :> (_, _);

on_hpf = checkbox("[4]Highpass on") : si.smoo;
on_lpf = checkbox("[8]Lowpass on") : si.smoo;
on_deess = checkbox("[12]De-ess on") : si.smoo;
on_eq = checkbox("[18]EQ on") : si.smoo;
on_shift = checkbox("[42]Pitch on") : si.smoo;
on_harm = checkbox("[46]Harmonizer on") : si.smoo;
on_fshift = checkbox("[200]Freq shift on") : si.smoo;
on_lows = checkbox("[56]Low shelf on") : si.smoo;
on_vocoder = checkbox("[60]Vocoder on") : si.smoo;
on_comp = checkbox("[78]Compressor on") : si.smoo;
on_drv = checkbox("[90]Drive on") : si.smoo;
on_res = checkbox("[94]Resonator on") : si.smoo;
on_metal = checkbox("[210]Metal on") : si.smoo;
on_tube = checkbox("[220]Comb on") : si.smoo;
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
chain = stomp(on_hpf, hpf) : stomp(on_lpf, lpf) : stomp(on_deess, deess) : stomp(on_eq, eq) : stomp(on_shift, shift) : stomp(on_harm, harm) : stomp(on_fshift, fshift) : stomp(on_lows, lows) : stomp(on_vocoder, vocoder) : stomp(on_comp, comp) : stomp(on_drv, drv) : stomp(on_res, res) : stomp(on_metal, metalb) : stomp(on_tube, tube) : stomp(on_crush, crush) : stomp(on_ring, ring) : stomp(on_trem, trem) : stomp(on_chorus, chorus) : stomp(on_wow, wowfl) : stomp(on_phaser, phaser) : stomp(on_drop, dropout) : stomp(on_echo, echo) : stomp(on_static, stat) : stomp(on_verb, verb);
on_apan = checkbox("[230]Auto pan on") : si.smoo;
on_schorus = checkbox("[240]Stereo chorus on") : si.smoo;
on_sphaser = checkbox("[270]Stereo phaser on") : si.smoo;
on_bspread = checkbox("[282]Bass spread on") : si.smoo;
stereo = stomp2(on_apan, autopan) : stomp2(on_schorus, schorus) : stomp2(on_sphaser, sphaser) : stomp2(on_bspread, bspread);
on_lim = checkbox("[196]Limiter on") : si.smoo;
// Limiter: fast compressor (ratio 20) at the threshold, no lookahead, then the hard clip stays as the last safety.
limit(x) = ba.if(lim < 0, x : co.compressor_mono(20, lim, 0.0005, 0.05), x);
process = _ <: (*(1 - mix)), (chain : *(mix)) :> *(lvl) <: (_, _) : stereo : par(i, 2, stomp(on_lim, limit) : max(-1) : min(1));
