/** The dark statement panel: the problem in one sentence. */
export function Statement() {
  return (
    <section className="flex min-h-[420px] items-center justify-center rounded-[28px] bg-brand-600 px-6 py-24 text-center sm:min-h-[520px]">
      <p className="display max-w-3xl text-[32px] text-white sm:text-5xl">
        ERP systems hold the answers to most business questions,{' '}
        <span className="text-brand-300">but the tables are cryptic and hard to join.</span>
      </p>
    </section>
  )
}
