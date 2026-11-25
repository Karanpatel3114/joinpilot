export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-6 py-4">
          <img src="/favicon.svg" alt="" className="h-7 w-7" />
          <span className="text-lg font-semibold tracking-tight">JoinPilot</span>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-16">
        <h1 className="text-3xl font-bold tracking-tight">From raw ERP tables to a tested data model</h1>
        <p className="mt-3 max-w-2xl text-slate-600 dark:text-slate-400">
          Upload tables, describe what you need in plain English, and approve evidence-backed joins
          before any view is built.
        </p>
      </main>
    </div>
  )
}
