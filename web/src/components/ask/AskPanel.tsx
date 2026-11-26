import { MessageSquareText } from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { useAsk } from '../../api/hooks'
import type { Answer } from '../../types/api'
import { ErrorNote } from '../ErrorNote'
import { AnswerView } from './AnswerView'

const EXAMPLES = [
  'Which 5 customers have the most overdue receivables?',
  'What is the total amount of all open receivables?',
  'How many sales orders were created each month in 2026?',
]

/** Ask the tested model a question in plain English; answers show their SQL and evidence. */
export function AskPanel({ projectId }: { projectId: string }) {
  const ask = useAsk(projectId)
  const [question, setQuestion] = useState('')
  const [answers, setAnswers] = useState<Answer[]>([])

  function submit(event?: FormEvent, text = question) {
    event?.preventDefault()
    if (text.trim().length < 3) return
    ask.mutate(text.trim(), { onSuccess: (answer) => setAnswers((list) => [answer, ...list]) })
  }

  return (
    <section aria-label="Ask" className="space-y-4">
      <form onSubmit={submit} className="flex gap-2">
        <label htmlFor="question" className="sr-only">
          Your question
        </label>
        <input
          id="question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
          placeholder="Ask about your data, for example: open receivables by country"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
        />
        <button
          type="submit"
          disabled={ask.isPending || question.trim().length < 3}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          <MessageSquareText className="h-4 w-4" /> {ask.isPending ? 'Thinking…' : 'Ask'}
        </button>
      </form>
      <div className="flex flex-wrap gap-2 text-xs">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => {
              setQuestion(example)
              submit(undefined, example)
            }}
            disabled={ask.isPending}
            className="rounded-full border border-slate-300 px-3 py-1 text-slate-600 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            {example}
          </button>
        ))}
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        Answers come from the newest tested model. The query must pass the SQL guard, runs read-only, and is
        stopped if it takes too long.
      </p>
      <ErrorNote error={ask.error} />
      <p aria-live="polite" className="sr-only">
        {answers[0] && (answers[0].blocked ? 'The question was blocked.' : `Answered with ${answers[0].rows.length} rows.`)}
      </p>
      {answers.map((answer, i) => (
        <AnswerView key={answers.length - i} answer={answer} />
      ))}
    </section>
  )
}
