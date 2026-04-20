// Hebrew RTL dashboard mock — what the user "lands on" after loading completes
function BrikDashboard() {
  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: '#F4F5F7',
      direction: 'rtl',
      fontFamily: '"Rubik", system-ui, sans-serif',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        background: '#323A4E',
        padding: '52px 20px 20px',
        color: '#fff',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <BrikMark size={28} color="#F59E0B"/>
            <span style={{ fontWeight: 700, fontSize: 18, direction: 'ltr' }}>
              Brik<span style={{ color: '#F59E0B' }}>Ops</span>
            </span>
          </div>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'rgba(255,255,255,0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, fontWeight: 600,
          }}>דמ</div>
        </div>
        <div style={{ fontSize: 13, opacity: 0.6, marginBottom: 4 }}>שלום, דניאל</div>
        <div style={{ fontSize: 22, fontWeight: 700, letterSpacing: -0.3 }}>פרויקטים פעילים</div>
      </div>

      {/* KPIs */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8,
        padding: '16px 20px 0',
      }}>
        <KPI label="ליקויים פתוחים" value="47" accent/>
        <KPI label="ביקורות השבוע" value="12"/>
        <KPI label="מסירות" value="3"/>
      </div>

      {/* Project cards */}
      <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <ProjectCard name="מגדלי אביב" addr="רמת גן · 84 דירות" defects={23} status="active"/>
        <ProjectCard name="פרויקט הדר" addr="תל אביב · 32 דירות" defects={14} status="review"/>
        <ProjectCard name="גני יהלום" addr="הרצליה · 56 דירות" defects={10} status="active"/>
      </div>
    </div>
  );
}

function KPI({ label, value, accent }) {
  return (
    <div style={{
      background: '#fff', padding: '12px 10px', borderRadius: 12,
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: accent ? '#F59E0B' : '#323A4E', lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, color: '#6B7280', marginTop: 4 }}>{label}</div>
    </div>
  );
}

function ProjectCard({ name, addr, defects, status }) {
  const statusMap = {
    active: { label: 'פעיל', color: '#10B981', bg: 'rgba(16, 185, 129, 0.1)' },
    review: { label: 'בבדיקה', color: '#F59E0B', bg: 'rgba(245, 158, 11, 0.12)' },
  };
  const s = statusMap[status];
  return (
    <div style={{
      background: '#fff', borderRadius: 14, padding: 14,
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 10,
        background: '#323A4E',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#fff', fontWeight: 700, fontSize: 18,
      }}>{name.charAt(0)}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 15, color: '#111', marginBottom: 2 }}>{name}</div>
        <div style={{ fontSize: 12, color: '#6B7280' }}>{addr}</div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: 11, padding: '3px 8px', borderRadius: 6,
          background: s.bg, color: s.color, fontWeight: 600, marginBottom: 4,
        }}>{s.label}</div>
        <div style={{ fontSize: 11, color: '#6B7280' }}>{defects} ליקויים</div>
      </div>
    </div>
  );
}

Object.assign(window, { BrikDashboard, KPI, ProjectCard });
