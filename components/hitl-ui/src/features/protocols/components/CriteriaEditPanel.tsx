import { useEffect, useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Edit2, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

interface CriteriaEditPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  criterion: {
    id: string;
    type: 'inclusion' | 'exclusion';
    text: string;
    status: string;
    confidence?: number;
    sourceText?: string;
  };
  onSave: (updates: {
    text: string;
    type: 'inclusion' | 'exclusion' | 'not-applicable';
    rationale: string;
  }) => void;
}

export function CriteriaEditPanel({
  open,
  onOpenChange,
  criterion,
  onSave,
}: CriteriaEditPanelProps) {
  const [editedType, setEditedType] = useState<'inclusion' | 'exclusion' | 'not-applicable'>(
    criterion.type
  );
  const [editedText, setEditedText] = useState(criterion.text);
  const [rationale, setRationale] = useState('');

  useEffect(() => {
    setEditedType(criterion.type);
    setEditedText(criterion.text);
    setRationale('');
  }, [criterion.id, criterion.text, criterion.type]);

  const handleClose = (isOpen: boolean) => {
    if (!isOpen) {
      setEditedType(criterion.type);
      setEditedText(criterion.text);
      setRationale('');
    }
    onOpenChange(isOpen);
  };

  const handleSave = () => {
    if (!editedText.trim()) {
      toast.error('Please provide updated criterion text');
      return;
    }
    if (!rationale.trim()) {
      toast.error('Please provide a rationale for changes');
      return;
    }

    onSave({
      text: editedText,
      type: editedType,
      rationale,
    });

    toast.success('Criterion updated successfully');
    handleClose(false);
  };

  return (
    <Sheet open={open} onOpenChange={handleClose}>
      <SheetContent side="right" className="w-full sm:max-w-2xl p-0 flex flex-col gap-0">
        <SheetHeader className="px-6 py-4 border-b">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <SheetTitle className="flex items-center gap-2" style={{ fontSize: '18px' }}>
                <Edit2 className="w-5 h-5" />
                Edit Criterion {criterion.type === 'inclusion' ? 'I' : 'E'}
                {criterion.id}
              </SheetTitle>
              <SheetDescription style={{ fontSize: '14px' }}>
                Modify criterion text or type. Changes are logged to the audit trail.
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <ScrollArea className="flex-1" style={{ maxHeight: 'calc(100vh - 220px)' }}>
          <div className="p-6 space-y-6" style={{ fontSize: '14px' }}>
            <Alert>
              <AlertDescription style={{ fontSize: '12px' }}>
                Current status:{' '}
                <Badge variant="outline" className="ml-1" style={{ fontSize: '11px' }}>
                  {criterion.status}
                </Badge>
                {criterion.confidence !== undefined && (
                  <span className="ml-2">
                    AI Confidence: {Math.round(criterion.confidence * 100)}%
                  </span>
                )}
              </AlertDescription>
            </Alert>

            <div className="space-y-3">
              <Label style={{ fontSize: '14px' }}>Original Criterion</Label>
              <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-2">
                <div className="flex items-start gap-2">
                  <Badge
                    variant="outline"
                    className={
                      criterion.type === 'inclusion'
                        ? 'bg-green-50 text-green-700 border-green-300'
                        : 'bg-red-50 text-red-700 border-red-300'
                    }
                    style={{ fontSize: '11px' }}
                  >
                    {criterion.type === 'inclusion' ? 'Inclusion' : 'Exclusion'} {criterion.id}
                  </Badge>
                </div>
                <p className="text-gray-700 leading-relaxed" style={{ fontSize: '14px' }}>
                  {criterion.text}
                </p>
                {criterion.sourceText && (
                  <>
                    <Separator className="my-2" />
                    <div className="space-y-1">
                      <span className="text-gray-500" style={{ fontSize: '12px' }}>
                        Source Evidence:
                      </span>
                      <p className="text-gray-600 italic" style={{ fontSize: '12px' }}>
                        &quot;{criterion.sourceText}&quot;
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <Label htmlFor="criterionText" style={{ fontSize: '14px' }}>
                Updated Criterion Text
              </Label>
              <Textarea
                id="criterionText"
                value={editedText}
                onChange={e => setEditedText(e.target.value)}
                placeholder="Edit criterion text"
                className="min-h-[120px] resize-none"
                style={{ fontSize: '14px' }}
              />
            </div>

            <Separator />

            <div className="space-y-3">
              <Label style={{ fontSize: '14px' }}>Criterion Type</Label>
              <RadioGroup
                value={editedType}
                onValueChange={value =>
                  setEditedType(value as 'inclusion' | 'exclusion' | 'not-applicable')
                }
              >
                <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                  <RadioGroupItem value="inclusion" id="edit-inclusion" />
                  <Label htmlFor="edit-inclusion" className="flex-1 cursor-pointer">
                    <div className="flex items-center gap-2">
                      <Badge
                        className="bg-green-100 text-green-700 border-green-300"
                        style={{ fontSize: '12px' }}
                      >
                        Inclusion
                      </Badge>
                      <span className="text-gray-600" style={{ fontSize: '14px' }}>
                        Patient must meet this criterion
                      </span>
                    </div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                  <RadioGroupItem value="exclusion" id="edit-exclusion" />
                  <Label htmlFor="edit-exclusion" className="flex-1 cursor-pointer">
                    <div className="flex items-center gap-2">
                      <Badge
                        className="bg-red-100 text-red-700 border-red-300"
                        style={{ fontSize: '12px' }}
                      >
                        Exclusion
                      </Badge>
                      <span className="text-gray-600" style={{ fontSize: '14px' }}>
                        Patient must NOT meet this criterion
                      </span>
                    </div>
                  </Label>
                </div>
                <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                  <RadioGroupItem value="not-applicable" id="edit-not-applicable" />
                  <Label htmlFor="edit-not-applicable" className="flex-1 cursor-pointer">
                    <div className="flex items-center gap-2">
                      <Badge
                        className="bg-gray-100 text-gray-700 border-gray-300"
                        style={{ fontSize: '12px' }}
                      >
                        Not Applicable
                      </Badge>
                      <span className="text-gray-600" style={{ fontSize: '14px' }}>
                        Exclude from screening
                      </span>
                    </div>
                  </Label>
                </div>
              </RadioGroup>
              {editedType === 'not-applicable' && (
                <p className="text-orange-600 flex items-center gap-1" style={{ fontSize: '12px' }}>
                  <AlertCircle className="w-3 h-3" />
                  This criterion will be excluded from screening
                </p>
              )}
            </div>

            <Separator />

            <div className="space-y-3">
              <Label htmlFor="edit-rationale" style={{ fontSize: '14px' }}>
                Change Rationale <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="edit-rationale"
                value={rationale}
                onChange={e => setRationale(e.target.value)}
                rows={3}
                className="resize-none"
                placeholder="Explain why you are making these changes..."
                style={{ fontSize: '14px' }}
              />
            </div>
          </div>
        </ScrollArea>

        <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between gap-3">
          <p className="text-gray-600 flex items-center gap-1" style={{ fontSize: '12px' }}>
            <RotateCcw className="w-3 h-3" />
            Changes will be logged to audit trail
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => handleClose(false)} style={{ fontSize: '14px' }}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!rationale.trim()}
              className="gap-2 bg-teal-600 hover:bg-teal-700"
              style={{ fontSize: '14px' }}
            >
              Save Changes
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
