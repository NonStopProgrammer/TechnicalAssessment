import type { Citation } from "../api/types";

export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return <p className="muted">No citations.</p>;
  }
  return (
    <ul className="citation-list">
      {citations.map((citation) => (
        <li key={citation.citation_key} title={citation.snippet}>
          [{citation.doc_id} §{citation.clause_id}, v:{citation.version}]
        </li>
      ))}
    </ul>
  );
}
