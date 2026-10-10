const TYPING_TAGS = ['INPUT', 'SELECT', 'TEXTAREA']

/** True when a key event came from somewhere the user is typing, so global shortcuts must stay out of the way. */
export function isTypingTarget(t: EventTarget | null): boolean {
  const el = t as HTMLElement | null
  return !!el && (TYPING_TAGS.includes(el.tagName) || !!el.isContentEditable)
}

/** After a mouse click on a play control, drop focus so the global Space key plays/pauses instead of re-pressing the button. Keyboard activation (detail 0) keeps focus. */
export function blurAfterPointer(e: MouseEvent) {
  if (e.detail > 0) (e.currentTarget as HTMLElement | null)?.blur()
}

/** Like blurAfterPointer, for a container: after a mouse click on a button inside it, drop that button's focus. */
export function blurClickedButton(e: MouseEvent) {
  if (e.detail > 0) (e.target as HTMLElement | null)?.closest('button')?.blur()
}
