"use client";

import { useEffect, useRef } from "react";

/**
 * Full-viewport cosmic background: drifting twinkling stars + occasional
 * meteors streaking across. Fixed behind all content.
 * Honors prefers-reduced-motion (one static frame, no meteors).
 */
type Star = {
  x: number;
  y: number;
  r: number;
  a: number;
  tw: number;
  ph: number;
  vx: number;
  vy: number;
};

type Meteor = {
  x: number;
  y: number;
  len: number;
  speed: number;
  ang: number;
  life: number;
  max: number;
  a: number;
};

const PI2 = Math.PI * 2;

export function CosmicBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduce = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    let w = 0;
    let h = 0;
    let stars: Star[] = [];
    const meteors: Meteor[] = [];
    let raf = 0;
    let lastMeteor = 0;

    const resize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(280, Math.floor((w * h) / 7000));
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.3 + 0.25,
        a: Math.random() * 0.5 + 0.15,
        tw: Math.random() * 0.9 + 0.2,
        ph: Math.random() * PI2,
        vx: (Math.random() - 0.5) * 0.03,
        vy: (Math.random() - 0.5) * 0.03,
      }));
    };

    const spawnMeteor = () => {
      meteors.push({
        x: Math.random() * w * 0.6 + w * 0.3,
        y: -20 + Math.random() * h * 0.25,
        len: Math.random() * 200 + 140,
        speed: Math.random() * 6 + 7,
        ang: Math.PI * 0.75 + (Math.random() * 0.2 - 0.1),
        life: 0,
        max: Math.random() * 60 + 70,
        a: Math.random() * 0.5 + 0.4,
      });
    };

    const draw = (t: number) => {
      ctx.clearRect(0, 0, w, h);

      // stars
      for (const s of stars) {
        s.x += s.vx;
        s.y += s.vy;
        if (s.x < 0) s.x += w;
        else if (s.x > w) s.x -= w;
        if (s.y < 0) s.y += h;
        else if (s.y > h) s.y -= h;

        const alpha = s.a * (0.55 + 0.45 * Math.sin(t * 0.001 * s.tw + s.ph));
        if (s.r > 1.05) {
          ctx.strokeStyle = `rgba(255,255,255,${alpha * 0.5})`;
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(s.x - s.r * 3, s.y);
          ctx.lineTo(s.x + s.r * 3, s.y);
          ctx.moveTo(s.x, s.y - s.r * 3);
          ctx.lineTo(s.x, s.y + s.r * 3);
          ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, PI2);
        ctx.fillStyle = `rgba(255,255,255,${alpha})`;
        ctx.fill();
      }

      // meteors
      if (t - lastMeteor > 2400 + Math.random() * 2800) {
        spawnMeteor();
        lastMeteor = t;
      }
      for (let i = meteors.length - 1; i >= 0; i--) {
        const m = meteors[i];
        m.x += Math.cos(m.ang) * m.speed;
        m.y += Math.sin(m.ang) * m.speed;
        m.life += 1;
        const tx = m.x - Math.cos(m.ang) * m.len;
        const ty = m.y - Math.sin(m.ang) * m.len;
        const fade =
          m.life < 10
            ? m.life / 10
            : m.life > m.max - 18
              ? Math.max(0, (m.max - m.life) / 18)
              : 1;
        const grad = ctx.createLinearGradient(m.x, m.y, tx, ty);
        grad.addColorStop(0, `rgba(189,201,230,${m.a * fade})`);
        grad.addColorStop(1, "rgba(189,201,230,0)");
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(m.x, m.y);
        ctx.lineTo(tx, ty);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(m.x, m.y, 1.8, 0, PI2);
        ctx.fillStyle = `rgba(255,255,255,${m.a * fade})`;
        ctx.fill();
        if (m.life > m.max || m.x < -60 || m.y > h + 60) {
          meteors.splice(i, 1);
        }
      }

      raf = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);

    if (reduce) {
      draw(0);
      cancelAnimationFrame(raf);
    } else {
      raf = requestAnimationFrame(draw);
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div className="cosmic-bg" aria-hidden>
      <canvas ref={canvasRef} />
    </div>
  );
}
