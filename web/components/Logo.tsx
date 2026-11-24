/** 서비스 로고 ":P". 콜론은 청록, P는 민트로 그린다. animated면 첫 접속 애니메이션용 클래스를 붙인다. */
export function LogoMark({ size = 32, animated = false, className = "" }: { size?: number; animated?: boolean; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label=":P" className={className}>
      <rect width="64" height="64" rx="16" fill="#0E1B2A" />
      <circle className={animated ? "intro-dot intro-dot1" : undefined} cx="19" cy="25" r="4.6" fill="#4FD1C5" />
      <circle className={animated ? "intro-dot intro-dot2" : undefined} cx="19" cy="40" r="4.6" fill="#4FD1C5" />
      <path
        className={animated ? "intro-stem" : undefined}
        d="M32 17 V48"
        stroke="#D9FFF8"
        strokeWidth="7"
        strokeLinecap="round"
        fill="none"
        pathLength={1}
      />
      <path
        className={animated ? "intro-bowl" : undefined}
        d="M32 17 H38.5 A9.75 9.75 0 0 1 38.5 36.5 H32"
        stroke="#D9FFF8"
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        pathLength={1}
      />
    </svg>
  );
}
