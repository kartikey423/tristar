interface BreadcrumbProps {
  items: string[];
  trailing?: React.ReactNode;
}

export function Breadcrumb({ items, trailing }: BreadcrumbProps) {
  return (
    <div className="flex items-center justify-between mb-6">
      <nav className="flex items-center gap-1.5 text-sm text-gray-400" aria-label="Breadcrumb">
        {items.map((item, i) => (
          <span key={item} className="flex items-center gap-1.5">
            {i > 0 && <span>/</span>}
            <span className={i === items.length - 1 ? 'text-gray-700 font-medium' : ''}>
              {item}
            </span>
          </span>
        ))}
      </nav>
      {trailing && <div className="text-xs text-gray-400">{trailing}</div>}
    </div>
  );
}
