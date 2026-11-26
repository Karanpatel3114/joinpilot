import { isRouteErrorResponse, Link, useRouteError } from 'react-router'

/** Shown instead of a page that could not load (a missing page, or a failed download). */
export function RouteError() {
  const error = useRouteError()
  const missing = isRouteErrorResponse(error) && error.status === 404
  return (
    <main className="mx-auto max-w-xl space-y-3 px-6 py-16 text-center">
      <h1 className="text-2xl font-bold tracking-tight">
        {missing ? 'Page not found' : 'This page could not load'}
      </h1>
      <p className="text-slate-600 dark:text-slate-400">
        {missing
          ? 'The address does not match any page in JoinPilot.'
          : 'Reload to try again; if the app was just updated, a reload fetches the new version.'}
      </p>
      <Link to="/" className="inline-block text-brand-600 hover:underline dark:text-brand-300">
        Back to projects
      </Link>
    </main>
  )
}
