import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Search,
  Download,
  TrendingUp,
  MapPin,
  FileCheck,
  AlertTriangle,
  FileText,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface EMRSnippet {
  source: string;
  date: string;
  text: string;
}

interface InstitutionalMapping {
  id: string;
  criterionText: string;
  protocol: string;
  mappingCode: string;
  mappingSystem: string;
  mappingDescription: string;
  contributingSite: string;
  reuseCount: number;
  criteriaType: 'inclusion' | 'exclusion';
  lastUsed: string;
  appliedAtSites: string[];
  emrSnippets: EMRSnippet[];
}

const mockInstitutionalMappings: InstitutionalMapping[] = [
  {
    id: 'im-1',
    criterionText: 'Active cancer diagnosis within past 5 years',
    protocol: 'CRC-2024-001',
    mappingCode: 'C18.9',
    mappingSystem: 'ICD-10',
    mappingDescription: 'Malignant neoplasm of colon, unspecified',
    contributingSite: 'Memorial Hospital',
    reuseCount: 23,
    criteriaType: 'exclusion',
    lastUsed: '2025-10-28',
    appliedAtSites: [
      'Memorial Hospital',
      'Boston General',
      'Cleveland Clinic',
      'Mayo Clinic',
      'Johns Hopkins',
    ],
    emrSnippets: [
      {
        source: 'Problem List - Epic',
        date: '2023-06-15',
        text: 'DIAGNOSIS: Malignant neoplasm of ascending colon (C18.2). Patient underwent hemicolectomy 06/2023. Currently on adjuvant chemotherapy FOLFOX protocol.',
      },
      {
        source: 'Oncology Note - Dr. Martinez',
        date: '2023-08-22',
        text: 'Stage IIIB colon adenocarcinoma s/p right hemicolectomy. Cycle 8 of 12 FOLFOX completed. Tolerated well with grade 1 peripheral neuropathy.',
      },
      {
        source: 'Pathology Report',
        date: '2023-06-18',
        text: 'Colon, right hemicolectomy: Adenocarcinoma, moderately differentiated, invading through muscularis propria into pericolonic tissue. 3/15 lymph nodes positive.',
      },
    ],
  },
  {
    id: 'im-2',
    criterionText: 'Age ≥ 18 years at time of screening',
    protocol: 'CRC-2024-001',
    mappingCode: 'age',
    mappingSystem: 'FHIR',
    mappingDescription: 'Patient.birthDate >= 18 years',
    contributingSite: 'Boston General',
    reuseCount: 47,
    criteriaType: 'inclusion',
    lastUsed: '2025-11-01',
    appliedAtSites: [
      'Boston General',
      'Memorial Hospital',
      'Cleveland Clinic',
      'Mayo Clinic',
      'Johns Hopkins',
      'Stanford Medical',
      'UCSF Medical',
      'Duke University',
    ],
    emrSnippets: [
      {
        source: 'Patient Demographics - FHIR',
        date: '2024-01-10',
        text: 'Patient.birthDate: 1978-03-22\nPatient.age: 46 years\nCalculated at screening date: 2024-10-15',
      },
    ],
  },
  {
    id: 'im-3',
    criterionText: 'History of colonoscopy in past 10 years',
    protocol: 'CRC-2023-015',
    mappingCode: '45378',
    mappingSystem: 'CPT',
    mappingDescription: 'Colonoscopy, flexible; diagnostic',
    contributingSite: 'Cleveland Clinic',
    reuseCount: 31,
    criteriaType: 'exclusion',
    lastUsed: '2025-10-25',
    appliedAtSites: [
      'Cleveland Clinic',
      'Memorial Hospital',
      'Mayo Clinic',
      'Boston General',
      'University Medical Center',
      'Regional Health System',
    ],
    emrSnippets: [
      {
        source: 'Procedure Note - GI',
        date: '2019-05-12',
        text: 'PROCEDURE: Colonoscopy (CPT 45378). Prep: Excellent. Scope advanced to cecum. Findings: Two small (<5mm) hyperplastic polyps in sigmoid, cold snare removed. Otherwise normal exam.',
      },
      {
        source: 'Billing Record',
        date: '2019-05-12',
        text: 'CPT 45378 - Colonoscopy, flexible; diagnostic, including collection of specimen(s) by brushing or washing, when performed',
      },
    ],
  },
  {
    id: 'im-4',
    criterionText: 'Hemoglobin < 10 g/dL within past 30 days',
    protocol: 'CRC-2024-002',
    mappingCode: '718-7',
    mappingSystem: 'LOINC',
    mappingDescription: 'Hemoglobin [Mass/volume] in Blood',
    contributingSite: 'Mayo Clinic',
    reuseCount: 18,
    criteriaType: 'exclusion',
    lastUsed: '2025-10-30',
    appliedAtSites: ['Mayo Clinic', 'Cleveland Clinic', 'Memorial Hospital', 'Stanford Medical'],
    emrSnippets: [
      {
        source: 'Lab Result - LOINC 718-7',
        date: '2025-10-15',
        text: 'Hemoglobin: 9.2 g/dL [LOW]\nReference Range: 12.0-16.0 g/dL\nMethod: Automated cell counter',
      },
      {
        source: 'Lab Result - LOINC 718-7',
        date: '2025-10-28',
        text: 'Hemoglobin: 8.8 g/dL [CRITICAL LOW]\nReference Range: 12.0-16.0 g/dL\nProvider notified.',
      },
    ],
  },
  {
    id: 'im-5',
    criterionText: 'Pregnancy or breastfeeding',
    protocol: 'CRC-2024-001',
    mappingCode: 'Z33.1',
    mappingSystem: 'ICD-10',
    mappingDescription: 'Pregnant state, incidental',
    contributingSite: 'University Medical Center',
    reuseCount: 56,
    criteriaType: 'exclusion',
    lastUsed: '2025-11-02',
    appliedAtSites: [
      'University Medical Center',
      'Memorial Hospital',
      'Boston General',
      'Cleveland Clinic',
      'Mayo Clinic',
      'Johns Hopkins',
      'Stanford Medical',
      'UCSF Medical',
      'Duke University',
      'Yale Medical',
    ],
    emrSnippets: [
      {
        source: 'OB/GYN Note',
        date: '2025-09-20',
        text: 'Patient reports LMP 2025-07-15. Urine pregnancy test: POSITIVE. Estimated gestational age: 9 weeks. Patient counseled on prenatal care and scheduled for first OB visit.',
      },
      {
        source: 'Problem List',
        date: '2025-09-20',
        text: 'Active Diagnosis: Pregnancy, first trimester (Z33.1)\nOnset: 2025-07-15 (LMP)\nStatus: Active',
      },
    ],
  },
  {
    id: 'im-6',
    criterionText: 'ECOG performance status 0-2',
    protocol: 'CRC-2023-012',
    mappingCode: '89247-1',
    mappingSystem: 'LOINC',
    mappingDescription: 'ECOG performance status score',
    contributingSite: 'Regional Health System',
    reuseCount: 12,
    criteriaType: 'inclusion',
    lastUsed: '2025-10-20',
    appliedAtSites: ['Regional Health System', 'Memorial Hospital', 'Cleveland Clinic'],
    emrSnippets: [
      {
        source: 'Oncology Assessment',
        date: '2025-10-18',
        text: 'ECOG Performance Status: 1\nPatient fully ambulatory, able to carry out light work. Restricted in physically strenuous activity but ambulatory and able to carry out work of a light or sedentary nature.',
      },
      {
        source: 'Clinical Flow Sheet - LOINC 89247-1',
        date: '2025-10-18',
        text: 'ECOG Score: 1\nAssessed by: Dr. Johnson, MD\nMethod: Clinical observation and patient interview',
      },
    ],
  },
];

export function InstitutionalMappingMemory() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedProtocol, setSelectedProtocol] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [objectedMappings, setObjectedMappings] = useState<Set<string>>(new Set());
  const [expandedSnippets, setExpandedSnippets] = useState<Set<string>>(new Set());

  const handleObjection = (mappingId: string) => {
    setObjectedMappings(prev => {
      const newSet = new Set(prev);
      if (newSet.has(mappingId)) {
        newSet.delete(mappingId);
      } else {
        newSet.add(mappingId);
      }
      return newSet;
    });
  };

  const toggleSnippets = (mappingId: string) => {
    setExpandedSnippets(prev => {
      const newSet = new Set(prev);
      if (newSet.has(mappingId)) {
        newSet.delete(mappingId);
      } else {
        newSet.add(mappingId);
      }
      return newSet;
    });
  };

  const filteredMappings = mockInstitutionalMappings.filter(mapping => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchesCriterion = mapping.criterionText.toLowerCase().includes(query);
      const matchesProtocol = mapping.protocol.toLowerCase().includes(query);
      const matchesSite = mapping.contributingSite.toLowerCase().includes(query);
      if (!matchesCriterion && !matchesProtocol && !matchesSite) {
        return false;
      }
    }

    if (selectedProtocol !== 'all' && mapping.protocol !== selectedProtocol) {
      return false;
    }

    if (selectedType !== 'all' && mapping.criteriaType !== selectedType) {
      return false;
    }

    return true;
  });

  const protocols = Array.from(new Set(mockInstitutionalMappings.map(m => m.protocol)));

  return (
    <TooltipProvider>
      <div className="flex flex-col h-full bg-gray-50">
        {/* Header */}
        <div className="bg-white border-b px-4 py-3">
          <h3 className="text-gray-900 flex items-center gap-2" style={{ fontSize: '16px' }}>
            <FileCheck className="w-5 h-5 text-teal-600" />
            Institutional Mapping Memory
          </h3>
          <p className="text-gray-600 mt-1" style={{ fontSize: '12px' }}>
            Reuse approved mappings from {mockInstitutionalMappings.length} protocols across the
            network
          </p>
        </div>

        {/* Search and Filters */}
        <div className="bg-white border-b px-4 py-3 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Filter by protocol, criteria, or site..."
              className="pl-10"
              style={{ fontSize: '14px', height: '36px' }}
            />
          </div>

          <div className="flex gap-2">
            <select
              value={selectedProtocol}
              onChange={e => setSelectedProtocol(e.target.value)}
              className="flex-1 h-9 px-3 rounded-md border border-gray-200 bg-white text-gray-900"
              style={{ fontSize: '12px' }}
            >
              <option value="all">All Protocols</option>
              {protocols.map(protocol => (
                <option key={protocol} value={protocol}>
                  {protocol}
                </option>
              ))}
            </select>

            <select
              value={selectedType}
              onChange={e => setSelectedType(e.target.value)}
              className="flex-1 h-9 px-3 rounded-md border border-gray-200 bg-white text-gray-900"
              style={{ fontSize: '12px' }}
            >
              <option value="all">All Types</option>
              <option value="inclusion">Inclusion</option>
              <option value="exclusion">Exclusion</option>
            </select>
          </div>
        </div>

        {/* Mapping Cards */}
        <ScrollArea className="flex-1">
          <div className="p-4 space-y-3">
            {filteredMappings.map(mapping => {
              const hasObjection = objectedMappings.has(mapping.id);
              return (
                <div
                  key={mapping.id}
                  className={`bg-white rounded-lg border p-3 hover:shadow-sm transition-all ${
                    hasObjection
                      ? 'border-orange-300 bg-orange-50/30'
                      : 'border-gray-200 hover:border-teal-300'
                  }`}
                >
                  {/* Criterion Type Badge */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className={`${
                          mapping.criteriaType === 'inclusion'
                            ? 'bg-green-50 text-green-700 border-green-200'
                            : 'bg-red-50 text-red-700 border-red-200'
                        }`}
                        style={{ fontSize: '10px' }}
                      >
                        {mapping.criteriaType.toUpperCase()}
                      </Badge>
                      {hasObjection && (
                        <Badge
                          variant="outline"
                          className="bg-orange-100 text-orange-700 border-orange-300 gap-1"
                          style={{ fontSize: '10px' }}
                        >
                          <AlertTriangle className="w-3 h-3" />
                          Objection Filed
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant="outline"
                        className="bg-teal-50 text-teal-700 border-teal-200 gap-1"
                        style={{ fontSize: '10px' }}
                      >
                        <TrendingUp className="w-3 h-3" />
                        {mapping.reuseCount}
                      </Badge>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            onClick={() => handleObjection(mapping.id)}
                            className={`rounded p-1 transition-colors ${
                              hasObjection
                                ? 'bg-orange-100 text-orange-700 hover:bg-orange-200'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                            aria-label="Flag mapping objection"
                          >
                            <AlertTriangle className="w-3.5 h-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="left">
                          <p style={{ fontSize: '12px' }}>
                            {hasObjection ? 'Remove objection' : 'Flag mapping for review'}
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </div>

                  {/* Criterion Text */}
                  <p className="text-gray-900 mb-2" style={{ fontSize: '13px', lineHeight: '1.4' }}>
                    {mapping.criterionText}
                  </p>

                  {/* Mapping Details */}
                  <div className="bg-teal-50 border border-teal-100 rounded p-2 mb-2">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-gray-700 font-mono" style={{ fontSize: '12px' }}>
                        {mapping.mappingSystem}:{mapping.mappingCode}
                      </span>
                    </div>
                    <p className="text-gray-600" style={{ fontSize: '11px' }}>
                      {mapping.mappingDescription}
                    </p>
                  </div>

                  {/* Metadata */}
                  <div className="flex items-center justify-between mb-3">
                    <div
                      className="flex items-center gap-1 text-gray-600"
                      style={{ fontSize: '11px' }}
                    >
                      <MapPin className="w-3 h-3" />
                      {mapping.contributingSite}
                    </div>
                    <div className="text-gray-500" style={{ fontSize: '11px' }}>
                      {mapping.protocol}
                    </div>
                  </div>

                  {/* Applied at Sites */}
                  <div className="bg-gray-50 border border-gray-200 rounded p-2 mb-2">
                    <div className="flex items-center gap-1 mb-1">
                      <MapPin className="w-3 h-3 text-gray-500" />
                      <span
                        className="text-gray-700"
                        style={{ fontSize: '11px', fontWeight: '500' }}
                      >
                        Applied at {mapping.appliedAtSites.length} sites:
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {mapping.appliedAtSites.slice(0, 5).map((site, idx) => (
                        <Badge
                          key={idx}
                          variant="outline"
                          className="bg-white text-gray-600 border-gray-300"
                          style={{ fontSize: '10px' }}
                        >
                          {site}
                        </Badge>
                      ))}
                      {mapping.appliedAtSites.length > 5 && (
                        <Badge
                          variant="outline"
                          className="bg-white text-gray-600 border-gray-300"
                          style={{ fontSize: '10px' }}
                        >
                          +{mapping.appliedAtSites.length - 5} more
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* EMR Snippets Toggle Button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleSnippets(mapping.id)}
                    className="w-full gap-2 justify-between"
                    style={{ fontSize: '12px', height: '32px' }}
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="w-3.5 h-3.5" />
                      <span>Raw EMR Snippets ({mapping.emrSnippets.length})</span>
                    </div>
                    {expandedSnippets.has(mapping.id) ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </Button>

                  {/* EMR Snippets Expanded Content */}
                  {expandedSnippets.has(mapping.id) && (
                    <div className="mt-2 space-y-2 border-t pt-2">
                      {mapping.emrSnippets.map((snippet, idx) => (
                        <div key={idx} className="bg-blue-50 border border-blue-200 rounded p-2">
                          <div className="flex items-center justify-between mb-1">
                            <span
                              className="text-blue-900"
                              style={{ fontSize: '11px', fontWeight: '500' }}
                            >
                              {snippet.source}
                            </span>
                            <span className="text-blue-600" style={{ fontSize: '10px' }}>
                              {snippet.date}
                            </span>
                          </div>
                          <p
                            className="text-gray-700 font-mono whitespace-pre-wrap"
                            style={{ fontSize: '11px', lineHeight: '1.5' }}
                          >
                            {snippet.text}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {filteredMappings.length === 0 && (
              <div className="text-center py-8">
                <p className="text-gray-500" style={{ fontSize: '13px' }}>
                  No mappings found matching your filters
                </p>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Footer Actions */}
        <div className="bg-white border-t px-4 py-3">
          {/* Export Button */}
          <Button
            variant="outline"
            className="w-full gap-2"
            style={{ fontSize: '13px', height: '36px' }}
          >
            <Download className="w-4 h-4" />
            Export Mappings for Compliance
          </Button>
        </div>
      </div>
    </TooltipProvider>
  );
}
