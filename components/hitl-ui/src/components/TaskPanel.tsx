import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useTaskStore } from '@/stores/TaskStore';

function statusBadgeVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status === 'failed') return 'destructive';
  if (status === 'completed') return 'secondary';
  return 'outline';
}

export function TaskPanel() {
  const { tasks, clearCompleted } = useTaskStore();
  const visible = tasks.filter(t => t.status === 'running' || t.status === 'failed' || t.status === 'completed');

  if (visible.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 w-[420px] max-w-[calc(100vw-2rem)] z-50">
      <Card className="border-gray-200 shadow-lg">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium text-gray-900">Background tasks</div>
            <Button variant="ghost" size="sm" onClick={clearCompleted}>
              Clear completed
            </Button>
          </div>

          <div className="space-y-3">
            {visible.slice(0, 5).map(task => (
              <div key={task.id} className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Link to={`/protocols/${encodeURIComponent(task.id)}`} className="text-sm text-teal-700 truncate">
                        {task.protocolTitle}
                      </Link>
                      <Badge variant={statusBadgeVariant(task.status)} className="text-xs">
                        {task.type}
                      </Badge>
                    </div>
                    <div className="text-xs text-gray-600 mt-0.5">{task.message}</div>
                  </div>
                  <Badge variant={statusBadgeVariant(task.status)} className="text-xs whitespace-nowrap">
                    {task.status}
                  </Badge>
                </div>

                {task.status === 'running' && (
                  <div className="space-y-1">
                    {task.progress == null ? (
                      <Progress value={40} className="h-2" />
                    ) : (
                      <Progress value={task.progress} className="h-2" />
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {visible.length > 5 && (
            <div className="text-xs text-gray-500">Showing latest 5 tasks. Open the protocol list for more.</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

