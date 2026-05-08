import { Link, NavLink, Route, Routes } from "react-router-dom";
import Digest from "./pages/Digest.jsx";
import Archive from "./pages/Archive.jsx";

function NavTab({ to, children, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `font-mono text-[11px] uppercase tracking-[0.18em] px-2 py-1 ${
          isActive ? "text-ink-50 border-b border-wire-ir" : "text-ink-400 hover:text-ink-100"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

export default function App() {
  return (
    <div className="min-h-screen bg-ink-950 text-ink-100">
      <header className="border-b border-ink-800 bg-ink-950/95 backdrop-blur sticky top-0 z-10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link to="/" className="font-mono text-sm tracking-wider text-ink-50">
            DEBATE&nbsp;DIGEST
            <span className="ml-2 font-mono text-[10px] uppercase tracking-widest text-ink-500">
              wire
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            <NavTab to="/" end>Today</NavTab>
            <NavTab to="/archive">Archive</NavTab>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Digest />} />
          <Route path="/d/:date" element={<Digest />} />
          <Route path="/archive" element={<Archive />} />
        </Routes>
      </main>
      <footer className="mx-auto max-w-6xl px-4 py-8 font-mono text-[11px] text-ink-500">
        Auto-generated every 3h · BP debate prep
      </footer>
    </div>
  );
}
