import { useEffect, useRef, useState } from "react";
import { site } from "./content.js";


function lerpAngle(from, to, t) {
  let diff = to - from;
  while (diff > Math.PI) diff -= Math.PI * 2;
  while (diff < -Math.PI) diff += Math.PI * 2;
  return from + diff * t;
}

function cover(imgW, imgH, boxW, boxH) {
  const scale = Math.max(boxW / imgW, boxH / imgH);
  const w = imgW * scale;
  const h = imgH * scale;
  return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h };
}

async function loadImage(src) {
  const img = new Image();
  img.decoding = "async";
  img.src = src;
  await img.decode();
  return img;
}

function ArrowIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M3 8h10M9 4l4 4-4 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function App() {
  const canvasRef = useRef(null);
  const [bg, setBg] = useState("#b01a2a");
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState("");
  const finePointer = useFinePointer();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d", { alpha: false });
    let frames = [];
    let center = null;
    let meta = {
      bg: "#b01a2a",
      width: 1280,
      height: 720,
      face: { x: 0.5, y: 0.42 },
    };
    let raf = 0;
    let running = true;
    const pointer = { x: 0, y: 0, active: false };
    let smoothed = 0;
    let primed = false;
    let inDeadzone = true;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const onMove = (event) => {
      pointer.x = event.clientX;
      pointer.y = event.clientY;
      pointer.active = true;
    };

    window.addEventListener("pointermove", onMove, { passive: true });

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const { width, height } = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    const drawImage = (img) => {
      const { width, height } = canvas;
      ctx.fillStyle = meta.bg;
      ctx.fillRect(0, 0, width, height);
      if (!img) return;
      const box = cover(meta.width, meta.height, width, height);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = "high";
      ctx.drawImage(img, box.x, box.y, box.w, box.h);
    };

    const loop = () => {
      if (!running) return;
      if (center) {
        const rect = canvas.getBoundingClientRect();
        const box = cover(meta.width, meta.height, rect.width, rect.height);
        const faceX = rect.left + box.x + meta.face.x * box.w;
        const faceY = rect.top + box.y + meta.face.y * box.h;
        const dx = pointer.x - faceX;
        const dy = pointer.y - faceY;
        const dist = Math.hypot(dx, dy);
        const enter = Math.min(window.innerWidth, window.innerHeight) * 0.12;
        const leave = enter * 1.25;
        if (inDeadzone) inDeadzone = dist < leave;
        else inDeadzone = dist < enter;

        if (pointer.active && !reduceMotion) {
          const target = Math.atan2(dy, dx);
          if (!primed) {
            smoothed = target;
            primed = true;
          } else {
            smoothed = lerpAngle(smoothed, target, 0.26);
          }
        }

        if (!pointer.active || reduceMotion || inDeadzone) {
          drawImage(center);
        } else {
          const norm = ((smoothed % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
          const count = meta.frameCount;
          const index = Math.round((norm / (Math.PI * 2)) * count) % count;
          drawImage(frames[index] || center);
        }
      }
      raf = requestAnimationFrame(loop);
    };

    (async () => {
      const response = await fetch("/frames/meta.json");
      meta = await response.json();
      setBg(meta.bg);
      document.documentElement.style.setProperty("--hero", meta.bg);
      const v = meta.version || 1;
      const [centerImg, ...rest] = await Promise.all([
        loadImage(`/frames/center.webp?v=${v}`),
        ...Array.from({ length: meta.frameCount }, (_, i) =>
          loadImage(`/frames/${String(i).padStart(3, "0")}.webp?v=${v}`)
        ),
      ]);
      center = centerImg;
      frames = rest;
      if (!running) return;
      drawImage(center);
      setReady(true);
      raf = requestAnimationFrame(loop);
    })();

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      observer.disconnect();
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  useEffect(() => {
    const sections = ["work", "about", "contact"]
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target?.id) setActive(visible.target.id);
      },
      { threshold: [0.35, 0.6], rootMargin: "-20% 0px -35% 0px" }
    );
    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, []);

  return (
    <>
      {finePointer ? <CustomCursor /> : null}
      <header className="nav-wrap">
        <nav className="nav" aria-label="Primary">
          {[
            ["work", "Work"],
            ["about", "About"],
            ["contact", "Contact"],
          ].map(([id, label]) => (
            <a key={id} href={`#${id}`} className={active === id ? "is-active" : ""}>
              {label}
            </a>
          ))}
        </nav>
      </header>

      <main>
        <section className="hero" style={{ background: bg }} aria-label="Introduction">
          <canvas ref={canvasRef} className={ready ? "is-ready" : ""} />
          <div className="hero-copy">
            <p className="eyebrow">{site.greeting}</p>
            <h1 className="name">{site.name}</h1>
            <p className="bio">{site.bio}</p>
            <div className="hero-actions">
              <a className="btn btn-solid" href="#resume">
                Resume <ArrowIcon />
              </a>
              <a className="btn btn-glass" href="#contact">
                Let's Talk
              </a>
            </div>
          </div>
        </section>

        <section id="work" className="panel">
          <div className="panel-inner">
            <p className="kicker">Work</p>
            <h2>Things I like to build.</h2>
            <div className="work-list">
              {site.work.map((item) => (
                <article key={item.index} className="work-item">
                  <span className="work-index">{item.index}</span>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                    <ul>
                      {item.tags.map((tag) => (
                        <li key={tag}>{tag}</li>
                      ))}
                    </ul>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="about" className="panel panel-about">
          <div className="panel-inner">
            <p className="kicker">About</p>
            <h2>{site.role}.</h2>
            {site.about.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </section>

        <section id="resume" className="panel panel-resume">
          <div className="panel-inner resume">
            <p className="kicker">Resume</p>
            <h2 className="resume-name">{site.name}</h2>
            <p className="resume-role">{site.role}</p>
            <p className="resume-meta">{site.resume.experience}</p>
            <div className="resume-summary">
              {site.resume.summary.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>

            <div className="resume-block">
              <h3>Technical skills</h3>
              <ul className="skills">
                {site.resume.skills.map((skill) => (
                  <li key={skill}>{skill}</li>
                ))}
              </ul>
            </div>

            <div className="resume-block">
              <h3>Roles and responsibilities</h3>
              <ul className="resume-points">
                {site.resume.responsibilities.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>

            <div className="resume-block">
              <h3>Key areas of experience</h3>
              <div className="resume-areas">
                {site.resume.areas.map((area) => (
                  <article key={area.title}>
                    <h4>{area.title}</h4>
                    <p>{area.text}</p>
                  </article>
                ))}
              </div>
            </div>

            <div className="resume-block">
              <h3>Professional strengths</h3>
              <ul className="skills">
                {site.resume.strengths.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section id="contact" className="panel">
          <div className="panel-inner contact-grid">
            <div>
              <p className="kicker">Contact</p>
              <h2>Tell me what you're making.</h2>
              <p>
                <a className="mail" href={`mailto:${site.email}`}>
                  {site.email}
                </a>
              </p>
            </div>
            <ContactForm />
          </div>
        </section>
      </main>
    </>
  );
}

function ContactForm() {
  const [sent, setSent] = useState(false);

  const onSubmit = (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") || "").trim();
    const message = String(data.get("message") || "").trim();
    const subject = encodeURIComponent(`Portfolio note from ${name || "someone"}`);
    const body = encodeURIComponent(`${message}\n\n— ${name}`);
    window.location.href = `mailto:${site.email}?subject=${subject}&body=${body}`;
    setSent(true);
  };

  return (
    <form className="contact-form" onSubmit={onSubmit}>
      <label>
        Name
        <input name="name" type="text" autoComplete="name" required placeholder="Your name" />
      </label>
      <label>
        Message
        <textarea name="message" required rows="5" placeholder="What should we build?" />
      </label>
      <button className="btn btn-solid btn-dark" type="submit">
        {sent ? "Opening email" : "Send a note"} <ArrowIcon />
      </button>
    </form>
  );
}

function CustomCursor() {
  const dotRef = useRef(null);
  const ringRef = useRef(null);

  useEffect(() => {
    const dot = dotRef.current;
    const ring = ringRef.current;
    if (!dot || !ring) return undefined;
    let raf = 0;
    let running = true;
    const mouse = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const dotPos = { ...mouse };
    const ringPos = { ...mouse };

    const onMove = (event) => {
      mouse.x = event.clientX;
      mouse.y = event.clientY;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const tick = () => {
      if (!running) return;
      dotPos.x += (mouse.x - dotPos.x) * 0.45;
      dotPos.y += (mouse.y - dotPos.y) * 0.45;

      let targetX = mouse.x;
      let targetY = mouse.y;
      let scale = 1;
      const hit = document.elementFromPoint(mouse.x, mouse.y);
      const interactive = hit?.closest?.("a, button, input, textarea");
      if (interactive) {
        const rect = interactive.getBoundingClientRect();
        targetX = mouse.x + (rect.left + rect.width / 2 - mouse.x) * 0.28;
        targetY = mouse.y + (rect.top + rect.height / 2 - mouse.y) * 0.28;
        scale = 1.65;
      }
      ringPos.x += (targetX - ringPos.x) * 0.16;
      ringPos.y += (targetY - ringPos.y) * 0.16;
      dot.style.transform = `translate3d(${dotPos.x}px, ${dotPos.y}px, 0)`;
      ring.style.transform = `translate3d(${ringPos.x}px, ${ringPos.y}px, 0) scale(${scale})`;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      running = false;
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
    };
  }, []);

  return (
    <>
      <div ref={ringRef} className="cursor-ring" />
      <div ref={dotRef} className="cursor-dot" />
    </>
  );
}

function useFinePointer() {
  const [fine, setFine] = useState(true);
  useEffect(() => {
    const media = window.matchMedia("(pointer: fine)");
    const update = () => setFine(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return fine;
}
