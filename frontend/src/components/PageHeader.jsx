import React from 'react';
import { ArrowRight } from 'lucide-react';
import Breadcrumbs from './Breadcrumbs';

// #621 — one page header for the drill-down screens (building → building defects → unit → defect):
// navy bar, 44px back button, title + location line, optional 44px actions on the far side.
export const PAGE_HEADER_ACTION_CLASS =
  'h-11 w-11 flex-shrink-0 flex items-center justify-center rounded-[10px] bg-white/[0.07] border border-white/10 hover:bg-white/[0.14] active:bg-white/20 transition-colors';

const PageHeader = ({
  title,
  titleTag: TitleTag = 'h1',
  titleExtra = null,
  crumbs = [],
  below = null,
  actions = null,
  onBack,
  backLabel = 'חזרה',
  maxWidth = '',
  zClass = 'z-30',
}) => (
  <header className={`sticky top-0 ${zClass} bg-navy text-white`} dir="rtl">
    <div className={`mx-auto ${maxWidth} px-3 py-2 min-h-[60px] flex items-center gap-2`}>
      {onBack && (
        <button type="button" onClick={onBack} aria-label={backLabel} title={backLabel} className={PAGE_HEADER_ACTION_CLASS}>
          <ArrowRight className="w-5 h-5" />
        </button>
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 min-w-0">
          <TitleTag className="text-lg font-bold leading-6 truncate" style={{ fontFamily: "'Rubik', sans-serif" }}>{title}</TitleTag>
          {titleExtra}
        </div>
        <Breadcrumbs items={crumbs} className="text-white/70 mt-0.5" />
        {below}
      </div>
      {actions}
    </div>
  </header>
);

export default PageHeader;
