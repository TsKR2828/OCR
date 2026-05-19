import { I } from './Icons';

interface Props {
  icon?: string;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon, title, hint, action }: Props) {
  const IconC = icon ? (I as any)[icon] : null;
  return (
    <div style={{
      padding: 40, textAlign: 'center',
      border: '1px dashed var(--ink-border)',
      borderRadius: 8,
      color: 'var(--text-tertiary)',
    }}>
      {IconC && <IconC size={32} style={{ color: 'var(--ink-hover)', marginBottom: 12 }} />}
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>{title}</div>
      {hint && <div style={{ fontSize: 11 }}>{hint}</div>}
      {action}
    </div>
  );
}
