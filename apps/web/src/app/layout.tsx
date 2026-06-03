import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Arb Intelligence',
  description:
    'Odds intelligence dashboard — theoretical arbitrage and edge detection. Not a gambling operator.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="card" style={{ borderRadius: 0, borderLeft: 0, borderRight: 0 }}>
          <div className="container" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>Arb Intelligence</strong>
              <span style={{ color: 'var(--muted)', marginLeft: '0.75rem', fontSize: '0.85rem' }}>
                Odds research · execution assist only
              </span>
            </div>
            <nav style={{ display: 'flex', gap: '1rem' }}>
              <a href="/">Opportunities</a>
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="container disclaimer">
          This platform does not accept wagers, hold customer funds, or access sportsbook accounts.
          All betting occurs at licensed external sportsbooks at your own risk.
        </footer>
      </body>
    </html>
  );
}
