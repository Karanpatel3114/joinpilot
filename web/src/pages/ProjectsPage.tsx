import { MessageSquareText, ShieldCheck, Waypoints } from 'lucide-react'
import { useProjects } from '../api/hooks'
import { CreateProjectForm } from '../components/CreateProjectForm'
import { ErrorNote } from '../components/ErrorNote'
import { ProjectCard } from '../components/ProjectCard'
import { AskVisual } from '../components/home/AskVisual'
import { ChecksVisual } from '../components/home/ChecksVisual'
import { EVAL_SOURCE, STATS } from '../components/home/evidence'
import { Feature } from '../components/home/Feature'
import { Hero } from '../components/home/Hero'
import { JoinsVisual } from '../components/home/JoinsVisual'
import { StackStrip } from '../components/home/StackStrip'
import { Statement } from '../components/home/Statement'

/** Home: what JoinPilot does, the measured results, then the user's projects. */
export function ProjectsPage() {
  const projects = useProjects()
  return (
    <>
      <Hero />
      <StackStrip />
      <Statement />

      <section id="how" aria-label="How it works" className="scroll-mt-20 pt-10">
        <Feature
          eyebrow="Join discovery"
          icon={Waypoints}
          iconClass="bg-[#be7948] text-white"
          title="Find every join, with the numbers that prove it"
          stat={STATS.joinF1}
          visual={<JoinsVisual />}
        >
          JoinPilot profiles each column, then proposes joins from value overlap, key uniqueness and
          cardinality. The AI ranks and explains the candidates; it never invents a join.
        </Feature>
        <Feature
          eyebrow="Approval and checks"
          icon={ShieldCheck}
          iconClass="bg-[#c4e8c4] text-[#163126]"
          title="You approve, then it builds tested views"
          stat={STATS.kpis}
          visual={<ChecksVisual />}
          flip
        >
          Nothing is created until a person approves the joins. Every SQL view then runs checks for lost rows,
          orphan keys and totals, and failures are repaired before the KPI dashboard is built.
        </Feature>
        <Feature
          eyebrow="Questions in plain English"
          icon={MessageSquareText}
          iconClass="bg-brand-600 text-brand-300 dark:bg-brand-300 dark:text-brand-600"
          title="Ask a question, see the guarded SQL behind the answer"
          stat={STATS.attacks}
          visual={<AskVisual />}
        >
          Questions become read-only SQL that must pass a strict guard before it runs, and every answer shows
          its query. Claude and other AI tools can use the same workflow through the MCP server.
        </Feature>
        <p className="font-mono text-[11px] text-slate-500 dark:text-slate-400">
          Numbers from the {EVAL_SOURCE.split} split evaluation, {EVAL_SOURCE.date}, commit{' '}
          <a href={EVAL_SOURCE.url} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-slate-950 dark:hover:text-white">
            {EVAL_SOURCE.commit}
          </a>
          .
        </p>
      </section>

      <section id="projects" aria-labelledby="projects-title" className="mt-20 scroll-mt-20 space-y-6 border-t border-slate-200 pt-16 dark:border-slate-800">
        <div>
          <p className="eyebrow">Your workspace</p>
          <h2 id="projects-title" className="mt-3 text-4xl font-semibold">
            Projects
          </h2>
          <p className="mt-2 max-w-xl text-slate-600 dark:text-slate-400">
            Each project holds your tables, their profile and the runs that turn them into a model. Create one and
            load the sample ERP data to try it.
          </p>
        </div>
        <div className="card p-5">
          <CreateProjectForm />
        </div>
        <ErrorNote error={projects.error} />
        {projects.isLoading && <p className="text-sm text-slate-500 dark:text-slate-400">Loading projects…</p>}
        {projects.data?.length === 0 && (
          <p className="text-sm text-slate-500 dark:text-slate-400">No projects yet. Create one to get started.</p>
        )}
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data?.map((project) => (
            <li key={project.id}>
              <ProjectCard project={project} />
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}
