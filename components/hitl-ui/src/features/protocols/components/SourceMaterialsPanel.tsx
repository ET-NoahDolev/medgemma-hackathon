import { useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FileText, Eye } from 'lucide-react';

export interface SourceDocument {
  id: string;
  name: string;
  content: string;
  type?: 'protocol' | 'ecrf' | 'other';
}

interface SourceMaterialsPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  documents: SourceDocument[];
}

export function SourceMaterialsPanel({
  open,
  onOpenChange,
  documents,
}: SourceMaterialsPanelProps) {
  const [selectedDoc, setSelectedDoc] = useState<SourceDocument | null>(null);
  const [activeTab, setActiveTab] = useState<'documents' | 'viewer'>('documents');

  const handleView = (doc: SourceDocument) => {
    setSelectedDoc(doc);
    setActiveTab('viewer');
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-3xl p-0 flex flex-col gap-0">
        <SheetHeader className="px-6 py-4 border-b">
          <SheetTitle className="flex items-center gap-2" style={{ fontSize: '18px' }}>
            <FileText className="w-5 h-5" />
            Source Materials
          </SheetTitle>
          <SheetDescription style={{ fontSize: '14px' }}>
            View protocol documents used for extraction
          </SheetDescription>
        </SheetHeader>

        <Tabs
          value={activeTab}
          onValueChange={value => setActiveTab(value as 'documents' | 'viewer')}
          className="flex-1 flex flex-col gap-0"
        >
          <div className="px-6 pt-6 pb-0">
            <TabsList className="grid w-full grid-cols-2" style={{ fontSize: '14px' }}>
              <TabsTrigger value="documents" style={{ fontSize: '14px' }}>
                Documents ({documents.length})
              </TabsTrigger>
              <TabsTrigger value="viewer" disabled={!selectedDoc} style={{ fontSize: '14px' }}>
                Viewer
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="documents" className="flex-1 mt-0">
            <div className="p-6 space-y-4">
              {documents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                  <FileText className="w-12 h-12 mb-4" />
                  <p style={{ fontSize: '14px' }}>No documents available</p>
                  <p className="text-gray-400" style={{ fontSize: '12px' }}>
                    Upload a protocol to view its source text.
                  </p>
                </div>
              ) : (
                <ScrollArea className="h-[calc(100vh-280px)]">
                  <div className="space-y-3">
                    {documents.map(doc => (
                      <Card key={doc.id} className="hover:shadow-md transition-shadow">
                        <CardContent className="p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <FileText className="w-4 h-4 text-gray-500 flex-shrink-0" />
                                <h4 className="truncate" style={{ fontSize: '14px' }}>
                                  {doc.name}
                                </h4>
                                {doc.type && (
                                  <Badge variant="outline" style={{ fontSize: '11px' }}>
                                    {doc.type}
                                  </Badge>
                                )}
                              </div>
                            </div>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleView(doc)}
                              className="gap-1"
                              style={{ fontSize: '12px' }}
                            >
                              <Eye className="w-3 h-3" />
                              View
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>
          </TabsContent>

          <TabsContent value="viewer" className="flex-1 mt-0">
            <ScrollArea className="h-[calc(100vh-220px)]">
              <div className="p-6">
                {selectedDoc ? (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <h3 style={{ fontSize: '16px' }}>{selectedDoc.name}</h3>
                      {selectedDoc.type && (
                        <Badge variant="outline" style={{ fontSize: '11px' }}>
                          {selectedDoc.type}
                        </Badge>
                      )}
                    </div>
                    <div className="p-4 bg-gray-50 border rounded-lg">
                      <div className="prose prose-sm max-w-none">
                        <pre
                          className="whitespace-pre-wrap text-gray-900 leading-relaxed"
                          style={{ fontSize: '13px' }}
                        >
                          {selectedDoc.content || 'Content not available'}
                        </pre>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <FileText className="w-12 h-12 mb-4" />
                    <p style={{ fontSize: '14px' }}>Select a document to view its contents</p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>

        <div className="px-6 py-4 border-t bg-gray-50 flex justify-end">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            style={{ fontSize: '14px' }}
          >
            Close
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
