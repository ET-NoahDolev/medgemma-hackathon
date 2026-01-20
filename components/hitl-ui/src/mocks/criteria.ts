export interface Criterion {
  id: string;
  type: 'inclusion' | 'exclusion';
  text: string;
  confidence: number;
  status: 'ai-suggested' | 'approved' | 'edited';
  evidenceSnippet?: string;
}

export const mockCriteria: Criterion[] = [
  {
    id: 'I1',
    type: 'inclusion',
    text: 'Age ≥ 45 and ≤ 75 years at time of screening',
    confidence: 0.96,
    status: 'approved',
    evidenceSnippet: 'Section 4.1: Eligible participants must be between 45 and 75 years old...',
  },
  {
    id: 'I2',
    type: 'inclusion',
    text: 'Average-risk for colorectal cancer (no personal or family history)',
    confidence: 0.92,
    status: 'approved',
    evidenceSnippet:
      'Section 4.1.2: Participants should have average risk with no family history of CRC...',
  },
  {
    id: 'I3',
    type: 'inclusion',
    text: 'No colonoscopy in past 10 years',
    confidence: 0.89,
    status: 'ai-suggested',
    evidenceSnippet:
      'Section 4.1.3: Must not have undergone colonoscopy within the last 10 years...',
  },
  {
    id: 'E1',
    type: 'exclusion',
    text: "History of inflammatory bowel disease (Crohn's or ulcerative colitis)",
    confidence: 0.95,
    status: 'approved',
    evidenceSnippet:
      "Section 4.2.1: Exclude patients with IBD including Crohn's disease or ulcerative colitis...",
  },
  {
    id: 'E2',
    type: 'exclusion',
    text: 'Current diagnosis of any cancer',
    confidence: 0.98,
    status: 'approved',
    evidenceSnippet: 'Section 4.2.3: Active cancer diagnosis is an exclusion criterion...',
  },
  {
    id: 'E3',
    type: 'exclusion',
    text: 'Blood pressure >160/100 mmHg despite treatment',
    confidence: 0.85,
    status: 'edited',
    evidenceSnippet:
      'Section 4.2.5: Uncontrolled hypertension defined as BP >160/100 on treatment...',
  },
];
