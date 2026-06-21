import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import './AppLayout.css';

const NAV_ITEMS = [
  { id: 'tables', label: 'Tables', icon: '🍳', path: '/' },
  { id: 'recipes', label: 'All Recipes', icon: '🍃', path: '/recipes' },
  { id: 'new-recipe', label: 'New Recipe', icon: '✍️', path: '/recipes/new' },
];

function getActiveNav(pathname) {
  if (pathname.startsWith('/recipes/new') || pathname.includes('/edit')) return 'new-recipe';
  if (pathname.startsWith('/recipes')) return 'recipes';
  return 'tables';
}

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeNav = getActiveNav(location.pathname);

  return (
    <div className="app-root">
      <aside className="app-sidebar desktop-only">
        <div className="sidebar-brand">
          <span className="sidebar-brand-icon">🌿</span>
          <span className="sidebar-brand-name">
            Ayurvedalove<span className="home-dot">.</span>
          </span>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`sidebar-nav-item ${activeNav === item.id ? 'active' : ''}`}
              onClick={() => navigate(item.path)}
            >
              <span className="sidebar-nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user-avatar">AL</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">Your kitchen</div>
            <div className="sidebar-user-sub">Ayurvedalove</div>
          </div>
        </div>
      </aside>

      <div className="app-body">
        <main className="app-main">
          <div className="app-page">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
