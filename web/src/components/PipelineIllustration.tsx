export function PipelineIllustration() {
  return (
    <svg aria-hidden="true" viewBox="0 0 420 156" fill="none" className="hidden w-full lg:block">
      <path
        className="overview-flow"
        d="M124 84 C150 84 152 68 174 68 M276 68 C294 68 296 78 310 78"
        stroke="#7CB6DE"
        strokeWidth="1.6"
        strokeDasharray="4 4"
      />
      <circle className="overview-pulse" cx="148" cy="77" r="3.8" fill="var(--pa-teal)" />
      <circle className="overview-pulse" cx="293" cy="72" r="3.8" fill="var(--pa-teal)" />
      <g fill="white" stroke="var(--pa-line)">
        <rect x="8" y="18" width="116" height="122" rx="14" />
        <rect x="174" y="34" width="102" height="68" rx="13" />
        <rect x="310" y="18" width="102" height="122" rx="14" />
      </g>
      <rect x="22" y="32" width="28" height="28" rx="8" fill="var(--pa-soft)" />
      <path
        d="M30 41H42M30 46H42M30 51H37"
        stroke="var(--pa-azure)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M24 74H104 M24 85H90 M24 96H96"
        stroke="var(--pa-line)"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <rect x="22" y="112" width="52" height="14" rx="7" fill="var(--pa-soft)" />
      <circle cx="31" cy="119" r="2.5" fill="var(--pa-teal)" />
      <circle cx="190" cy="50" r="4.5" fill="var(--pa-violet)" />
      <path
        d="M201 50H245 M188 67H260 M188 78H242 M188 89H222"
        stroke="var(--pa-line)"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <circle cx="328" cy="36" r="9" fill="var(--pa-soft)" />
      <path
        d="M328 32V40M324 36H332"
        stroke="var(--pa-azure)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M346 36H392 M324 58H396 M324 69H380"
        stroke="var(--pa-line)"
        strokeWidth="5"
        strokeLinecap="round"
      />
      <rect
        x="322"
        y="86"
        width="78"
        height="38"
        rx="9"
        fill="var(--pa-soft)"
        stroke="var(--pa-line)"
      />
      <path
        d="M332 99H384 M332 109H370"
        stroke="var(--pa-line)"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}
