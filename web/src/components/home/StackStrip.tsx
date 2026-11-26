const STACK = ['FastAPI', 'LangGraph', 'DuckDB', 'sqlglot', 'Postgres', 'Redis', 'React', 'MCP']

/** A quiet row of the open-source tools JoinPilot is built on. */
export function StackStrip() {
  return (
    <section aria-labelledby="stack-title" className="py-14 text-center">
      <h2 id="stack-title" className="font-mono text-[12px] tracking-normal text-slate-500 dark:text-slate-400">
        Built on open-source tools, runs on free tiers, tested on synthetic ERP data
      </h2>
      <ul className="mx-auto mt-8 grid max-w-5xl grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-4 lg:grid-cols-8">
        {STACK.map((name) => (
          <li key={name} className="text-xl font-semibold tracking-[-0.04em] text-slate-700 dark:text-slate-300">
            {name}
          </li>
        ))}
      </ul>
    </section>
  )
}
