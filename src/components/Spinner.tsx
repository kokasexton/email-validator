export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <span style={{
      display: 'inline-block', width: size, height: size,
      border: '2px solid var(--neutral-200)', borderTopColor: 'var(--primary-500)',
      borderRadius: '50%', animation: 'spin .65s linear infinite', flexShrink: 0,
    }} />
  );
}
