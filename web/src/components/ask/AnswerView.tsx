import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router'
import type { Answer, ReasonCode } from '../../types/api'
import { cell, label } from '../dashboard/chartTheme'
import { MetricChart } from '../dashboard/MetricChart'
import { shapeOf } from './answerChart'

const REASONS: Record<ReasonCode, string> = {
  UNSAFE_SQL: 'The query the model wrote was not safe to run, so nothing ran.',
  UNKNOWN_IDENTIFIER: 'The model named a table or column the project does not have, so nothing ran.',
  TIMEOUT: 'The query took too long and was stopped.',
  QUERY_FAILED: 'The database could not run the query.',
  LLM_UNAVAILABLE: 'The language model is not available. Add GEMINI_API_KEY to .env (free, no billing) and restart the API.',
}

/** One answer: the result, how it was produced and the guarded SQL behind it. */
export function AnswerView({ answer }: { answer: Answer }) {
  if (answer.blocked) {
    return (
      <article aria-label={answer.question} className="space-y-2 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-950/40">
        <h3 className="font-semibold">{answer.question}</h3>
        <p role="alert" className="flex gap-2 text-amber-900 dark:text-amber-200">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {answer.reason_code && REASONS[answer.reason_code]} <span className="opacity-80">({answer.message})</span>
          </span>
        </p>
        {answer.sql && <pre className="overflow-auto rounded-lg bg-white/70 p-3 font-mono text-xs dark:bg-slate-950">{answer.sql}</pre>}
      </article>
    )
  }
  const shape = shapeOf(answer)
  const evidence = answer.evidence
  return (
    <article aria-label={answer.question} className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <header>
        <h3 className="font-semibold">{answer.question}</h3>
        {evidence && <p className="text-sm text-slate-600 dark:text-slate-400">{evidence.explanation}</p>}
      </header>
      {shape.kind === 'number' && (
        <p className="text-4xl font-semibold tabular-nums tracking-tight">
          {cell(shape.value)} <span className="text-sm font-normal text-slate-500 dark:text-slate-400">{label(shape.label)}</span>
        </p>
      )}
      {shape.kind === 'chart' && (
        <div role="img" aria-label={`Chart of ${answer.rows.length} rows; the table below lists every value.`}>
          <MetricChart metric={shape.metric} />
        </div>
      )}
      {shape.kind !== 'number' && (
        <div className="max-h-80 overflow-auto rounded-lg border border-slate-200 dark:border-slate-800">
          <table aria-label="Answer rows" className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900 dark:text-slate-400">
              <tr>
                {answer.columns.map((c) => (
                  <th key={c} className="px-3 py-2">{label(c)}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {answer.rows.map((row, i) => (
                <tr key={i}>
                  {answer.columns.map((c) => (
                    <td key={c} className={`px-3 py-1.5 ${typeof row[c] === 'number' ? 'text-right tabular-nums' : ''}`}>
                      {cell(row[c] as string | number | null)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <details className="text-sm">
        <summary className="cursor-pointer text-slate-600 dark:text-slate-400">SQL and evidence</summary>
        <pre className="mt-2 overflow-auto rounded-lg bg-slate-50 p-3 font-mono text-xs whitespace-pre-wrap dark:bg-slate-950">{answer.sql}</pre>
        {evidence && (
          <dl aria-label="Evidence" className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs text-slate-600 dark:text-slate-400">
            <dt>Model</dt>
            <dd>
              run{' '}
              <Link to={`/runs/${evidence.run_id}`} className="font-mono text-brand-600 hover:underline dark:text-brand-300">
                {evidence.run_id.slice(0, 8)}
              </Link>
            </dd>
            <dt>Reads</dt>
            <dd className="font-mono">{evidence.views.length ? evidence.views.join(', ') : 'raw tables only'}</dd>
            <dt>Rows</dt>
            <dd>
              {evidence.row_count}
              {evidence.truncated && ' (more rows exist; the answer shows the first ones)'}
            </dd>
            <dt>Attempts</dt>
            <dd>{evidence.attempts}</dd>
            <dt>Time</dt>
            <dd>{Math.round(evidence.elapsed_ms)} ms</dd>
          </dl>
        )}
      </details>
    </article>
  )
}
