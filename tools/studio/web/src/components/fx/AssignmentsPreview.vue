<script setup lang="ts">
import type { FxDiff, FxDiffRow, FxPreview } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'
import SectionCard from '../shared/SectionCard.vue'
import Flag from '../ui/Flag.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import { fxPreviewId, fxRenderUrl } from './previewUrl'

defineProps<{ diff: FxDiff | null; fallback: FxPreview | null; unsavedLabels: number }>()

const chainText = (c: string[]) => (c.length ? c.join(' + ') : 'no effect')
/** Raw sample when the chain is empty, otherwise the sample rendered through the chain. */
const clip = (r: FxDiffRow, chain: string[]) => (!r.sample_wav ? { id: null, src: undefined } : chain.length ? { id: fxPreviewId(chain, r.sample_wav), src: fxRenderUrl(chain, r.sample_wav) } : { id: r.sample_wav, src: undefined })
const afterText = (r: FxDiffRow) => (r.changed ? chainText(r.after) : 'unchanged')
</script>

<template>
  <SectionCard title="Assignments preview" summary="what each voice gets after Write · changed rows first">
    <p v-if="unsavedLabels" class="note"><Flag>note</Flag> This preview reads the saved label map. {{ unsavedLabels }} unsaved {{ unsavedLabels === 1 ? 'label is' : 'labels are' }} not reflected until you Write.</p>
    <template v-if="diff">
      <p v-for="(n, label) in diff.unmapped_labels" :key="label" class="warn">{{ n }} {{ n === 1 ? 'line uses' : 'lines use' }} “{{ label }}”, which has no preset yet.</p>
      <EmptyState v-if="!diff.rows.length" message="No voice has an effect label or an existing assignment." />
      <div v-else class="tbl-wrap">
        <table class="tbl">
          <thead><tr><th>Voice</th><th class="hide-sm">Labels</th><th>Now</th><th>After write</th><th class="listen"><span class="vh">Listen</span></th></tr></thead>
          <tbody>
            <tr v-for="r in diff.rows" :key="r.voice" :data-changed="r.changed">
              <td class="who">{{ r.speaker }}<span v-if="r.lines" class="muted lines"> · {{ r.lines }}</span></td>
              <td class="mono hide-sm">{{ r.labels.join(', ') || '–' }}</td>
              <td class="muted">{{ chainText(r.now) }}</td>
              <td :class="r.changed ? 'chg' : 'muted'">{{ afterText(r) }}</td>
              <td class="listen">
                <span v-if="r.changed || r.after.length" class="ab">
                  <InlinePlay v-bind="clip(r, r.now)" title="Now" :subtitle="`${r.speaker} · ${chainText(r.now)}`" :unavailable-reason="r.sample_wav ? undefined : 'No rendered clip for this voice'" />
                  <InlinePlay v-bind="clip(r, r.after)" title="After write" :subtitle="`${r.speaker} · ${chainText(r.after)}`" :unavailable-reason="r.sample_wav ? undefined : 'No rendered clip for this voice'" />
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="muted foot">The two play buttons are Now and After write on the same clip.</p>
    </template>
    <template v-else-if="fallback">
      <p>{{ fallback.lines }} lines and {{ fallback.speakers }} speakers would get FX.</p>
      <p v-for="(n, label) in fallback.unmapped_labels" :key="label" class="warn">{{ n }} {{ n === 1 ? 'line uses' : 'lines use' }} “{{ label }}”, which has no preset yet.</p>
    </template>
    <EmptyState v-else message="The per-voice preview needs the newer studio server (GET /api/fx/assignments/diff)." />
  </SectionCard>
</template>

<style scoped>
.note, .warn { margin: 0 0 var(--s-2); font-size: var(--fs-sm); }
.warn { color: var(--warn); }
.who { font-weight: 600; white-space: nowrap; }
.lines { font-weight: 400; }
.chg { color: var(--warn); }
.listen { width: 90px; }
.ab { display: inline-flex; gap: var(--s-2); }
.foot { margin: var(--s-2) 0 0; font-size: var(--fs-sm); }
</style>
