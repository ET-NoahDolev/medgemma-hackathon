import { useMemo, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ProtocolListSkeleton } from '@/components/ui/loading-states';
import { useProtocols } from '@/hooks/useProtocols';
import { useUploadProtocol } from '@/hooks/useUploadProtocol';
import { FileText, Upload, Info } from 'lucide-react';

function statusColor(status: string): string {
  const s = status.toLowerCase();
  if (s === 'completed') return 'bg-green-100 text-green-700 border-green-300';
  if (s === 'failed') return 'bg-red-100 text-red-700 border-red-300';
  if (s === 'extracting' || s === 'grounding' || s === 'pending')
    return 'bg-blue-100 text-blue-700 border-blue-300';
  return 'bg-gray-100 text-gray-700 border-gray-300';
}

export function ProtocolListScreen() {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const { data, isLoading, error } = useProtocols({ skip: 0, limit: 50 });
  const uploadProtocol = useUploadProtocol();

  const protocols = useMemo(() => data?.protocols ?? [], [data?.protocols]);

  const handleSelectFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelected = (file: File | null) => {
    if (!file) return;
    // Navigate immediately, let upload complete in background
    uploadProtocol.mutate(
      { file, autoExtract: true },
      {
        onSuccess: (resp) => {
          navigate(`/protocols/${encodeURIComponent(resp.protocol_id)}`);
        },
        onError: (error) => {
          console.error('Upload failed:', error);
          // Error handling is done by the mutation hook
        },
      }
    );
  };

  return (
    <div className="flex flex-col min-h-screen">
      <div className="bg-white border-b border-gray-200 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-6 h-6 text-teal-600" />
              <h1 className="font-semibold text-gray-900">Protocols</h1>
            </div>
            <p className="text-sm text-gray-600">
              Start a new protocol upload, or open one that’s already processing.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              className="hidden"
              onChange={e => void handleFileSelected(e.target.files?.item(0) ?? null)}
            />
            <Button onClick={handleSelectFileClick} disabled={uploadProtocol.isPending}>
              <Upload className="w-4 h-4 mr-2" />
              {uploadProtocol.isPending ? 'Uploading…' : 'New Protocol'}
            </Button>
          </div>
        </div>

        <Alert className="mt-4 border-blue-300 bg-blue-50">
          <Info className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800">
            Long-running tasks run in the background. You can upload another protocol while extraction
            continues.
          </AlertDescription>
        </Alert>

        {error && (
          <Alert className="mt-4 border-red-300 bg-red-50">
            <Info className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">{error.message}</AlertDescription>
          </Alert>
        )}
      </div>

      <div className="bg-transparent p-6 max-w-6xl mx-auto w-full">
        {isLoading ? (
          <ProtocolListSkeleton count={6} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {protocols.map(p => (
              <Link key={p.protocol_id} to={`/protocols/${encodeURIComponent(p.protocol_id)}`}>
                <Card className="hover:shadow-md transition-shadow">
                  <CardContent className="p-5 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium text-gray-900 truncate">{p.title}</div>
                        <div className="text-xs text-gray-500 mt-1 truncate">{p.protocol_id}</div>
                      </div>
                      <Badge variant="outline" className={statusColor(p.processing_status)}>
                        {p.processing_status}
                      </Badge>
                    </div>

                    <div className="text-sm text-gray-600">
                      {('progress_message' in p && (p as unknown as { progress_message?: string | null }).progress_message) ||
                        `Processed ${p.processed_count ?? 0} criteria`}
                    </div>

                    <div className="text-xs text-gray-500">
                      {p.total_estimated && p.total_estimated > 0
                        ? `${p.processed_count ?? 0}/${p.total_estimated} criteria`
                        : `${p.processed_count ?? 0} criteria`}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}

        {!isLoading && protocols.length === 0 && (
          <div className="text-center text-sm text-gray-600 py-16">
            No protocols yet. Upload a PDF to get started.
          </div>
        )}
      </div>
    </div>
  );
}

