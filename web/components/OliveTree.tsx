/**
 * 자라는 올리브 나무(2.5D). level 0 화분 → 1 새싹 → 2 어린 묘목 → 3 묘목 → 4 올리브 나무.
 * 빛은 왼쪽 위에서 오고, 바닥에는 타원 그림자를 깔아 입체감을 준다.
 * 나무 그림에는 자연색(화분 테라코타, 줄기 갈색, 올리브 열매)을 예외로 쓴다(decisions.md).
 */

const TERRACOTTA = ["#e0a07a", "#c9764a", "#9c5434"];
const BARK = ["#9b7653", "#6e4f34", "#4a3424"];

type Leaf = { x: number; y: number; r: number; s?: number; tone?: number };

function OliveLeaf({ x, y, r, s = 1, tone = 0 }: Leaf) {
  const fills = ["url(#ot-leaf)", "url(#ot-leaf-dark)", "url(#ot-leaf-silver)"];
  return (
    <g transform={`translate(${x} ${y}) rotate(${r}) scale(${s})`}>
      <path d="M0 0 C 6 -5, 22 -5, 30 0 C 22 5, 6 5, 0 0 Z" fill={fills[tone % 3]} />
      <path d="M2 0 L27 0" stroke="#d9fff8" strokeOpacity=".35" strokeWidth=".8" />
    </g>
  );
}

/** 줄기를 따라 잎을 번갈아 붙인다. */
function leavesAlong(x0: number, y0: number, x1: number, y1: number, n: number, spread = 1): Leaf[] {
  const out: Leaf[] = [];
  for (let i = 0; i < n; i++) {
    const t = 0.25 + (0.75 * i) / Math.max(1, n - 1);
    const side = i % 2 === 0 ? -1 : 1;
    out.push({
      x: x0 + (x1 - x0) * t,
      y: y0 + (y1 - y0) * t,
      r: side < 0 ? 200 - 25 * spread + i * 3 : -20 + 25 * spread - i * 3,
      s: 0.7 + 0.35 * (1 - t) + 0.1 * spread,
      tone: i,
    });
  }
  return out;
}

function Pot({ cx = 200, top = 360 }: { cx?: number; top?: number }) {
  return (
    <g>
      <ellipse cx={cx} cy={top + 92} rx="86" ry="16" fill="#0e1b2a" opacity=".14" />
      <path
        d={`M${cx - 62} ${top + 12} L${cx - 48} ${top + 86} Q${cx} ${top + 100} ${cx + 48} ${top + 86} L${cx + 62} ${top + 12} Z`}
        fill="url(#ot-pot)"
      />
      <ellipse cx={cx} cy={top + 12} rx="70" ry="15" fill={TERRACOTTA[1]} />
      <ellipse cx={cx} cy={top + 6} rx="72" ry="15" fill="url(#ot-pot)" />
      <ellipse cx={cx} cy={top + 6} rx="60" ry="11" fill="#4a3424" />
      <ellipse cx={cx - 6} cy={top + 4} rx="50" ry="7" fill="#6e4f34" opacity=".7" />
    </g>
  );
}

function Ground({ cx = 200, y = 440, w = 170 }: { cx?: number; y?: number; w?: number }) {
  return (
    <g>
      <ellipse cx={cx} cy={y + 10} rx={w + 10} ry="26" fill="#0e1b2a" opacity=".12" />
      <ellipse cx={cx} cy={y} rx={w} ry="30" fill="url(#ot-ground)" />
      <ellipse cx={cx - 20} cy={y - 8} rx={w * 0.7} ry="14" fill="#d9fff8" opacity=".25" />
      {[-110, -70, 60, 105, 20].map((dx, i) => (
        <path
          key={i}
          d={`M${cx + dx} ${y - 2} q2 -10 4 0 M${cx + dx + 5} ${y - 1} q3 -12 5 1`}
          stroke="#2d625b"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
        />
      ))}
    </g>
  );
}

function Canopy({ blobs, olives = [] }: { blobs: [number, number, number][]; olives?: [number, number][] }) {
  return (
    <g>
      {blobs.map(([x, y, r], i) => (
        <circle key={`b${i}`} cx={x + 6} cy={y + 8} r={r} fill="#0e1b2a" opacity=".18" />
      ))}
      {blobs.map(([x, y, r], i) => (
        <circle key={`d${i}`} cx={x} cy={y} r={r} fill="url(#ot-canopy)" />
      ))}
      {blobs.map(([x, y, r], i) => (
        <circle key={`h${i}`} cx={x - r * 0.3} cy={y - r * 0.35} r={r * 0.45} fill="#d9fff8" opacity=".16" />
      ))}
      {blobs.flatMap(([x, y, r], i) =>
        [0, 1, 2, 3].map((k) => {
          const a = ((i * 67 + k * 97) % 360) * (Math.PI / 180);
          return (
            <OliveLeaf
              key={`l${i}-${k}`}
              x={x + Math.cos(a) * r * 0.72}
              y={y + Math.sin(a) * r * 0.72}
              r={(a * 180) / Math.PI + 100}
              s={0.55}
              tone={(i + k) % 3}
            />
          );
        }),
      )}
      {olives.map(([x, y], i) => (
        <g key={`o${i}`}>
          <ellipse cx={x} cy={y} rx="5" ry="6.5" fill={i % 3 === 0 ? "#7c8f3c" : "#2a2540"} />
          <ellipse cx={x - 1.5} cy={y - 2.5} rx="1.6" ry="2" fill="#fff" opacity=".45" />
        </g>
      ))}
    </g>
  );
}

function Stage({ level }: { level: number }) {
  if (level <= 0)
    return (
      <g>
        <Pot />
        <ellipse cx="200" cy="364" rx="7" ry="4" fill="#9b7653" />
        <ellipse cx="198" cy="362" rx="3" ry="1.5" fill="#fff" opacity=".4" />
      </g>
    );
  if (level === 1)
    return (
      <g>
        <Pot />
        <path
          d="M200 366 C 198 345, 203 330, 200 312"
          stroke="#2d625b"
          strokeWidth="4"
          fill="none"
          strokeLinecap="round"
        />
        <OliveLeaf x={200} y={318} r={205} s={0.9} />
        <OliveLeaf x={200} y={318} r={-25} s={0.9} tone={2} />
        <OliveLeaf x={201} y={334} r={-10} s={0.6} tone={1} />
      </g>
    );
  if (level === 2)
    return (
      <g>
        <Pot />
        <path
          d="M200 366 C 194 320, 208 290, 200 250"
          stroke="url(#ot-bark)"
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M201 300 C 214 290, 222 284, 232 270"
          stroke="#6e4f34"
          strokeWidth="3"
          fill="none"
          strokeLinecap="round"
        />
        {leavesAlong(200, 366, 200, 250, 9).map((l, i) => (
          <OliveLeaf key={i} {...l} />
        ))}
        {leavesAlong(201, 300, 232, 270, 4, 0.5).map((l, i) => (
          <OliveLeaf key={`b${i}`} {...l} />
        ))}
        <OliveLeaf x={200} y={252} r={-80} s={0.8} tone={2} />
      </g>
    );
  if (level === 3)
    return (
      <g>
        <Pot />
        <path
          d="M200 368 C 190 320, 212 270, 198 200"
          stroke="url(#ot-bark)"
          strokeWidth="11"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M200 262 C 222 246, 240 232, 256 206"
          stroke="url(#ot-bark)"
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M198 238 C 178 226, 160 214, 148 192"
          stroke="url(#ot-bark)"
          strokeWidth="5"
          fill="none"
          strokeLinecap="round"
        />
        <Canopy
          blobs={[
            [150, 186, 34],
            [256, 196, 36],
            [200, 168, 46],
            [228, 150, 30],
            [172, 150, 28],
          ]}
        />
      </g>
    );
  return (
    <g>
      <Ground />
      {/* 뒤틀린 올리브 줄기 */}
      <path
        d="M178 448 C 184 400, 166 360, 186 316 C 196 292, 186 270, 194 240 L 212 240 C 216 272, 222 296, 214 320 C 206 352, 230 396, 226 448 Z"
        fill="url(#ot-bark)"
      />
      <path d="M190 330 C 196 300, 190 280, 198 250" stroke="#d9fff8" strokeOpacity=".18" strokeWidth="3" fill="none" />
      <path
        d="M198 270 C 160 250, 132 228, 104 196"
        stroke="url(#ot-bark)"
        strokeWidth="12"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M210 262 C 250 246, 280 222, 300 186"
        stroke="url(#ot-bark)"
        strokeWidth="12"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M204 246 C 206 206, 196 170, 204 130"
        stroke="url(#ot-bark)"
        strokeWidth="9"
        fill="none"
        strokeLinecap="round"
      />
      <Canopy
        blobs={[
          [96, 190, 46],
          [302, 180, 48],
          [150, 150, 52],
          [254, 140, 54],
          [204, 112, 58],
          [200, 186, 50],
          [128, 210, 34],
          [278, 214, 34],
          [204, 64, 34],
        ]}
        olives={[
          [118, 214],
          [160, 196],
          [236, 184],
          [282, 212],
          [214, 150],
          [178, 120],
          [264, 112],
          [300, 160],
          [140, 168],
          [214, 86],
          [96, 176],
          [246, 216],
        ]}
      />
    </g>
  );
}

export function OliveTree({
  level,
  className = "",
  sway = true,
  title,
}: {
  level: number;
  className?: string;
  sway?: boolean;
  title?: string;
}) {
  return (
    <svg viewBox="0 0 400 480" className={className} role="img" aria-label={title ?? "올리브 나무"}>
      <defs>
        <linearGradient id="ot-pot" x1="0" x2="1">
          <stop offset="0" stopColor={TERRACOTTA[0]} />
          <stop offset=".55" stopColor={TERRACOTTA[1]} />
          <stop offset="1" stopColor={TERRACOTTA[2]} />
        </linearGradient>
        <linearGradient id="ot-bark" x1="0" x2="1">
          <stop offset="0" stopColor={BARK[0]} />
          <stop offset=".6" stopColor={BARK[1]} />
          <stop offset="1" stopColor={BARK[2]} />
        </linearGradient>
        <radialGradient id="ot-canopy" cx=".35" cy=".3" r=".8">
          <stop offset="0" stopColor="#4f8a7c" />
          <stop offset=".55" stopColor="#2d625b" />
          <stop offset="1" stopColor="#224b46" />
        </radialGradient>
        <radialGradient id="ot-ground" cx=".4" cy=".3" r=".8">
          <stop offset="0" stopColor="#4f8a7c" />
          <stop offset="1" stopColor="#224b46" />
        </radialGradient>
        <linearGradient id="ot-leaf" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#5f9c8c" />
          <stop offset="1" stopColor="#2d625b" />
        </linearGradient>
        <linearGradient id="ot-leaf-dark" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#2d625b" />
          <stop offset="1" stopColor="#163430" />
        </linearGradient>
        <linearGradient id="ot-leaf-silver" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#a9d6cc" />
          <stop offset="1" stopColor="#5f9c8c" />
        </linearGradient>
      </defs>
      <g className={sway ? "olive-sway" : undefined}>
        <Stage level={level} />
      </g>
    </svg>
  );
}

export const STAGE_HINTS = [
  "첫 기록을 남기면 싹이 튼다.",
  "항목을 모을수록 잎이 늘어난다.",
  "가지가 뻗기 시작했다.",
  "곧 열매를 맺을 나무가 된다.",
  "열매를 맺은 올리브 나무다.",
];
