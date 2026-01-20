import { useEffect } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { QueryProvider } from '@/providers/QueryProvider';
import { ProtocolScreen } from '@/screens/ProtocolScreen';
import { setTheme } from '@/design-system/theme';

export default function App() {
  useEffect(() => {
    setTheme('light');
  }, []);

  return (
    <QueryProvider>
      <div className="min-h-screen bg-transparent">
        <div className="h-[calc(100vh-64px)]">
          <ProtocolScreen />
        </div>
      </div>
      <Toaster />
    </QueryProvider>
  );
}
