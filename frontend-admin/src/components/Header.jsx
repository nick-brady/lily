import { NavLink } from 'react-router-dom';
import { useAuth } from '../auth';

// The one header, now that there are two pages. `children` is the page's
// own control (the dashboard's date range, the logs page has none here).
export default function Header({ children }) {
  const { logout } = useAuth();
  return (
    <header className="flex items-center justify-between flex-wrap gap-3">
      <div className="flex items-center gap-5">
        <h1 className="text-xl font-bold text-gray-900">Arrival Story · Admin</h1>
        <nav className="flex items-center gap-1 text-sm">
          {[
            { to: '/', label: 'Dashboard' },
            { to: '/logs', label: 'Logs' },
          ].map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `px-2.5 py-1 rounded-md font-medium ${
                  isActive ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3">
        {children}
        <button onClick={logout} className="text-sm text-gray-500 hover:text-gray-700">
          Sign out
        </button>
      </div>
    </header>
  );
}
