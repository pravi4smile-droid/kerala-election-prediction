type DashboardStatusProps = {
  message: string;
  tone?: 'loading' | 'error';
};

export function DashboardStatus({ message, tone = 'loading' }: DashboardStatusProps) {
  const className = tone === 'error' ? 'next-error' : 'next-loader';
  return <main className={className}>{message}</main>;
}

export function NoScriptFallback() {
  return (
    <noscript>
      <DashboardStatus tone="error" message="JavaScript is required to run this dashboard." />
    </noscript>
  );
}
