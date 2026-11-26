import { Sparkles, Upload } from 'lucide-react'
import { type ChangeEvent, useRef } from 'react'
import { useLoadSample, useUploadFiles } from '../api/hooks'
import { ErrorNote } from './ErrorNote'

/** Adds tables to a project: upload CSV or Parquet files, or load the synthetic ERP sample. */
export function UploadPanel({ projectId }: { projectId: string }) {
  const upload = useUploadFiles(projectId)
  const sample = useLoadSample(projectId)
  const input = useRef<HTMLInputElement>(null)

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    if (files.length) upload.mutate(files)
    event.target.value = ''
  }

  const busy = upload.isPending || sample.isPending
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
      <h2 className="text-xl font-semibold">Add tables</h2>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        Upload CSV or Parquet extracts, or load a synthetic SAP-style ERP sample with planted
        data-quality issues.
      </p>
      <div className="mt-4 flex flex-wrap gap-3">
        <input
          ref={input}
          type="file"
          multiple
          accept=".csv,.parquet"
          onChange={onFiles}
          className="sr-only"
          tabIndex={-1}
          aria-label="Upload CSV or Parquet files"
        />
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={busy}
          className="btn-secondary"
        >
          <Upload className="h-4 w-4" /> Upload files
        </button>
        <button
          type="button"
          onClick={() => sample.mutate('erp_s1_sap')}
          disabled={busy}
          className="btn-primary"
        >
          <Sparkles className="h-4 w-4" /> Load ERP sample
        </button>
      </div>
      {busy && <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Loading tables…</p>}
      {upload.data && (
        <p className="mt-3 text-sm text-emerald-700 dark:text-emerald-400">
          Loaded {upload.data.map((t) => t.name).join(', ')}.
        </p>
      )}
      <div className="mt-3 space-y-2">
        <ErrorNote error={upload.error} />
        <ErrorNote error={sample.error} />
      </div>
    </div>
  )
}
