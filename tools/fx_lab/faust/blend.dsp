// Smallest example: highpass -> lowpass -> drive, convex-mixed with the raw input.
import("stdfaust.lib");
a     = hslider("[0]Blend (0 raw, 1 processed)", 0.55, 0, 1, 0.001) : si.smoo;
hp    = hslider("[1]Highpass Hz", 300, 20, 2000, 1) : si.smoo;
lp    = hslider("[2]Lowpass Hz", 3000, 200, 12000, 10) : si.smoo;
drive = hslider("[3]Drive", 0.35, 0, 1, 0.01) : si.smoo;
k     = 1 + drive * 9;
chain = fi.highpass(2, hp) : fi.lowpass(2, lp) : (\(x).(ma.tanh(k * x) / ma.tanh(k)));
process = _ <: (*(1 - a)), (chain : *(a)) :> _;
