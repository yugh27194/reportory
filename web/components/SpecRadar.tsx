"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Minus, Plus, Target } from "lucide-react";
import { useState } from "react";
import { ErrorText } from "@/components/ErrorText";
import { put } from "@/lib/api";
import { josa } from "@/lib/text";
import { ITEM_TYPE_LABELS, type Growth, type RadarAxis, type SpecPreset } from "@/lib/types";

/** 레이더 전용 색(팔레트 예외, decisions.md): 목표 기준선은 주홍, 내 현황은 파랑. */
export const RADAR_TARGET = "#F2552C";
export const RADAR_MINE = "#2F6FE4";

const SIZE = 320;
const C = SIZE / 2;
const R = 112;

function point(i: number, n: number, ratio: number) {
  const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
  return [C + Math.cos(a) * R * ratio, C + Math.sin(a) * R * ratio] as const;
}

function polygon(values: number[], max: number) {
  return values.map((v, i) => point(i, values.length, Math.min(v, max) / max).join(",")).join(" ");
}

export function RadarChart({
  axes,
  values,
  target,
}: {
  axes: RadarAxis[];
  values: Record<RadarAxis, number>;
  target: Record<RadarAxis, number>;
}) {
  const n = axes.length;
  const mine = axes.map((a) => values[a] ?? 0);
  const goal = axes.map((a) => target[a] ?? 0);
  const max = Math.max(3, ...mine, ...goal);
  const step = max <= 6 ? 1 : Math.ceil(max / 5);
  const rings = Array.from({ length: Math.floor(max / step) }, (_, i) => (i + 1) * step);

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-auto w-full max-w-[340px]" role="img" aria-label="스펙 레이더">
      <defs>
        <radialGradient id="radar-bg" cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#fffcf5" />
          <stop offset="1" stopColor="#fff7e6" />
        </radialGradient>
      </defs>
      <polygon points={polygon(Array(n).fill(max), max)} fill="url(#radar-bg)" stroke="#ebe4d6" />
      {rings.map((r) => (
        <polygon key={r} points={polygon(Array(n).fill(r), max)} fill="none" stroke="#ebe4d6" strokeDasharray="2 3" />
      ))}
      {axes.map((_, i) => {
        const [x, y] = point(i, n, 1);
        return <line key={i} x1={C} y1={C} x2={x} y2={y} stroke="#ebe4d6" />;
      })}
      {rings.map((r) => {
        const [x, y] = point(0, n, r / max);
        return (
          <text key={`t${r}`} x={x + 4} y={y + 3} fontSize="8" fill="#5b6673">
            {r}
          </text>
        );
      })}
      <polygon
        points={polygon(mine, max)}
        fill={RADAR_MINE}
        fillOpacity=".28"
        stroke={RADAR_MINE}
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {mine.map((v, i) => {
        const [x, y] = point(i, n, Math.min(v, max) / max);
        return <circle key={i} cx={x} cy={y} r="3" fill={RADAR_MINE} />;
      })}
      <polygon points={polygon(goal, max)} fill="none" stroke={RADAR_TARGET} strokeWidth="2.5" strokeLinejoin="round" />
      {axes.map((a, i) => {
        const [x, y] = point(i, n, 1.2);
        const short = (values[a] ?? 0) < (target[a] ?? 0);
        return (
          <g key={a}>
            <text x={x} y={y - 2} textAnchor="middle" fontSize="11" fontWeight="600" fill="#0e1b2a">
              {ITEM_TYPE_LABELS[a]}
            </text>
            <text x={x} y={y + 11} textAnchor="middle" fontSize="10" fill={short ? RADAR_TARGET : "#5b6673"}>
              {values[a] ?? 0} / {target[a] ?? 0}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** 레이더와 목표 기준선 고르기·고치기. */
export function SpecRadar({ growth }: { growth: Growth }) {
  const qc = useQueryClient();
  const { axes, values, target } = growth.radar;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(target.values);
  const save = useMutation({
    mutationFn: (body: { preset: SpecPreset; values?: Record<RadarAxis, number> }) => put("/me/spec-target", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["growth"] }),
  });
  const shown = editing ? draft : target.values;
  const gaps = axes.filter((a) => (values[a] ?? 0) < (target.values[a] ?? 0));

  return (
    <div className="flex flex-col items-center gap-4">
      <RadarChart axes={axes} values={values} target={shown} />
      <div className="flex flex-wrap items-center justify-center gap-4 text-xs text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-5 rounded" style={{ background: RADAR_TARGET }} /> 목표 기준선
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-sm" style={{ background: RADAR_MINE, opacity: 0.45 }} /> 내 스펙
        </span>
      </div>
      <div className="w-full space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Target size={15} className="shrink-0" style={{ color: RADAR_TARGET }} />
          <select
            className="input w-auto flex-1 py-1.5"
            value={target.preset}
            onChange={(e) => {
              const preset = e.target.value as SpecPreset;
              if (preset === "custom") {
                setDraft(target.values);
                setEditing(true);
              } else {
                setEditing(false);
                save.mutate({ preset });
              }
            }}
          >
            {Object.entries(growth.presets).map(([k, p]) => (
              <option key={k} value={k}>
                {p.label}
              </option>
            ))}
            <option value="custom">직접 정하기</option>
          </select>
          {!editing && (
            <button
              className="btn btn-sm"
              onClick={() => {
                setDraft(target.values);
                setEditing(true);
              }}
            >
              기준 고치기
            </button>
          )}
        </div>
        {editing && (
          <div className="rounded-xl bg-cream/70 p-3">
            <ul className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              {axes.map((a) => (
                <li key={a} className="flex items-center gap-2">
                  <span className="mr-auto">{ITEM_TYPE_LABELS[a]}</span>
                  <button
                    className="btn-ghost rounded p-1"
                    aria-label={`${ITEM_TYPE_LABELS[a]} 줄이기`}
                    onClick={() =>
                      setDraft({
                        ...draft,
                        [a]: Math.max(0, (draft[a] ?? 0) - 1),
                      })
                    }
                  >
                    <Minus size={13} />
                  </button>
                  <span className="w-5 text-center font-semibold">{draft[a] ?? 0}</span>
                  <button
                    className="btn-ghost rounded p-1"
                    aria-label={`${ITEM_TYPE_LABELS[a]} 늘리기`}
                    onClick={() =>
                      setDraft({
                        ...draft,
                        [a]: Math.min(20, (draft[a] ?? 0) + 1),
                      })
                    }
                  >
                    <Plus size={13} />
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-3 flex justify-end gap-2">
              <button className="btn btn-sm" onClick={() => setEditing(false)}>
                취소
              </button>
              <button
                className="btn btn-primary btn-sm"
                disabled={save.isPending}
                onClick={() => save.mutate({ preset: "custom", values: draft }, { onSuccess: () => setEditing(false) })}
              >
                기준 저장
              </button>
            </div>
          </div>
        )}
        <p className="text-center text-sm text-muted">
          {gaps.length === 0
            ? "모든 축이 목표 기준선에 닿았다."
            : `${josa(gaps.map((a) => ITEM_TYPE_LABELS[a]).join(", "), "이", "가")} 기준선에 못 미친다.`}
        </p>
        <ErrorText error={save.error} />
      </div>
    </div>
  );
}
