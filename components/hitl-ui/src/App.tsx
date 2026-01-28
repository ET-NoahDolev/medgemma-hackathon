import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { QueryProvider } from '@/providers/QueryProvider';
import { ProtocolScreen } from '@/screens/ProtocolScreen';
import { setTheme } from '@/design-system/theme';
import { TaskStoreProvider } from '@/stores/TaskStore';
import { TaskPanel } from '@/components/TaskPanel';
import { ProtocolListScreen } from '@/screens/ProtocolListScreen';

export default function App() {
  useEffect(() => {
    setTheme('light');
  }, []);

  return (
    <QueryProvider>
      <TaskStoreProvider>
        <BrowserRouter>
          <div className="min-h-screen bg-transparent">
            <Routes>
              <Route path="/" element={<ProtocolListScreen />} />
              <Route path="/protocols/:protocolId" element={<ProtocolScreen />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
          <TaskPanel />
          <Toaster />
        </BrowserRouter>
      </TaskStoreProvider>
    </QueryProvider>
  );
}
