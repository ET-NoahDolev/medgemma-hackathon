import { useState, useEffect } from 'react';
import { Toaster } from '@/components/ui/sonner';
import { QueryProvider } from '@/providers/QueryProvider';
import { ProtocolScreen } from '@/screens/ProtocolScreen';
import { TriplaneReview } from '@/screens/TriplaneReview';
import { setTheme } from '@/design-system/theme';
import { Button } from '@/components/ui/button';

export default function App() {
  const [view, setView] = useState<'protocol' | 'review'>('protocol');

  useEffect(() => {
    setTheme('light');
  }, []);

  return (
    <QueryProvider>
      <div className="min-h-screen bg-transparent">
        <div className="p-4 flex gap-2 border-b border-gray-200">
          <Button variant={view === 'protocol' ? 'default' : 'outline'} onClick={() => setView('protocol')}>
            Protocol Review
          </Button>
          <Button variant={view === 'review' ? 'default' : 'outline'} onClick={() => setView('review')}>
            Triplane Review
          </Button>
        </div>
        <div className="h-[calc(100vh-64px)]">
          {view === 'protocol' ? <ProtocolScreen /> : <TriplaneReview />}
        </div>
      </div>
      <Toaster />
    </QueryProvider>
  );
}
