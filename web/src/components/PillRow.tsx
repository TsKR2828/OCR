interface PillItem {
  id: string;
  label: string;
  color?: string;
  count?: number;
}

interface Props {
  items: PillItem[];
  value: string;
  onChange: (val: string) => void;
  showAll?: boolean;
}

export function PillRow({ items, value, onChange, showAll = true }: Props) {
  return (
    <div className="pill-row">
      {showAll && (
        <button className={'pill' + (value === 'all' ? ' pill--active' : '')} onClick={() => onChange('all')}>
          全部
        </button>
      )}
      {items.map((it) => (
        <button
          key={it.id}
          className={'pill' + (value === it.id ? ' pill--active' : '')}
          onClick={() => onChange(it.id)}
        >
          {it.color && <span className="pill__dot" style={{ background: it.color }} />}
          {it.label}
          {it.count != null && <span className="pill__count">{it.count}</span>}
        </button>
      ))}
    </div>
  );
}
