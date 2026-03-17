"use client";
import { useEffect, useRef } from "react";

export default function Cursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (dotRef.current) { dotRef.current.style.left = e.clientX + "px"; dotRef.current.style.top = e.clientY + "px"; }
      if (ringRef.current) { ringRef.current.style.left = e.clientX + "px"; ringRef.current.style.top = e.clientY + "px"; }
    };
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  const base: React.CSSProperties = { position: "fixed", borderRadius: "50%", pointerEvents: "none", zIndex: 9999, transform: "translate(-50%,-50%)" };

  return (
    <>
      <div ref={dotRef} style={{ ...base, width: 8, height: 8, background: "var(--main)", transition: "transform 0.1s" }} />
      <div ref={ringRef} style={{ ...base, width: 30, height: 30, border: "2px solid rgba(220,88,185,0.5)", transition: "all 0.15s ease" }} />
    </>
  );
}