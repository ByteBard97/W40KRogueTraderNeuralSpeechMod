import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AssignmentsPreview from './AssignmentsPreview.vue'

const row = (o: object) => ({ voice: 'slot:a', kind: 'slot', speaker: 'Pool A', labels: ['machine'], lines: 4, now: [], after: ['Clean'], changed: true, changed_lines: 4, sample_wav: 'data/render/export/a.wav', ...o })
const diff = { rows: [row({}), row({ voice: 'speaker:Idira', speaker: 'Idira', changed: false, now: ['Mine'], after: ['Mine'], sample_wav: null })], changed: 1, unmapped_labels: { helmet: 2 }, file_mtime: null }

describe('AssignmentsPreview', () => {
  it('lists changed rows with before and after, and warns about unmapped labels', () => {
    const w = mount(AssignmentsPreview, { props: { diff, fallback: null, unsavedLabels: 0 } })
    const rows = w.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Pool A')
    expect(rows[0].text()).toContain('no effect')
    expect(rows[0].text()).toContain('Clean')
    expect(rows[1].text()).toContain('unchanged')
    expect(w.text()).toContain('“helmet”')
  })

  it('says the preview reads the saved map when labels are unsaved', () => {
    const w = mount(AssignmentsPreview, { props: { diff, fallback: null, unsavedLabels: 2 } })
    expect(w.text()).toContain('2 unsaved labels are not reflected')
  })

  it('A/B buttons are disabled without a rendered clip', () => {
    const w = mount(AssignmentsPreview, { props: { diff, fallback: null, unsavedLabels: 0 } })
    const idira = w.findAll('tbody tr')[1].findAll('button')
    expect(idira.length).toBe(2)
    expect(idira.every((b) => b.attributes('disabled') !== undefined)).toBe(true)
    expect(w.findAll('tbody tr')[0].findAll('button')[0].attributes('disabled')).toBeUndefined()
  })

  it('degrades to the counts, then to a plain message, when the diff route is missing', () => {
    const fb = { lines: 7, speakers: 2, unmapped_labels: {}, sample: [] }
    expect(mount(AssignmentsPreview, { props: { diff: null, fallback: fb, unsavedLabels: 0 } }).text()).toContain('7 lines and 2 speakers')
    expect(mount(AssignmentsPreview, { props: { diff: null, fallback: null, unsavedLabels: 0 } }).text()).toContain('newer studio server')
  })
})
