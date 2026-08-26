import type { RiskRating } from "../api/types";

const COLORS: Record<RiskRating, string> = {
  LOW: "#2e7d32",
  MEDIUM: "#f9a825",
  HIGH: "#ef6c00",
  CRITICAL: "#c62828",
};

export function RiskBadge({ rating }: { rating: RiskRating }) {
  return (
    <span
      style={{
        backgroundColor: COLORS[rating],
        color: "white",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: 0.5,
      }}
    >
      {rating}
    </span>
  );
}
