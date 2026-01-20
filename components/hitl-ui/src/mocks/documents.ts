export interface SourceDocument {
  id: string;
  name: string;
  type: 'protocol' | 'ecrf' | 'other';
  uploadDate: string;
  size: string;
  status: 'processed' | 'processing' | 'error';
  criteriaExtracted?: number;
  content: string;
}

export interface Contradiction {
  id: string;
  severity: 'high' | 'medium' | 'low';
  confidence: number;
  title: string;
  description: string;
  sources: {
    documentId: string;
    documentName: string;
    excerpt: string;
    location: string;
  }[];
  aiReasoning: string;
  status: 'open' | 'resolved' | 'dismissed';
  resolution?: {
    resolvedBy: string;
    resolvedAt: string;
    instructions: string;
  };
}

export const mockContradictions: Contradiction[] = [
  {
    id: 'contra-1',
    severity: 'high',
    confidence: 0.92,
    title: 'IBD Diagnosis Conflicts with Colonoscopy Requirement',
    description:
      "The protocol includes patients with Crohn's disease, but the eCRF excludes those who have undergone a colonoscopy. Crohn's diagnosis typically requires a colonoscopy",
    sources: [
      {
        documentId: 'doc-1',
        documentName: 'CRC-Study-Protocol-v2.3.pdf',
        excerpt:
          "Exclude patients with inflammatory bowel disease including Crohn's disease or ulcerative colitis.",
        location: 'Section 4.2.1',
      },
      {
        documentId: 'doc-2',
        documentName: 'eCRF-Template-v1.5.xlsx',
        excerpt: 'No colonoscopy in past 10 years',
        location: 'Eligibility Checklist',
      },
    ],
    aiReasoning:
      "Crohn's disease diagnosis requires endoscopic confirmation via colonoscopy. If a patient has a documented Crohn's diagnosis, they must have had a colonoscopy. This creates a temporal paradox where excluded patients (Crohn's) would violate an inclusion requirement (no colonoscopy in 10 years).",
    status: 'open',
  },
  {
    id: 'contra-2',
    severity: 'medium',
    confidence: 0.78,
    title: 'Age Range Discrepancy Between Documents',
    description:
      'Protocol specifies age 45-75 years, but the eCRF eligibility checklist only mentions "Age 45-75 years" without clarifying if it\'s inclusive or at time of screening vs. enrollment.',
    sources: [
      {
        documentId: 'doc-1',
        documentName: 'CRC-Study-Protocol-v2.3.pdf',
        excerpt:
          'Eligible participants must be between 45 and 75 years old at the time of screening visit.',
        location: 'Section 4.1',
      },
      {
        documentId: 'doc-2',
        documentName: 'eCRF-Template-v1.5.xlsx',
        excerpt: 'Age 45-75 years',
        location: 'Eligibility Checklist',
      },
    ],
    aiReasoning:
      'The protocol explicitly states "at the time of screening visit," but the eCRF doesn\'t specify the timing reference. This could lead to confusion about whether age should be calculated at screening, consent, or enrollment. Additionally, the protocol uses "between" which could be interpreted as exclusive of endpoints (>45 and <75) vs. inclusive (≥45 and ≤75).',
    status: 'open',
  },
  {
    id: 'contra-3',
    severity: 'low',
    confidence: 0.65,
    title: 'Blood Pressure Threshold Minor Inconsistency',
    description:
      'Protocol uses "uncontrolled hypertension" with specific threshold, eCRF uses "Blood pressure controlled" without defining the threshold.',
    sources: [
      {
        documentId: 'doc-1',
        documentName: 'CRC-Study-Protocol-v2.3.pdf',
        excerpt:
          'Patients with uncontrolled hypertension (blood pressure >160/100 mmHg despite antihypertensive therapy) should be excluded.',
        location: 'Section 4.2.5',
      },
      {
        documentId: 'doc-2',
        documentName: 'eCRF-Template-v1.5.xlsx',
        excerpt: 'Blood pressure controlled',
        location: 'Eligibility Checklist',
      },
    ],
    aiReasoning:
      'The eCRF checklist doesn\'t specify what "controlled" means. While the protocol clearly defines >160/100 mmHg as the exclusion threshold, the eCRF could benefit from this specificity to ensure consistent screening across sites.',
    status: 'open',
  },
];

export const mockDocuments: SourceDocument[] = [
  {
    id: 'doc-1',
    name: 'CRC-Study-Protocol-v2.3.pdf',
    type: 'protocol',
    uploadDate: '2024-10-15',
    size: '2.4 MB',
    status: 'processed',
    criteriaExtracted: 12,
    content: `STUDY PROTOCOL

Version 2.3
Date: October 15, 2024

1. STUDY TITLE
Colorectal Cancer Screening Trial: A Multicenter Study

2. OBJECTIVES
Primary: To evaluate the effectiveness of early screening in average-risk populations
Secondary: To assess patient compliance and follow-up rates

3. STUDY POPULATION

3.1 Inclusion Criteria
Participants must meet ALL of the following criteria:

Section 4.1: Eligible participants must be between 45 and 75 years old at the time of screening visit.

Section 4.1.2: Participants should have average risk with no personal or family history of colorectal cancer or advanced adenomas.

Section 4.1.3: Must not have undergone colonoscopy within the last 10 years prior to enrollment.

Section 4.1.4: Willing and able to provide informed consent and comply with study procedures.

3.2 Exclusion Criteria
Participants meeting ANY of the following criteria will be excluded:

Section 4.2.1: Exclude patients with inflammatory bowel disease including Crohn's disease or ulcerative colitis.

Section 4.2.2: History of familial adenomatous polyposis (FAP) or Lynch syndrome.

Section 4.2.3: Active cancer diagnosis is an exclusion criterion for study participation.

Section 4.2.4: Pregnant or breastfeeding women.

Section 4.2.5: Patients with uncontrolled hypertension (blood pressure >160/100 mmHg despite antihypertensive therapy) should be excluded.

Section 4.2.6: History of bleeding disorders or current use of anticoagulation therapy that cannot be safely interrupted.

4. STUDY PROCEDURES
[Additional protocol sections...]`,
  },
  {
    id: 'doc-2',
    name: 'eCRF-Template-v1.5.xlsx',
    type: 'ecrf',
    uploadDate: '2024-10-20',
    size: '456 KB',
    status: 'processed',
    criteriaExtracted: 8,
    content: `ELECTRONIC CASE REPORT FORM (eCRF)
Study: Cauldron Clinical Trial OS

Demographics Section:
- Patient ID: [Auto-generated]
- Date of Birth: [MM/DD/YYYY]
- Age at Screening: [Calculated]
- Gender: [M/F/Other]
- Race/Ethnicity: [Dropdown]

Medical History:
- Personal History of CRC: [Yes/No]
- Family History of CRC: [Yes/No]
- IBD Diagnosis: [Yes/No]
  - If Yes, specify: [Crohn's/UC/Other]
- Prior Colonoscopy: [Yes/No]
  - If Yes, date: [MM/DD/YYYY]

Vital Signs:
- Blood Pressure: [___/___] mmHg
- Heart Rate: [___] bpm
- Temperature: [___] °F

Laboratory Values:
- Hemoglobin: [___] g/dL
- Creatinine: [___] mg/dL

Eligibility Checklist:
□ Age 45-75 years
□ Average risk (no personal/family history)
□ No colonoscopy in past 10 years
□ No IBD diagnosis
□ No active cancer
□ Blood pressure controlled`,
  },
  {
    id: 'doc-3',
    name: 'Amendment-3-Oct-2024.pdf',
    type: 'other',
    uploadDate: '2024-10-25',
    size: '890 KB',
    status: 'processing',
    criteriaExtracted: 0,
    content: '',
  },
];
