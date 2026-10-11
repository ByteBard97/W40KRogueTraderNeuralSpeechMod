<script setup lang="ts">
import { computed } from 'vue'
import type { MatchRowData } from '../../api/types'
import { entryName, plural, whyFlagged } from '../../utils/matchText'
import Btn from '../ui/Btn.vue'
import Icon from '../ui/Icon.vue'
import Tag from '../ui/Tag.vue'

/** The match under review: both sides, why it was flagged, sample lines, and the accept / reject buttons. */
const props = defineProps<{ row: MatchRowData; position: string; hearing: boolean }>()
defineEmits<{ decide: [value: 'accept' | 'reject']; hear: []; prev: []; next: [] }>()

const attrs = computed(() => [props.row.gender, props.row.species, props.row.role].filter((x): x is string => !!x))
const why = computed(() => whyFlagged(props.row))
const canHear = computed(() => !!props.row.has_bank && !!props.row.speaker_sample)
const hearReason = computed(() => (!props.row.has_bank ? 'No voice bank for this speaker' : 'No sample clip for this speaker'))
const samples = computed(() => props.row.samples.map((text, i) => ({ text, gap: i > 0 && !!props.row.gaps[i - 1] })).filter((s) => s.text))
</script>

<template>
  <section class="detail" aria-label="Current match">
    <div class="match-head">
      <span class="from">{{ entryName(row) }}</span>
      <span class="arrow" aria-hidden="true">→</span>
      <span class="to">{{ row.speaker }}</span>
      <Tag :variant="row.has_bank ? 'bank' : 'nobank'">{{ row.has_bank ? 'bank' : 'no bank' }}</Tag>
      <span class="muted num pos">{{ position }}</span>
    </div>

    <div class="sides">
      <div>
        <div class="cap">Roster entry</div>
        <div class="attr"><Tag v-for="a in attrs" :key="a">{{ a }}</Tag></div>
        <div class="mono muted src">{{ row.conversation }} · {{ plural(row.lines, 'line') }}</div>
      </div>
      <div>
        <div class="cap">Proposed speaker</div>
        <div class="attr"><Tag>game gender {{ row.game_gender ?? '?' }}</Tag><Tag>{{ plural(row.speaker_lines, 'line') }}</Tag></div>
        <Btn size="sm" class="hear" kbd="Space" :pressed="hearing" :disabled="!canHear" :title="canHear ? undefined : hearReason" @click="$emit('hear')">
          <Icon name="play" :size="10" />Hear {{ row.speaker }}
        </Btn>
      </div>
    </div>

    <div v-if="why" class="why" role="note">
      <Icon name="warn" :size="16" class="why-ico" />
      <div><b>Why flagged</b><div>{{ why }}</div></div>
    </div>

    <div>
      <div class="cap">Sample lines</div>
      <template v-for="(s, i) in samples" :key="i">
        <div v-if="s.gap" class="muted gap">… other speakers' lines in between</div>
        <p class="sample">{{ s.text }}</p>
      </template>
      <p v-if="!samples.length" class="muted sample">No sample text for this entry.</p>
      <details v-if="row.evidence.length">
        <summary class="muted">Evidence</summary>
        <ul class="evidence"><li v-for="(e, i) in row.evidence" :key="i">{{ e }}</li></ul>
      </details>
    </div>

    <div class="judge">
      <Btn variant="good" size="lg" class="big" kbd="A" :pressed="row.decision === 'accept'" @click="$emit('decide', 'accept')">
        <Icon name="check" :size="18" />Accept {{ row.speaker }}
      </Btn>
      <Btn variant="danger" size="lg" class="big" kbd="R" :pressed="row.decision === 'reject'" @click="$emit('decide', 'reject')">
        <Icon name="x" :size="18" />Reject
      </Btn>
    </div>

    <div class="foot">
      <span v-if="row.suggest" class="muted" :title="row.suggest_reason">Suggested: <b class="sug">{{ row.suggest === 'accept' ? 'Accept' : 'Reject' }}</b></span>
      <span class="nav">
        <Btn variant="ghost" kbd="K" @click="$emit('prev')">Previous</Btn>
        <Btn kbd="N" @click="$emit('next')">Next unreviewed</Btn>
      </span>
    </div>
  </section>
</template>

<style scoped>
.detail { display: flex; flex-direction: column; gap: var(--s-4); padding: var(--s-5); border-radius: var(--r-lg); background: var(--surface); border: 1px solid var(--line); min-width: 0; }
.match-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); }
.from, .to { font-size: 22px; font-weight: 600; overflow-wrap: anywhere; }
.to { color: var(--accent-hi); }
.arrow { color: var(--text-3); font-size: 22px; line-height: 1; }
.pos { font-size: var(--fs-sm); margin-left: auto; }
.sides { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr)); gap: var(--s-3); }
.cap { font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--text-3); margin-bottom: var(--s-1); }
.attr { display: flex; flex-wrap: wrap; gap: 6px; }
.src { margin-top: 6px; overflow-wrap: anywhere; }
.hear { margin-top: 6px; }
.hear[aria-pressed="true"] { border-color: var(--accent); color: var(--accent-hi); }
.why { display: flex; gap: var(--s-2); align-items: flex-start; padding: 10px 12px; border-radius: var(--r-md); background: var(--warn-tint); border: 1px solid var(--warn-line); font-size: 13px; }
.why-ico { color: var(--warn); flex: none; margin-top: 2px; }
.sample { font-size: 15px; line-height: 1.55; padding: 10px 0; margin: 0; border-top: 1px solid var(--line); }
.gap { font-size: var(--fs-sm); padding-top: var(--s-2); }
summary { cursor: pointer; font-size: var(--fs-sm); padding-top: 6px; }
.evidence { font-size: var(--fs-md); color: var(--text-2); margin: 0; padding: var(--s-1) 0 0 18px; }
.evidence li + li { margin-top: 4px; }
.judge { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--s-3); margin-top: var(--s-1); }
.big { min-height: var(--hit-xl); font-size: 17px; font-weight: 600; border-width: 1.5px; border-radius: var(--r-lg); }
.big.v-good { background: var(--good-tint); }
.big.v-danger { background: var(--bad-tint); }
.big.v-good[aria-pressed="true"] { background: var(--good); color: var(--good-ink); border-color: var(--good); }
.big.v-danger[aria-pressed="true"] { background: var(--bad); color: var(--bad-ink); border-color: var(--bad); }
.foot { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; font-size: 13px; }
.sug { color: var(--text); }
.nav { margin-left: auto; display: flex; gap: var(--s-2); }
@media (max-width: 480px) { .detail { padding: var(--s-4); } .big { min-height: 56px; } .nav { margin-left: 0; } }
</style>
