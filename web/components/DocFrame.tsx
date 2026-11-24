"use client";

import { useImperativeHandle, useRef, type Ref } from "react";

export type EditPayload = {
  items: Record<string, { title?: string; lines?: string[] }>;
  summary?: string;
};

export type DocFrameHandle = { collect: () => EditPayload };

const EDIT_STYLE = `
[data-edit] { border-radius: 2px; outline: 1px dashed transparent; outline-offset: 1px; transition: outline-color .15s, background .15s; cursor: text; }
[data-edit]:hover { outline-color: #4FD1C5; background: rgba(79,209,197,.10); }
[data-edit]:focus { outline: 2px solid #4FD1C5; background: #fff; }
ul.lines:empty, ul.lines { display: block !important; }
li[data-placeholder]:empty::before { content: "내용을 쓴다"; color: #9aa5ae; }
`;

/**
 * 문서 미리보기. editing이면 iframe 안의 data-edit 요소(제목·문장·요약)를 바로 고칠 수 있게 한다.
 * iframe에서는 스크립트를 돌리지 않는다(allow-same-origin만 주고 부모가 DOM을 다룬다).
 */
export function DocFrame({
  html,
  editing,
  onDirty,
  ref,
}: {
  html: string;
  editing: boolean;
  onDirty?: () => void;
  ref?: Ref<DocFrameHandle>;
}) {
  const frame = useRef<HTMLIFrameElement>(null);

  useImperativeHandle(ref, () => ({
    collect() {
      const doc = frame.current?.contentDocument;
      const out: EditPayload = { items: {} };
      if (!doc) return out;
      const slot = (id: string) => (out.items[id] ??= {});
      doc.querySelectorAll<HTMLElement>('[data-edit="title"]').forEach((el) => {
        if (el.dataset.item) slot(el.dataset.item).title = el.innerText.trim();
      });
      doc.querySelectorAll<HTMLElement>('[data-edit="line"]').forEach((el) => {
        const id = el.dataset.item;
        if (!id) return;
        const s = slot(id);
        s.lines ??= [];
        const text = el.innerText.trim();
        if (text) s.lines.push(`${el.dataset.prefix ?? ""}${text}`);
      });
      // 줄을 모두 지운 항목도 빈 목록으로 보낸다.
      doc.querySelectorAll<HTMLElement>("[data-lines]").forEach((ul) => {
        const id = ul.dataset.lines;
        if (id) slot(id).lines ??= [];
      });
      const summary = doc.querySelector<HTMLElement>('[data-edit="summary"]');
      if (summary) out.summary = summary.innerText.trim();
      return out;
    },
  }));

  function prepare() {
    const doc = frame.current?.contentDocument;
    if (!doc || !editing) return;
    const style = doc.createElement("style");
    style.textContent = EDIT_STYLE;
    doc.head.appendChild(style);
    doc.querySelectorAll<HTMLElement>("ul[data-lines]").forEach((ul) => {
      if (!ul.querySelector("li")) {
        const li = doc.createElement("li");
        li.dataset.edit = "line";
        li.dataset.item = ul.dataset.lines ?? "";
        li.dataset.placeholder = "1";
        ul.appendChild(li);
      }
    });
    doc.querySelectorAll<HTMLElement>("[data-edit]").forEach((el) => {
      el.contentEditable = "true";
      el.spellcheck = false;
      el.title = el.dataset.edit === "line" ? "눌러서 고친다. Enter로 줄을 나눈다." : "눌러서 고친다.";
      if (el.dataset.edit !== "line") {
        el.addEventListener("keydown", (e) => {
          if (e.key === "Enter") e.preventDefault();
        });
      }
    });
    doc.addEventListener("input", () => onDirty?.());
  }

  return (
    <iframe
      key={editing ? "edit" : "view"}
      ref={frame}
      title="문서 미리보기"
      srcDoc={html}
      sandbox={editing ? "allow-same-origin" : ""}
      onLoad={prepare}
      className="mx-auto block h-[1123px] w-full max-w-[794px] rounded bg-white shadow-lift"
    />
  );
}
