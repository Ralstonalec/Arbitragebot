import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Fund Dashboard',
  description: 'Multi-sleeve trading fund — markets, Polymarket copy-trading, sports +EV, insider disclosures.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface)' }}>
          <div className="container" style={{ display: 'flex', justifyContent: 'space-between',
                                              alignItems: 'center', paddingTop: '0.75rem',
                                              paddingBottom: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div style={{ width: 28, height: 28, borderRadius: 8,
                            background: 'linear-gradient(135deg, #3d9eff 0%, #a78bfa 100%)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: '0.8rem', fontWeight: 800, color: '#041018' }}>
                F
              </div>
              <div>
                <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>Fund</span>
                <span style={{ color: 'var(--muted)', marginLeft: '0.4rem', fontSize: '0.8rem' }}>
                  intelligence
                </span>
              </div>
            </div>
            <nav style={{ display: 'flex', gap: '1.25rem', fontSize: '0.875rem' }}>
              <a href="/" style={{ color: 'var(--text)', fontWeight: 500 }}>Portfolio</a>
              <a href="/opportunities" style={{ color: 'var(--muted)' }}>Opportunities</a>
            </nav>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
