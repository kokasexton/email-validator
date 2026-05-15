import { NavLink } from 'react-router-dom';
import { CircleCheck as CheckCircle, Layers, History, Code as Code2, LayoutDashboard } from 'lucide-react';
import s from './Layout.module.css';

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className={s.root}>
      <aside className={s.sidebar}>
        <div className={s.brand}>
          <span className={s.brandIcon}><CheckCircle size={18} strokeWidth={2.5} /></span>
          <div>
            <div className={s.brandName}>VerifyPro</div>
            <div className={s.brandSub}>Email Intelligence</div>
          </div>
        </div>

        <nav className={s.nav}>
          <div className={s.group}>
            <div className={s.groupLabel}>Validate</div>
            <NavLink to="/" end className={({ isActive }) => `${s.item} ${isActive ? s.active : ''}`}>
              <LayoutDashboard size={15} /> Dashboard
            </NavLink>
            <NavLink to="/single" className={({ isActive }) => `${s.item} ${isActive ? s.active : ''}`}>
              <CheckCircle size={15} /> Single Email
            </NavLink>
            <NavLink to="/bulk" className={({ isActive }) => `${s.item} ${isActive ? s.active : ''}`}>
              <Layers size={15} /> Bulk / CSV
            </NavLink>
          </div>
          <div className={s.group}>
            <div className={s.groupLabel}>Data</div>
            <NavLink to="/history" className={({ isActive }) => `${s.item} ${isActive ? s.active : ''}`}>
              <History size={15} /> History
            </NavLink>
            <NavLink to="/api-docs" className={({ isActive }) => `${s.item} ${isActive ? s.active : ''}`}>
              <Code2 size={15} /> API Reference
            </NavLink>
          </div>
        </nav>

        <div className={s.footer}>
          <span className={s.ver}>v2.0.0</span>
          <span className={s.port}>SMTP :25</span>
        </div>
      </aside>

      <main className={s.main}>{children}</main>
    </div>
  );
}
