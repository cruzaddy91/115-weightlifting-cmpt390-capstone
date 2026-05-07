import { Link, Navigate, useParams } from 'react-router-dom'
import './HeadCoachDashboard.css'

const CATEGORY_PAGES = {
  '001': {
    label: '001_INFINITY',
    colorKey: 'gun-silver',
    status: 'UNASSIGNED',
    description: 'Assistant-manager template. No head coach, coaches, or athletes assigned yet.',
  },
  '002': {
    label: '002_REACH',
    colorKey: 'shell-copper',
    status: 'UNASSIGNED',
    description: 'Assistant-manager template. No head coach, coaches, or athletes assigned yet.',
  },
  '003': {
    label: '003_FORERUNNER',
    colorKey: 'sand-tan',
    status: 'UNASSIGNED',
    description: 'Assistant-manager template. No head coach, coaches, or athletes assigned yet.',
  },
  '004': {
    label: '004_ODST',
    colorKey: 'steel-blue',
    status: 'UNASSIGNED',
    description: 'Assistant-manager template. No head coach, coaches, or athletes assigned yet.',
  },
}

const HeadCoachCategoryPage = () => {
  const { prefix } = useParams()
  const category = CATEGORY_PAGES[prefix]

  if (!category) return <Navigate to="/head" replace />

  return (
    <main className="head-dashboard page-shell">
      <header className="head-dashboard-header">
        <div>
          <div className="dashboard-kicker-row">
            <span className="dashboard-kicker">Head Coach Category</span>
            <Link to="/head" className="head-dashboard-link-coach">Back to master dashboard</Link>
          </div>
          <h1>{category.label}</h1>
          <p className="dashboard-description head-dashboard-lede">
            Empty template using the same assignment rules and cardinalities as the master head-coach workspace.
          </p>
        </div>
      </header>

      <section className="head-category-template-grid" aria-label={`${category.label} template`}>
        <article className="head-category-template-card section-card">
          <span className={`head-org-badge head-org-${category.colorKey}`}>{category.label}</span>
          <h2>{category.status}</h2>
          <p>{category.description}</p>
        </article>
        <article className="head-category-template-card section-card">
          <span className="label">Head coach</span>
          <strong className="data">Empty</strong>
          <p>Future promoted line coach will assume this category prefix.</p>
        </article>
        <article className="head-category-template-card section-card">
          <span className="label">Line coaches</span>
          <strong className="data">0</strong>
          <p>Minimum 0. Coaches can be assigned after this category has a head coach.</p>
        </article>
        <article className="head-category-template-card section-card">
          <span className="label">Athletes</span>
          <strong className="data">0</strong>
          <p>Athletes inherit the category color through their accountable coach or head coach.</p>
        </article>
      </section>
    </main>
  )
}

export default HeadCoachCategoryPage
