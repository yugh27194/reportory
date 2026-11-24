"use client";

import { useState } from "react";
import { ITEM_TYPE_LABELS, ITEM_TYPE_ORDER, type Item, type ItemType } from "@/lib/types";

/**
 * 모아보기의 스킬트리(2.5D). 밑동은 '나', 굵은 가지는 항목 유형, 가지에 달린 잎은 항목 하나다.
 * 바닥 타원, 그림자, 빛 방향 그라데이션으로 입체감을 준다.
 */

const W = 1000;
const H = 690;
const ROOT = { x: 500, y: 600 };
const FORK = { x: 500, y: 410 };

type Placed = { item: Item; x: number; y: number; angle: number };
type Branch = {
  type: ItemType;
  path: string;
  end: { x: number; y: number };
  leaves: Placed[];
  width: number;
};

function layout(items: Item[]): Branch[] {
  const groups = ITEM_TYPE_ORDER.map((t) => ({
    type: t,
    items: items.filter((i) => i.type === t),
  })).filter((g) => g.items.length > 0);
  const n = groups.length;
  return groups.map((g, gi) => {
    const deg = n === 1 ? 0 : -78 + (156 * gi) / (n - 1);
    const a = (deg * Math.PI) / 180;
    // 바깥 가지일수록 줄기 낮은 곳에서 나온다. 끝점은 타원 둘레에 놓는다.
    const start = { x: FORK.x + Math.sin(a) * 12, y: FORK.y + Math.abs(deg) * 1.1 };
    const end = { x: 500 + Math.sin(a) * 400, y: 470 - Math.cos(a) * 360 };
    const ctrl = { x: start.x + (end.x - start.x) * 0.18, y: start.y - (start.y - end.y) * 0.8 - 20 };
    const path = `M${start.x} ${start.y} Q${ctrl.x} ${ctrl.y} ${end.x} ${end.y}`;
    const at = (t: number) => ({
      x: (1 - t) ** 2 * start.x + 2 * (1 - t) * t * ctrl.x + t * t * end.x,
      y: (1 - t) ** 2 * start.y + 2 * (1 - t) * t * ctrl.y + t * t * end.y,
    });
    const count = g.items.length;
    const leaves = g.items.map((item, k) => {
      const t = count === 1 ? 0.75 : 0.3 + (0.62 * k) / (count - 1);
      const p = at(t);
      const q = at(Math.min(1, t + 0.01));
      const dir = Math.atan2(q.y - p.y, q.x - p.x);
      const side = k % 2 === 0 ? 1 : -1;
      const off = 26 + (Math.floor(k / 2) % 2) * 14;
      return {
        item,
        x: p.x + Math.cos(dir + (side * Math.PI) / 2) * off,
        y: p.y + Math.sin(dir + (side * Math.PI) / 2) * off,
        angle: (dir * 180) / Math.PI + side * 50,
      };
    });
    return {
      type: g.type,
      path,
      end,
      leaves,
      width: 7 + Math.min(10, count * 1.3),
    };
  });
}

export function SkillTree({
  items,
  selected,
  onSelect,
}: {
  items: Item[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [hover, setHover] = useState<Placed | null>(null);
  const branches = layout(items);

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="스킬트리">
        <defs>
          <linearGradient id="st-bark" x1="0" x2="1">
            <stop offset="0" stopColor="#9b7653" />
            <stop offset=".6" stopColor="#6e4f34" />
            <stop offset="1" stopColor="#4a3424" />
          </linearGradient>
          <radialGradient id="st-ground" cx=".45" cy=".3" r=".8">
            <stop offset="0" stopColor="#d9fff8" />
            <stop offset="1" stopColor="#4fd1c5" stopOpacity=".35" />
          </radialGradient>
          <radialGradient id="st-aura" cx=".5" cy=".5" r=".5">
            <stop offset="0" stopColor="#4fd1c5" stopOpacity=".22" />
            <stop offset="1" stopColor="#4fd1c5" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="st-leaf" cx=".3" cy=".3" r=".9">
            <stop offset="0" stopColor="#7fc4b4" />
            <stop offset=".6" stopColor="#2d625b" />
            <stop offset="1" stopColor="#163430" />
          </radialGradient>
          <radialGradient id="st-leaf-on" cx=".3" cy=".3" r=".9">
            <stop offset="0" stopColor="#d9fff8" />
            <stop offset=".6" stopColor="#4fd1c5" />
            <stop offset="1" stopColor="#38b2a6" />
          </radialGradient>
          <filter id="st-shadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="3" dy="5" stdDeviation="3" floodColor="#0e1b2a" floodOpacity=".25" />
          </filter>
        </defs>

        <ellipse cx={W / 2} cy={330} rx={440} ry={300} fill="url(#st-aura)" />
        {/* 바닥(2.5D 원판) */}
        <ellipse cx={ROOT.x + 8} cy={ROOT.y + 30} rx={300} ry={46} fill="#0e1b2a" opacity=".08" />
        <ellipse cx={ROOT.x} cy={ROOT.y + 18} rx={290} ry={44} fill="url(#st-ground)" />
        <ellipse cx={ROOT.x} cy={ROOT.y + 18} rx={290} ry={44} fill="none" stroke="#4fd1c5" strokeOpacity=".5" />

        {/* 줄기 */}
        <path
          d={`M${ROOT.x - 34} ${ROOT.y + 14} C ${ROOT.x - 20} 540, ${ROOT.x - 30} 470, ${FORK.x - 14} ${FORK.y}
              L ${FORK.x + 14} ${FORK.y} C ${ROOT.x + 30} 470, ${ROOT.x + 20} 540, ${ROOT.x + 34} ${ROOT.y + 14} Z`}
          fill="url(#st-bark)"
          filter="url(#st-shadow)"
        />

        {branches.map((b) => (
          <g key={b.type}>
            <path
              d={b.path}
              stroke="#0e1b2a"
              strokeOpacity=".12"
              strokeWidth={b.width}
              fill="none"
              transform="translate(4 6)"
            />
            <path d={b.path} stroke="url(#st-bark)" strokeWidth={b.width} fill="none" strokeLinecap="round" />
            {b.leaves.map((l, i) => {
              const on = selected === l.item.id || hover?.item.id === l.item.id;
              return (
                <g
                  key={l.item.id}
                  className="leaf-pop cursor-pointer outline-none"
                  style={{ animationDelay: `${0.4 + i * 0.04}s` }}
                  onMouseEnter={() => setHover(l)}
                  onMouseLeave={() => setHover(null)}
                  onClick={() => onSelect(selected === l.item.id ? null : l.item.id)}
                  role="button"
                  aria-label={l.item.title}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") onSelect(l.item.id);
                  }}
                >
                  <g transform={`translate(${l.x} ${l.y}) rotate(${l.angle}) scale(${on ? 1.35 : 1})`}>
                    <ellipse
                      rx="22"
                      ry="11"
                      fill={on ? "url(#st-leaf-on)" : "url(#st-leaf)"}
                      filter="url(#st-shadow)"
                    />
                    <path d="M-18 0 L18 0" stroke="#d9fff8" strokeOpacity=".5" strokeWidth="1" />
                  </g>
                  {l.item.visibility === "public" && (
                    <circle cx={l.x + 14} cy={l.y - 10} r="4" fill="#4fd1c5" stroke="#fff" strokeWidth="1.5" />
                  )}
                </g>
              );
            })}
            <g transform={`translate(${b.end.x} ${b.end.y})`}>
              <rect x={-44} y={-15} width={88} height={28} rx={14} fill="#0e1b2a" filter="url(#st-shadow)" />
              <text textAnchor="middle" y={4} fontSize="13" fontWeight="700" fill="#fff">
                {ITEM_TYPE_LABELS[b.type]}
                <tspan fill="#4fd1c5"> {b.leaves.length}</tspan>
              </text>
            </g>
          </g>
        ))}

        <g transform={`translate(${ROOT.x} ${ROOT.y + 20})`}>
          <ellipse rx="34" ry="12" cy="6" fill="#0e1b2a" opacity=".2" />
          <circle r="26" fill="#0e1b2a" />
          <circle r="26" fill="none" stroke="#4fd1c5" strokeWidth="2" />
          <text textAnchor="middle" y="6" fontSize="16" fontWeight="800" fill="#4fd1c5">
            나
          </text>
        </g>
      </svg>
      {hover && (
        <div
          className="pointer-events-none absolute z-10 max-w-60 -translate-x-1/2 -translate-y-full rounded-xl bg-ink px-3 py-2 text-xs text-white shadow-lift"
          style={{
            left: `${(hover.x / W) * 100}%`,
            top: `${((hover.y - 18) / H) * 100}%`,
          }}
        >
          <p className="font-semibold">{hover.item.title}</p>
          {hover.item.organization && <p className="text-white/60">{hover.item.organization}</p>}
        </div>
      )}
    </div>
  );
}
