// Category styling — matches spec §9 design direction.
export const CATEGORIES = {
  IR: { label: "IR", color: "wire-ir", textColor: "text-wire-ir", bgColor: "bg-wire-ir/10", borderColor: "border-wire-ir/30" },
  Econ: { label: "Econ", color: "wire-econ", textColor: "text-wire-econ", bgColor: "bg-wire-econ/10", borderColor: "border-wire-econ/30" },
  Business: { label: "Business", color: "wire-business", textColor: "text-wire-business", bgColor: "bg-wire-business/10", borderColor: "border-wire-business/30" },
};

// Canonical stock arguments from spec §8. Pills for these get crisp styling;
// anything outside the list still renders, just neutrally.
export const CANONICAL_STOCK_ARGS = new Set([
  // Economic
  "Dutch Disease", "Moral Hazard", "Race to the Bottom", "Structural Adjustment",
  "Resource Curse", "Dependency Theory", "Brain Drain", "Capital Flight",
  "Rent-Seeking", "Infant Industry", "Comparative Advantage", "Austerity",
  // Political
  "Democratic Backsliding", "Authoritarian Resilience", "Mandate Theory",
  "Slippery Slope", "Regulatory Capture", "Balkanization", "Self-Determination",
  "Humanitarian Intervention",
  // Social
  "Chilling Effect", "Perverse Incentives", "Tragedy of the Commons",
  "Cultural Imperialism", "Tokenism", "Paternalism",
]);
