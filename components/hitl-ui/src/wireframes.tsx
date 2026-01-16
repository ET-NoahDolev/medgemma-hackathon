import type { ReactElement } from "react";

type WireframeProps = {
  title?: string;
  description?: string;
};

/**
 * Render a placeholder list of protocols for the HITL UI.
 *
 * @param props - Component props for the wireframe.
 * @returns A React element representing the protocol list placeholder.
 *
 * @example
 * ```tsx
 * <ProtocolListWireframe title="Protocols" description="Select a protocol to review." />
 * ```
 *
 * @remarks
 * This wireframe is a visual stub used to map layout and data needs.
 */
export function ProtocolListWireframe({
  title = "Protocols",
  description = "Select a protocol to begin review.",
}: WireframeProps): ReactElement {
  return (
    <section aria-label="Protocol list wireframe">
      <h2>{title}</h2>
      <p>{description}</p>
      <div className="wireframe-panel">Protocol list placeholder</div>
    </section>
  );
}

/**
 * Render a placeholder criterion card for the HITL UI.
 *
 * @param props - Component props for the wireframe.
 * @returns A React element representing a criterion card placeholder.
 *
 * @example
 * ```tsx
 * <CriterionCardWireframe title="Criterion" description="Review criterion text and evidence." />
 * ```
 *
 * @remarks
 * This wireframe highlights fields needed for criterion editing.
 */
export function CriterionCardWireframe({
  title = "Criterion",
  description = "Review criterion text, type, and evidence.",
}: WireframeProps): ReactElement {
  return (
    <section aria-label="Criterion card wireframe">
      <h2>{title}</h2>
      <p>{description}</p>
      <div className="wireframe-card">Criterion details placeholder</div>
    </section>
  );
}

/**
 * Render a placeholder candidate list for SNOMED grounding.
 *
 * @param props - Component props for the wireframe.
 * @returns A React element representing the grounding candidates placeholder.
 *
 * @example
 * ```tsx
 * <GroundingCandidatesWireframe title="SNOMED Candidates" />
 * ```
 *
 * @remarks
 * Use this wireframe to align candidate metadata and actions.
 */
export function GroundingCandidatesWireframe({
  title = "SNOMED Candidates",
  description = "Review and accept candidate SNOMED concepts.",
}: WireframeProps): ReactElement {
  return (
    <section aria-label="Grounding candidates wireframe">
      <h2>{title}</h2>
      <p>{description}</p>
      <div className="wireframe-panel">Candidates placeholder</div>
    </section>
  );
}

/**
 * Render a placeholder audit timeline for HITL actions.
 *
 * @param props - Component props for the wireframe.
 * @returns A React element representing the audit timeline placeholder.
 *
 * @example
 * ```tsx
 * <HitlTimelineWireframe title="Audit Timeline" />
 * ```
 *
 * @remarks
 * This stub captures the audit fields needed for reviewer transparency.
 */
export function HitlTimelineWireframe({
  title = "Audit Timeline",
  description = "Track reviewer actions and rationale.",
}: WireframeProps): ReactElement {
  return (
    <section aria-label="Audit timeline wireframe">
      <h2>{title}</h2>
      <p>{description}</p>
      <div className="wireframe-panel">Audit timeline placeholder</div>
    </section>
  );
}
