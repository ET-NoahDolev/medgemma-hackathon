import { FileText, Calendar, MapPin } from 'lucide-react';

interface EvidenceSnippetProps {
  source: string;
  timestamp: string;
  location?: string;
  snippet: string;
  highlighted?: string[];
}

export function EvidenceSnippet({
  source,
  timestamp,
  location,
  snippet,
  highlighted = [],
}: EvidenceSnippetProps) {
  const highlightText = (text: string) => {
    if (highlighted.length === 0) return text;

    let result = text;
    highlighted.forEach(term => {
      const regex = new RegExp(`(${term})`, 'gi');
      result = result.replace(regex, '<mark class="bg-yellow-200 px-1 rounded">$1</mark>');
    });

    return result;
  };

  return (
    <div className="p-3 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-all">
      <div className="flex items-start gap-2 mb-2">
        <FileText className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-900">{source}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Calendar className="w-3 h-3" />
              {timestamp}
            </span>
            {location && (
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                {location}
              </span>
            )}
          </div>
        </div>
      </div>

      <div
        className="text-sm text-gray-700 leading-relaxed"
        dangerouslySetInnerHTML={{ __html: highlightText(snippet) }}
      />
    </div>
  );
}
