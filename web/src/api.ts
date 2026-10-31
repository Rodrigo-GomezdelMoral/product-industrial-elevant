export type Flag = 'missing' | 'low_confidence' | 'ambiguous' | 'no_match' | 'invalid_code' | 'invalid_quantity'
export type Field = 'lift_id' | 'location' | 'inspection_date' | 'technician'
export type State = 'drafting' | 'review' | 'approved' | 'failed'
export type Version = { name: string; sha256: string }
export type Line = {
  number: number; defect: { page: number; row: number; text: string } | null; expanded: string; item_code: string | null
  description: string; unit: string; quantity: string; unit_price: string | null; amount: string | null; candidates: string[]
  flag: Flag | null; reason: string; outcome: 'proposed' | 'accepted' | 'changed' | 'removed' | 'added'
}
export type Quote = {
  id: string; state: State; catalogue: Version; template: Version; header: Record<Field, string | null>
  header_flags: Partial<Record<Field, Flag>>; lines: Line[]; vat_rate: string; subtotal: string; vat: string; total: string
  events: { at: string; by: string; action: string; detail: string }[]; created_at: string; drafted_at: string | null
  approved_at: string | null; approved_by: string | null
}
export type Edit = {
  action: 'accept' | 'item' | 'quantity' | 'remove' | 'add' | 'header'
  line?: number | null; code?: string | null; quantity?: number | null; field?: Field | null; value?: string | null
}
export type Item = { code: string; description: string; unit: string; unit_price: string }
export type Reviewed = { quote: Quote; error: string | null }
export type Recording = {
  title: string; file: string; suggestion?: string; status: [string, number][]; draft: Quote; catalogue: Item[]; document: string
  steps: { edits: Edit[]; approve: boolean; ms: number; quote: Quote; error: string | null }[]
  corrections: { text: string; edits: Edit[]; ms: number }[]
}

export class Refusal extends Error {}

export const DEMO = import.meta.env.VITE_DEMO === 'true'
export const BASE = import.meta.env.BASE_URL
export const NEEDS_SYSTEM = 'That needs the deployed system: this demo replays recorded runs, so use the suggestions.'
export const RECORDINGS: Recording[] = DEMO
  ? Object.values(import.meta.glob<Recording>('../fixtures/*.json', { eager: true, import: 'default' }))
  : []
export const FIELDS: Record<Field, string> = { lift_id: 'Lift ID', location: 'Location', inspection_date: 'Inspection date', technician: 'Technician' }

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const pdf = body instanceof Blob
  const headers = body === undefined ? undefined : { 'Content-Type': pdf ? 'application/pdf' : 'application/json' }
  const response = await fetch(path, { method, headers, body: pdf ? body : JSON.stringify(body) }).catch(() => {
    throw new Refusal('Elevant is not reachable; check the connection and try again')
  })
  if (response.ok) return response
  const detail: unknown = await response.json().then((json: { detail?: unknown }) => json.detail, () => null)
  throw new Refusal(typeof detail === 'string' ? detail : `the request failed with status ${response.status}`)
}

const json = async <T>(method: string, path: string, body?: unknown): Promise<T> =>
  (await send(method, path, body)).json() as Promise<T>

async function* events(response: Response): AsyncGenerator<[string, unknown]> {
  const reader = response.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (let chunk = await reader.read(); !chunk.done; chunk = await reader.read()) {
    const blocks = (buffer + chunk.value.replaceAll('\r', '')).split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const event = /^event: (.*)$/m.exec(block)?.[1]
      const data = [...block.matchAll(/^data: (.*)$/gm)].map((match) => match[1]).join('\n')
      if (event && data) yield [event, JSON.parse(data)]
    }
  }
}

export const live = {
  me: () => json<{ name: string; roles: string[] }>('GET', '/api/me'),
  list: () => json<{ id: string; state: State; lift_id?: string | null }[]>('GET', '/api/quotes'),
  get: (id: string) => json<Quote>('GET', `/api/quotes/${id}`),
  upload: async function* (file: File) {
    yield* events(await send('POST', '/api/quotes', file))
  },
  review: (id: string, edits: Edit[], approve: boolean) => json<Reviewed>('POST', `/api/quotes/${id}/review`, { edits, approve }),
  correct: (id: string, text: string) => json<Edit[]>('POST', `/api/quotes/${id}/corrections`, { text }),
  catalogue: (id: string) => json<Item[]>('GET', `/api/quotes/${id}/catalogue`),
  feedback: async (id: string, value: 'up' | 'down') => void (await send('POST', `/api/quotes/${id}/feedback`, { value })),
  document: (id: string) => `/api/quotes/${id}/document`,
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, Math.max(ms, 0)))
const played = new Map<string, number>()
const recording = (id: string) => RECORDINGS.find((run) => run.draft.id === id)!

const demo: Omit<typeof live, 'list' | 'get'> = {
  me: async () => ({ name: 'Demo visitor', roles: ['Quote.Estimator'] }),
  upload: async function* (file: File) {
    const run = RECORDINGS.find((candidate) => candidate.file === file.name)
    if (!run) throw new Refusal(NEEDS_SYSTEM)
    let elapsed = 0
    for (const [text, ms] of run.status) {
      await pause(ms - elapsed)
      elapsed = ms
      yield ['status', text]
    }
    await pause(Date.parse(run.draft.drafted_at ?? run.draft.created_at) - Date.parse(run.draft.created_at) - elapsed)
    played.set(run.draft.id, 0)
    yield ['quote', run.draft]
  },
  review: async (id, edits, approve) => {
    const next = played.get(id) ?? 0
    const step = recording(id).steps[next]
    if (!step) throw new Refusal('The recorded run ends here.')
    if (JSON.stringify([step.edits, step.approve]) !== JSON.stringify([edits, approve])) {
      const recorded = [...step.edits.map(describe), ...(step.approve ? ['Approve'] : [])].join('; ')
      throw new Refusal(`The recorded run did something else next: ${recorded}.`)
    }
    await pause(step.ms)
    played.set(id, next + 1)
    return { quote: step.quote, error: step.error }
  },
  correct: async (id, text) => {
    const found = recording(id).corrections.find((correction) => correction.text === text)
    if (!found) throw new Refusal(NEEDS_SYSTEM)
    await pause(found.ms)
    return found.edits
  },
  catalogue: async (id) => recording(id).catalogue,
  feedback: async () => undefined,
  document: (id) => `${BASE}demo/${recording(id).document}`,
}

export const api = DEMO ? demo : live

export function describe(edit: Edit): string {
  const line = `Line ${edit.line}`
  const said: Record<Edit['action'], string> = {
    accept: `Accept line ${edit.line}`, item: `${line}: use ${edit.code}`, quantity: `${line}: quantity ${edit.quantity}`,
    remove: `Remove line ${edit.line}`, add: `Add ${edit.code} × ${edit.quantity}`,
    header: `${edit.field ? FIELDS[edit.field] : 'Header'}: ${edit.value}`,
  }
  return said[edit.action]
}
