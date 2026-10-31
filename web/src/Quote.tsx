import { Check, CircleCheck, Copy, Download, LoaderCircle, ThumbsDown, ThumbsUp, TriangleAlert, X } from 'lucide-react'
import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { api, describe, FIELDS, type Edit, type Field, type Flag, type Item, type Line, type Quote, type State } from './api'

export type Review = (edits: Edit[], approve?: boolean) => void

export const PLAIN = { allowedElements: ['p', 'strong', 'code'], unwrapDisallowed: true }
export const STATES: Record<State, string> = { drafting: 'Drafting', review: 'In review', approved: 'Approved', failed: 'Failed' }
const FLAGS: Record<Flag, string> = {
  missing: 'Missing', low_confidence: 'Low confidence', ambiguous: 'Ambiguous', no_match: 'No match',
  invalid_code: 'Invalid code', invalid_quantity: 'Invalid quantity',
}
const EURO = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' })
const euro = (value: string | null) => (value === null ? '—' : EURO.format(Number(value)))
const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Madrid' }) : '—'
const kept = (quote: Quote) => quote.lines.filter((line) => line.outcome !== 'removed')
const text = (line: Line) => line.expanded || line.defect?.text || 'Added by the estimator'
const vat = (quote: Quote) => `VAT ${Math.round(Number(quote.vat_rate) * 100)} %`
const fieldFlag = (quote: Quote, field: Field): Flag | undefined =>
  quote.header_flags[field] ?? (quote.header[field]?.trim() ? undefined : 'missing')

function openFlags(quote: Quote): string[] {
  const header = (Object.keys(FIELDS) as Field[]).filter((field) => fieldFlag(quote, field)).map((field) => FIELDS[field])
  const lines = kept(quote).filter((line) => line.flag).map((line) => `line ${line.number}`)
  return [...header, ...lines, ...(kept(quote).length ? [] : ['the quote has no lines'])]
}

function summary(quote: Quote): string {
  const { lift_id, location, inspection_date, technician } = quote.header
  const flagged = kept(quote).filter((line) => line.flag).length
  return [
    `**Lift ${lift_id ?? '(ID missing)'}** · ${location ?? '(location missing)'} · inspected ${inspection_date ?? '(date missing)'} by ${technician ?? '(technician missing)'}`,
    `${kept(quote).length} lines, ${flagged ? `**${flagged} flagged**` : 'none flagged'}. Subtotal ${euro(quote.subtotal)} · ${vat(quote)} ${euro(quote.vat)} · **Total ${euro(quote.total)}**`,
  ].join('\n\n')
}

function table(quote: Quote): string {
  const rows = kept(quote).map((line) => `| ${line.number} | ${text(line)} | ${line.item_code ?? ''} | ${line.quantity} | ${euro(line.amount)} |`)
  return ['| # | Defect | Item | Quantity | Amount |', '|---|---|---|---|---|', ...rows].join('\n')
}

function FlagWord({ flag }: { flag?: Flag | null }) {
  return flag ? <span className="flag"><TriangleAlert size={16} aria-hidden /> {FLAGS[flag]}</span> : null
}

function Commit({ value, label, onCommit, number = false }: { value: string; label?: string; onCommit: (value: string) => void; number?: boolean }) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  const commit = () => draft.trim() && draft.trim() !== value && onCommit(draft.trim())
  const kind = number ? { type: 'number', min: '0', step: 'any', inputMode: 'decimal' as const } : {}
  return <input aria-label={label} value={draft} {...kind} onChange={(event) => setDraft(event.target.value)} onBlur={commit} onKeyDown={(event) => event.key === 'Enter' && commit()} />
}

function Row({ line, editing, review, names }: { line: Line; editing: boolean; review: Review; names: Map<string, string> }) {
  const n = line.number
  const live = line.outcome !== 'removed'
  const acceptable = live && line.outcome === 'proposed' && line.item_code !== null && [null, 'low_confidence'].includes(line.flag)
  const choosing = editing && live && line.candidates.length > 0 && (line.flag !== null || line.outcome === 'changed')
  const search = (event: KeyboardEvent<HTMLInputElement>) => {
    const code = event.currentTarget.value.trim()
    if (event.key !== 'Enter' || !code) return
    review([{ action: 'item', line: n, code }])
    event.currentTarget.value = ''
  }
  return (
    <tr className={live ? undefined : 'removed'}>
      <td>{n}</td>
      <td>{text(line)}{line.defect && <small>page {line.defect.page}, row {line.defect.row}</small>}</td>
      <td>
        {line.item_code ?? '—'}
        <small>{line.description || names.get(line.item_code ?? '')}</small>
        {choosing && (
          <span className="candidates">
            {line.candidates.map((code) => (
              <button key={code} type="button" aria-pressed={code === line.item_code} aria-label={`Choose ${code} ${names.get(code) ?? ''} for line ${n}`} onClick={() => code !== line.item_code && review([{ action: 'item', line: n, code }])}>{code}</button>
            ))}
          </span>
        )}
        {editing && live && <input list="catalogue" aria-label={`Search the catalogue for line ${n}`} placeholder="Search the catalogue" onKeyDown={search} />}
      </td>
      <td>{editing && live ? <Commit number label={`Quantity for line ${n}`} value={String(Number(line.quantity))} onCommit={(value) => review([{ action: 'quantity', line: n, quantity: Number(value) }])} /> : `${Number(line.quantity)} ${line.unit}`}</td>
      <td>{euro(line.unit_price)}</td>
      <td>{euro(line.amount)}</td>
      <td>{live ? <FlagWord flag={line.flag} /> : 'Removed'}{line.flag && line.reason && <small>{line.reason}</small>}</td>
      {editing && (
        <td>
          <span className="row-actions">
            <button type="button" aria-label={`Accept line ${n}`} aria-disabled={!acceptable} onClick={() => acceptable && review([{ action: 'accept', line: n }])}><Check size={16} aria-hidden /></button>
            <button type="button" aria-label={`Remove line ${n}`} aria-disabled={!live} onClick={() => live && review([{ action: 'remove', line: n }])}><X size={16} aria-hidden /></button>
          </span>
        </td>
      )}
    </tr>
  )
}

function Lines({ quote, items, review, problem }: { quote: Quote; items: Item[]; review: Review; problem?: string }) {
  const editing = quote.state === 'review'
  const open = openFlags(quote)
  const names = new Map(items.map((item) => [item.code, item.description]))
  const add = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    review([{ action: 'add', code: String(form.get('code')).trim(), quantity: Number(form.get('quantity')) }])
    event.currentTarget.reset()
  }
  const total = (label: string, value: string, strong = false) => (
    <tr className={strong ? 'total' : undefined}>
      <th scope="row" colSpan={5}>{label}</th>
      <td>{euro(value)}</td>
      <td colSpan={editing ? 2 : 1} />
    </tr>
  )
  return (
    <section className="card" aria-labelledby={`lines-${quote.id}`}>
      <h2 id={`lines-${quote.id}`}>{editing ? 'Review the draft' : 'Quote lines'}</h2>
      {editing && (
        <div className="fields">
          {(Object.keys(FIELDS) as Field[]).map((field) => (
            <label key={field}>
              <span>{FIELDS[field]} <FlagWord flag={fieldFlag(quote, field)} /></span>
              <Commit value={quote.header[field] ?? ''} onCommit={(value) => review([{ action: 'header', field, value }])} />
            </label>
          ))}
        </div>
      )}
      <datalist id="catalogue">
        {items.map((item) => <option key={item.code} value={item.code}>{`${item.description} · ${item.unit} · ${euro(item.unit_price)}`}</option>)}
      </datalist>
      <div className="scroll" role="region" aria-label="Quote lines" tabIndex={0}>
        <table>
          <thead>
            <tr>
              {['#', 'Defect', 'Item', 'Quantity', 'Unit price', 'Amount', 'Flag', ...(editing ? ['Actions'] : [])].map((name) => <th key={name} scope="col">{name}</th>)}
            </tr>
          </thead>
          <tbody>
            {quote.lines.map((line) => <Row key={line.number} line={line} editing={editing} review={review} names={names} />)}
          </tbody>
          <tfoot>
            {total('Subtotal', quote.subtotal)}
            {total(vat(quote), quote.vat)}
            {total('Total', quote.total, true)}
          </tfoot>
        </table>
      </div>
      {editing && (
        <form className="add" onSubmit={add}>
          <input name="code" list="catalogue" aria-label="Item to add" placeholder="Add an item from the catalogue" required />
          <input name="quantity" type="number" min="0" step="any" defaultValue="1" aria-label="Quantity to add" required />
          <button type="submit">Add line</button>
        </form>
      )}
      {problem && <p className="problem" role="alert"><TriangleAlert size={16} aria-hidden /> {problem}</p>}
      {editing && (
        <div className="approve">
          <button type="button" className="primary" aria-disabled={open.length > 0} aria-describedby={`open-${quote.id}`} onClick={() => open.length === 0 && review([], true)}>Approve</button>
          <span id={`open-${quote.id}`}>{open.length ? `Resolve first: ${open.join(', ')}` : 'Every flag is resolved.'}</span>
        </div>
      )}
    </section>
  )
}

function Approved({ quote }: { quote: Quote }) {
  const download = useRef<HTMLAnchorElement>(null)
  useEffect(() => {
    if (document.activeElement === document.body) download.current?.focus()
  }, [])
  return (
    <section className="card" aria-labelledby={`approved-${quote.id}`}>
      <h2 id={`approved-${quote.id}`}><CircleCheck size={20} className="ok" aria-hidden /> Approved</h2>
      <p>
        Approved by {quote.approved_by} on {when(quote.approved_at)}. Each line of the Word quote carries its catalogue code, the
        catalogue version and the report page and row.
      </p>
      <a ref={download} className="button primary" href={api.document(quote.id)} download={`${quote.id}.docx`}><Download size={16} aria-hidden /> Download quote (.docx)</a>
      <dl className="trace">
        <dt>Catalogue</dt>
        <dd>{`${quote.catalogue.name} · SHA-256 ${quote.catalogue.sha256.slice(0, 12)}`}</dd>
        <dt>Template</dt>
        <dd>{`${quote.template.name} · SHA-256 ${quote.template.sha256.slice(0, 12)}`}</dd>
        <dt>Drafted</dt>
        <dd>{when(quote.drafted_at)}</dd>
      </dl>
      <details>
        <summary>History: {quote.events.length} recorded changes</summary>
        <ol>{quote.events.map((event, index) => <li key={index}>{`${when(event.at)} · ${event.by} · ${event.action} ${event.detail}`}</li>)}</ol>
      </details>
    </section>
  )
}

type Answered = { status: string[]; busy: boolean; error?: string; quote?: Quote; review: Review; problem?: string }

export function Answer({ status, busy, error, quote, review, problem }: Answered) {
  const [items, setItems] = useState<Item[]>([])
  const [rated, setRated] = useState<'up' | 'down'>()
  const [said, setSaid] = useState('')
  const id = quote?.id
  const editing = quote?.state === 'review'
  useEffect(() => (setRated(undefined), setSaid('')), [id])
  useEffect(() => {
    if (id && editing) api.catalogue(id).then(setItems, () => setItems([]))
  }, [id, editing])
  const rate = (value: 'up' | 'down') =>
    id && api.feedback(id, value).then(() => (setRated(value), setSaid('Thanks for the rating.')), (failure: Error) => setSaid(failure.message))
  const copy = () =>
    quote && Promise.resolve().then(() => navigator.clipboard.writeText(`${summary(quote)}\n\n${table(quote)}`)).then(() => setSaid('Copied.'), () => setSaid('This browser does not allow copying here.'))
  return (
    <article className="turn" aria-label="Elevant">
      <p className="by">Elevant</p>
      <div aria-live="polite">
        <ul className="status">
          {status.map((step, index) => <li key={index}>{step}…{busy && index === status.length - 1 && <LoaderCircle size={16} className="spin" aria-hidden />}</li>)}
        </ul>
        {quote && <Markdown {...PLAIN}>{summary(quote)}</Markdown>}
      </div>
      {error && <p className="problem card" role="alert"><TriangleAlert size={16} aria-hidden /> {error}</p>}
      {quote && (
        <>
          <Lines quote={quote} items={items} review={review} problem={problem} />
          {quote.state === 'approved' && <Approved quote={quote} />}
          <div className="after">
            <button type="button" aria-label="Copy the quote as Markdown" onClick={copy}><Copy size={16} aria-hidden /></button>
            <button type="button" aria-label="Good draft" aria-pressed={rated === 'up'} onClick={() => rate('up')}><ThumbsUp size={16} aria-hidden /></button>
            <button type="button" aria-label="Poor draft" aria-pressed={rated === 'down'} onClick={() => rate('down')}><ThumbsDown size={16} aria-hidden /></button>
            <span aria-live="polite">{said}</span>
          </div>
        </>
      )}
      <hr />
    </article>
  )
}

export function Proposal({ edits, state, confirm, dismiss }: { edits: Edit[]; state: 'open' | 'applied' | 'dismissed'; confirm: () => void; dismiss: () => void }) {
  return (
    <article className="turn" aria-label="Elevant">
      <p className="by">Elevant</p>
      <section className="card" aria-label="Proposed correction">
        <p>I propose these changes. Nothing changes until you confirm.</p>
        <ul>{edits.map((edit, index) => <li key={index}>{describe(edit)}</li>)}</ul>
        {state === 'open' ? (
          <div className="approve">
            <button type="button" className="primary" onClick={confirm}>Confirm</button>
            <button type="button" onClick={dismiss}>Dismiss</button>
          </div>
        ) : (
          <p className="muted" role="status">{state === 'applied' ? 'Applied.' : 'Dismissed.'}</p>
        )}
      </section>
      <hr />
    </article>
  )
}
