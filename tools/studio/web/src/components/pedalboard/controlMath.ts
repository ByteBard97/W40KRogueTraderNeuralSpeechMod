// Slider maths shared with the FX Lab page (tools/fx_lab/index.html): frequency and time controls get a
// squared curve so the low end has finer steps.
import type { CatalogControl } from '../../pedalboard/types'

export const SLIDER_STEPS = 1000
const SKEWED_LABEL = /\b(Hz|ms)\b/
const SKEW_POWER = 2
const WHEEL_STEP = 0.02
const WHEEL_STEP_FINE = 0.004

const skewOf = (c: CatalogControl) => (SKEWED_LABEL.test(c.label) ? SKEW_POWER : 1)
const clamp = (c: CatalogControl, v: number) => Math.min(c.max, Math.max(c.min, v))

/** Value to 0..1 slider position. */
export function toT(c: CatalogControl, v: number): number {
  const span = c.max - c.min
  if (span <= 0) return 0
  return Math.pow(Math.min(1, Math.max(0, (v - c.min) / span)), 1 / skewOf(c))
}

/** 0..1 slider position to a value snapped to the control's step. */
export function fromT(c: CatalogControl, t: number): number {
  let v = c.min + (c.max - c.min) * Math.pow(Math.min(1, Math.max(0, t)), skewOf(c))
  // toFixed strips float noise such as 0.30000000000000004 after snapping to a decimal step.
  if (c.step) v = Number((Math.round(v / c.step) * c.step).toFixed(decimalsOf(c)))
  return clamp(c, v)
}

/** New value after one mouse-wheel notch; scrolling up raises the value. */
export function wheelValue(c: CatalogControl, v: number, deltaY: number, fine: boolean): number {
  const step = fine ? WHEEL_STEP_FINE : WHEEL_STEP
  return fromT(c, toT(c, v) - Math.sign(deltaY) * step)
}

/** Digits to show after the decimal point for a control's step. */
export function decimalsOf(c: CatalogControl): number {
  const s = String(c.step)
  const dot = s.indexOf('.')
  return dot < 0 ? 0 : s.length - dot - 1
}
