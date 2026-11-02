import { ArrowUp, CircleUserRound, FileText, LogOut, Menu, Paperclip, Search, SquarePen, X } from 'lucide-react'
import { type KeyboardEvent, useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { api, BASE, DEMO, live, NEEDS_SYSTEM, RECORDINGS, type Edit, type Quote, type Recording, type State } from './api'
import { Answer, PLAIN, Proposal, STATES } from './Quote'

type Turn =
  | { kind: 'user'; text: string }
  | { kind: 'answer'; status: string[]; busy: boolean; error?: string }
  | { kind: 'proposal'; edits: Edit[]; state: 'open' | 'applied' | 'dismissed' }
  | { kind: 'note'; text: string }
type Chat = { key: string; title: string; state?: State; quote?: Quote; turns: Turn[]; problem?: string }

const SAMPLE = 'report-0108.pdf'
const reason = (error: unknown) => (error instanceof Error ? error.message : String(error))
const title = (quote: Quote) => quote.header.lift_id ?? 'Lift ID missing'
const recorded = (): Chat[] => RECORDINGS.map((run) => ({ key: run.draft.id, title: run.title, turns: [] }))

export function App() {
  const [chats, setChats] = useState<Chat[]>(recorded)
  const [selected, setSelected] = useState<string>()
  const [user, setUser] = useState<{ name: string; roles: string[] }>({ name: '', roles: [] })
  const [query, setQuery] = useState<string>()
  const [menu, setMenu] = useState(false)
  const [text, setText] = useState('')
  const [file, setFile] = useState<File>()
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const picker = useRef<HTMLInputElement>(null)
  const composer = useRef<HTMLTextAreaElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const thread = useRef<HTMLDivElement>(null)
  const queue = useRef(Promise.resolve(true))
  const chat = chats.find((candidate) => candidate.key === selected)
  const recording = RECORDINGS.find((candidate) => candidate.draft.id === selected)

  const patch = (key: string, change: (chat: Chat) => Chat) =>
    setChats((all) => all.map((candidate) => (candidate.key === key ? change(candidate) : candidate)))
  const say = (key: string, ...turns: Turn[]) => patch(key, (current) => ({ ...current, turns: [...current.turns, ...turns] }))
  const listed = (rows: { id: string; state: State; lift_id?: string | null }[]) =>
    setChats((all) => [...all, ...rows.filter((row) => !all.some((known) => known.key === row.id)).map((row) => ({ key: row.id, title: row.lift_id ?? 'Lift ID missing', state: row.state, turns: [] }))])

  useEffect(() => {
    api.me().then(setUser, (error: unknown) => setNotice(reason(error)))
    if (!DEMO) live.list().then(listed, (error: unknown) => setNotice(reason(error)))
  }, [])
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
    if (document.activeElement === document.body) thread.current?.focus({ preventScroll: true })
  }, [chat?.turns.length])

  const play = (run: Recording) => {
    setSelected(run.draft.id)
    setMenu(false)
    setNotice('')
    if (!chats.find((candidate) => candidate.key === run.draft.id)?.turns.length) void upload(new File([], run.file), run.draft.id)
  }

  async function open(key: string) {
    const run = RECORDINGS.find((candidate) => candidate.draft.id === key)
    if (run) return play(run)
    setSelected(key)
    setMenu(false)
    setNotice('')
    if (DEMO || key.startsWith('new-') || chats.find((candidate) => candidate.key === key)?.quote) return
    try {
      const quote = await live.get(key)
      patch(key, (current) => ({ ...current, quote, state: quote.state, title: title(quote), turns: [{ kind: 'answer', status: [], busy: false }] }))
    } catch (error) {
      say(key, { kind: 'note', text: reason(error) })
    }
  }

  async function upload(report: File, into?: string) {
    if (busy) return
    let key = into ?? `new-${Date.now()}`
    if (!into) setChats((all) => [{ key, title: report.name, state: 'drafting', turns: [] }, ...all])
    setSelected(key)
    setBusy(true)
    say(key, { kind: 'user', text: `Uploaded \`${report.name}\`` }, { kind: 'answer', status: [], busy: true })
    const answer = (change: (turn: Turn & { kind: 'answer' }) => Turn, state?: State) =>
      patch(key, (current) => ({ ...current, state: state ?? current.state, turns: current.turns.map((turn) => (turn.kind === 'answer' ? change(turn) : turn)) }))
    const fail = (text: string) => answer((turn) => ({ ...turn, error: text }), 'failed')
    try {
      for await (const [event, data] of api.upload(report)) {
        if (event === 'status') answer((turn) => ({ ...turn, status: [...turn.status, String(data)] }))
        if (event === 'error') fail((data as { detail: string }).detail)
        if (event !== 'quote') continue
        const quote = data as Quote
        const from = key
        setChats((all) => all.filter((other) => other.key !== quote.id || other.key === from).map((other) => (other.key === from ? { ...other, key: quote.id, quote, state: quote.state, title: DEMO ? other.title : title(quote) } : other)))
        setSelected((current) => (current === from ? quote.id : current))
        key = quote.id
      }
    } catch (error) {
      fail(reason(error))
    } finally {
      answer((turn) => ({ ...turn, busy: false }))
      setBusy(false)
    }
  }

  function review(edits: Edit[], approve = false): Promise<boolean> {
    const key = chat?.quote ? chat.key : undefined
    if (!key) return Promise.resolve(false)
    const run = async () => {
      try {
        const { quote, error } = await api.review(key, edits, approve)
        patch(key, (current) => ({ ...current, quote, state: quote.state, problem: error ?? undefined, title: DEMO ? current.title : title(quote) }))
        return !error
      } catch (error) {
        patch(key, (current) => ({ ...current, problem: reason(error) }))
        return false
      }
    }
    return (queue.current = queue.current.then(run))
  }

  async function correct(words: string) {
    if (busy) return
    if (chat?.quote?.state !== 'review') return setNotice('Attach an inspection report (PDF) to start a quote, or open a quote in review to correct it.')
    const key = chat.key
    say(key, { kind: 'user', text: words })
    setBusy(true)
    try {
      say(key, { kind: 'proposal', edits: await api.correct(key, words), state: 'open' })
    } catch (error) {
      say(key, { kind: 'note', text: reason(error) })
    } finally {
      setBusy(false)
    }
  }

  const settle = (index: number, state: 'applied' | 'dismissed') => {
    composer.current?.focus()
    if (chat) patch(chat.key, (current) => ({ ...current, turns: current.turns.map((turn, at) => (at === index && turn.kind === 'proposal' ? { ...turn, state } : turn)) }))
  }

  function submit() {
    if (busy) return
    setNotice('')
    if (file) {
      setFile(undefined)
      return void upload(file)
    }
    const words = text.trim()
    if (!words) return
    setText('')
    if (DEMO && !recording?.corrections.some((correction) => correction.text === words)) return setNotice(NEEDS_SYSTEM)
    void correct(words)
  }

  const enter = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    submit()
  }

  async function sample() {
    const response = await fetch(`${BASE}samples/${SAMPLE}`).catch(() => null)
    if (!response?.ok) return setNotice('The sample report is not available; attach a PDF instead.')
    await upload(new File([await response.blob()], SAMPLE, { type: 'application/pdf' }))
  }

  const suggestions: [string, () => void][] = [
    ['Upload an inspection report', () => picker.current?.click()],
    ['Try a sample scanned report', () => void sample()],
    ['Open quotes in review', () => (setQuery('review'), setMenu(true))],
  ]
  const sent = (words: string) => chat?.turns.some((turn) => turn.kind === 'user' && turn.text === words)
  const pending = DEMO && chat?.quote?.state === 'review' ? (recording?.corrections ?? []).filter((correction) => !sent(correction.text)) : []
  const shown = chats.filter((item) => query === undefined || `${item.title} ${item.state ? STATES[item.state] : ''}`.toLowerCase().includes(query.trim().toLowerCase()))
  const alert = notice && <p className="status error" role="alert">{notice}</p>

  return (
    <div className="app">
      {DEMO && <header className="band">Demo mode · recorded runs from the deployed system</header>}
      <div className="layout">
        <button type="button" className="icon menu" aria-label="Quotes" aria-expanded={menu} onClick={() => setMenu(!menu)}><Menu size={20} /></button>
        <aside className={menu ? 'sidebar open' : 'sidebar'} aria-label="Quotes">
          <h1><img src={`${BASE}elevant-logo.svg`} alt="Elevant" height={28} /></h1>
          <div className="row">
            <button type="button" className="primary" onClick={() => (setSelected(undefined), setMenu(false), setNotice(''))}><SquarePen size={16} aria-hidden /> New chat</button>
            <button type="button" className="icon round" aria-label="Search quotes" aria-expanded={query !== undefined} onClick={() => setQuery(query === undefined ? '' : undefined)}><Search size={16} /></button>
          </div>
          {query !== undefined && <input className="search" aria-label="Search quotes by lift ID or state" autoFocus value={query} onChange={(event) => setQuery(event.target.value)} />}
          <nav aria-label="Quotes">
            <ul>
              {shown.map((item) => (
                <li key={item.key}>
                  <button type="button" className={item.key === selected ? 'item selected' : 'item'} aria-current={item.key === selected} onClick={() => void open(item.key)}>
                    <FileText size={16} aria-hidden /> <span>{item.title}{item.state && <small> · {STATES[item.state]}</small>}</span>
                  </button>
                </li>
              ))}
            </ul>
            {chats.length === 0 && <p className="status">No quotes yet.</p>}
          </nav>
          <div className="me">
            <CircleUserRound className="avatar" size={28} strokeWidth={1.5} aria-hidden />
            <span>{user.name || 'Signed out'}<small>{DEMO ? 'Demo' : user.roles.length ? 'User' : 'No Elevant role'}</small></span>
            {!DEMO && <a className="icon" href="/.auth/logout" aria-label="Sign out"><LogOut size={16} /></a>}
          </div>
        </aside>
        <main>
          {!chat?.turns.length ? (
            <div className="empty">
              <img src={`${BASE}elevant-icon.svg`} alt="" width={56} height={56} />
              <h2>Turn an inspection report into a priced quote you can trust.</h2>
              <div className="suggestions">
                {suggestions.map(([label, action]) => {
                  const run = RECORDINGS.find((candidate) => candidate.suggestion === label)
                  return <button type="button" key={label} className="suggestion" disabled={busy || (DEMO && !run)} onClick={run ? () => play(run) : action}>{label}</button>
                })}
              </div>
              {alert}
            </div>
          ) : (
            <div className="thread" role="log" aria-label="Conversation" aria-busy={busy} ref={thread} tabIndex={-1}>
              {chat.turns.map((turn, index) =>
                turn.kind === 'user' ? (
                  <div className="turn user" key={index}><CircleUserRound className="avatar" size={28} strokeWidth={1.5} aria-hidden /><Markdown {...PLAIN}>{turn.text}</Markdown></div>
                ) : turn.kind === 'answer' ? (
                  <Answer key={index} {...turn} quote={chat.quote} problem={chat.problem} review={(edits, approve) => void review(edits, approve)} />
                ) : turn.kind === 'proposal' ? (
                  <Proposal key={index} edits={turn.edits} state={turn.state} confirm={() => void review(turn.edits).then((done) => done && settle(index, 'applied'))} dismiss={() => settle(index, 'dismissed')} />
                ) : (
                  <p className="status error" key={index}>{turn.text}</p>
                ),
              )}
              {alert}
              <div ref={end} />
            </div>
          )}
          {(pending.length > 0 || file) && (
            <div className="chips">
              {pending.map((correction) => <button type="button" className="secondary" key={correction.text} onClick={() => void correct(correction.text)}>{correction.text}</button>)}
              {file && <p className="chip"><FileText size={16} aria-hidden /> {file.name}<button type="button" className="icon" aria-label={`Remove ${file.name}`} onClick={() => (setFile(undefined), composer.current?.focus())}><X size={16} /></button></p>}
            </div>
          )}
          <form className="composer" aria-busy={busy} onSubmit={(event) => (event.preventDefault(), submit())}>
            <button type="button" className="icon" aria-label="Attach a PDF report" onClick={() => (DEMO ? setNotice(NEEDS_SYSTEM) : picker.current?.click())}><Paperclip size={18} /></button>
            <input ref={picker} type="file" accept="application/pdf,.pdf" hidden onChange={(event) => (setFile(event.target.files?.[0]), (event.target.value = ''))} />
            <textarea ref={composer} rows={1} aria-label="Message Elevant" placeholder={chat?.quote?.state === 'review' ? 'Describe a correction, for example: line 3 is the landing door roller, 2 units' : 'Attach an inspection report (PDF), then press Enter'} value={text} onChange={(event) => setText(event.target.value)} onKeyDown={enter} />
            <button type="submit" className="send" aria-label="Send" disabled={busy || !(file || text.trim())}><ArrowUp size={18} /></button>
          </form>
        </main>
      </div>
    </div>
  )
}
