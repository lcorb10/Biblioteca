// Biblioteca · interacciones de la interfaz
(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const icons = () => window.lucide && lucide.createIcons();

  /* ---------- toasts ---------- */
  document.querySelectorAll(".toast").forEach((t, i) => {
    const close = () => { t.classList.add("out"); setTimeout(() => t.remove(), 300); };
    t.querySelector("button")?.addEventListener("click", close);
    setTimeout(close, 5200 + i * 600);
  });

  /* ---------- contadores que suben ---------- */
  const runCounters = () => document.querySelectorAll("[data-count]").forEach((el) => {
    const end = Number(el.dataset.count);
    if (reduce || !end) { el.textContent = end; return; }
    const t0 = performance.now(), dur = 900;
    const step = (t) => {
      const p = Math.min((t - t0) / dur, 1);
      el.textContent = Math.round(end * (1 - Math.pow(1 - p, 4)));
      if (p < 1) requestAnimationFrame(step);
    };
    el.textContent = 0;
    requestAnimationFrame(step);
  });

  /* ---------- bienvenida después de iniciar sesión ---------- */
  const root = document.documentElement;
  const intro = document.getElementById("intro");
  if (intro && root.classList.contains("intro-playing")) {
    try { sessionStorage.removeItem("bib-intro"); } catch (e) {}
    document.querySelectorAll("[data-count]").forEach((el) => (el.textContent = 0));
    let done = false;
    const end = () => {
      if (done) return;
      done = true;
      root.classList.remove("intro-playing");
      runCounters();
    };
    const timer = setTimeout(end, 3000);
    const skip = () => { clearTimeout(timer); intro.classList.add("skip"); setTimeout(end, 300); };
    intro.addEventListener("click", skip);
    addEventListener("keydown", skip, { once: true });
  } else {
    root.classList.remove("intro-playing");
    runCounters();
  }

  /* ---------- confirmación antes de eliminar ---------- */
  const dlg = document.getElementById("confirm");
  let pending = null;
  document.querySelectorAll("form[data-confirm]").forEach((f) => {
    f.addEventListener("submit", (e) => {
      if (f.dataset.ok) return;
      e.preventDefault();
      pending = f;
      dlg.querySelector("h2").textContent = f.dataset.confirm;
      dlg.querySelector("p").textContent = f.dataset.detail || "Esta acción no se puede deshacer.";
      dlg.showModal();
    });
  });
  dlg?.addEventListener("close", () => {
    if (dlg.returnValue === "ok" && pending) { pending.dataset.ok = "1"; pending.requestSubmit(); }
    pending = null;
  });

  /* ---------- estado de carga al enviar ---------- */
  document.querySelectorAll("form:not([method=get])").forEach((f) => {
    f.addEventListener("submit", (e) => {
      if (e.defaultPrevented) return;
      const b = e.submitter || f.querySelector("[type=submit]");
      if (b) setTimeout(() => b.classList.add("loading"), 0);
    });
  });

  /* ---------- aprobar / rechazar: la solicitud sale de la lista ---------- */
  document.querySelectorAll(".req form").forEach((f) => {
    f.addEventListener("submit", (e) => {
      if (reduce || f.dataset.go) return;
      e.preventDefault();
      f.dataset.go = "1";
      const action = e.submitter?.formAction;
      if (action) f.action = action;
      f.closest(".req").classList.add("leaving");
      setTimeout(() => f.submit(), 220);
    });
  });

  /* ---------- campos de tokens (autores / categorías) ---------- */
  document.querySelectorAll("[data-tokens]").forEach((box) => {
    const hidden = box.querySelector("input[type=hidden]");
    const input = box.querySelector("input[type=text]");
    const wrap = box.querySelector(".tokens");
    const suggest = box.querySelector(".suggest");
    let vals = hidden.value.split(",").map((s) => s.trim()).filter(Boolean);

    const sync = () => {
      hidden.value = vals.join(", ");
      wrap.querySelectorAll(".token").forEach((t) => t.remove());
      vals.forEach((v, i) => {
        const t = document.createElement("span");
        t.className = "token";
        t.textContent = v;
        const x = document.createElement("button");
        x.type = "button";
        x.setAttribute("aria-label", `Quitar ${v}`);
        x.innerHTML = '<i data-lucide="x"></i>';
        x.onclick = () => { vals.splice(i, 1); sync(); };
        t.append(x);
        wrap.insertBefore(t, input);
      });
      suggest?.querySelectorAll("button").forEach((b) => (b.hidden = vals.includes(b.textContent)));
      icons();
    };
    const add = (v) => {
      v = v.trim().replace(/,$/, "").trim();
      if (v && !vals.some((x) => x.toLowerCase() === v.toLowerCase())) vals.push(v);
      input.value = "";
      sync();
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(input.value); }
      else if (e.key === "Backspace" && !input.value && vals.length) { vals.pop(); sync(); }
    });
    input.addEventListener("blur", () => input.value && add(input.value));
    wrap.addEventListener("click", () => input.focus());
    suggest?.querySelectorAll("button").forEach((b) => (b.onclick = () => add(b.textContent)));
    input.form.addEventListener("submit", () => input.value && add(input.value));
    sync();
  });

  /* ---------- vista previa de multa (devoluciones) ---------- */
  const fine = document.querySelector("[data-fine]");
  if (fine) {
    const sel = document.getElementById("id_prestamo");
    const fd = document.getElementById("fecha_devolucion");
    const tarifa = Number(fine.dataset.fine);
    const fmt = (n) => "$" + Math.round(n).toLocaleString("es-CO");
    const calc = () => {
      const opt = sel.selectedOptions[0];
      if (!opt || !opt.dataset.vence) return;
      const venc = new Date(opt.dataset.vence + "T00:00");
      const dev = new Date(fd.value + "T00:00");
      const dias = Math.max(Math.round((dev - venc) / 86400000), 0);
      fine.classList.toggle("late", dias > 0);
      fine.querySelector("b").textContent = dias ? fmt(dias * tarifa) : "Sin multa";
      fine.querySelector("span").textContent = dias
        ? `${dias} día${dias > 1 ? "s" : ""} de retraso × ${fmt(tarifa)} por día`
        : `A tiempo: vencía el ${opt.dataset.venceTxt}`;
      const b = fine.querySelector("b");
      b.style.animation = "none"; b.offsetHeight; b.style.animation = "";
      document.getElementById("detalle-prestamo").textContent = opt.dataset.info;
    };
    sel.addEventListener("change", calc);
    fd.addEventListener("input", calc);
    calc();
  }

  /* ---------- mostrar / ocultar clave ---------- */
  document.querySelectorAll(".pw button").forEach((b) => {
    b.addEventListener("click", () => {
      const i = b.previousElementSibling;
      const show = i.type === "password";
      i.type = show ? "text" : "password";
      b.setAttribute("aria-label", show ? "Ocultar" : "Mostrar");
      b.innerHTML = `<i data-lucide="${show ? "eye-off" : "eye"}"></i>`;
      icons();
    });
  });

  /* ---------- tooltip de los lomos del estante ---------- */
  const tip = document.createElement("div");
  tip.className = "float-tip";
  tip.setAttribute("aria-hidden", "true");
  document.body.append(tip);
  document.querySelectorAll(".spine").forEach((s) => {
    const src = s.querySelector("[data-tip]");
    if (!src) return;
    const show = () => {
      const r = s.getBoundingClientRect();
      tip.innerHTML = src.innerHTML;
      tip.style.left = r.left + r.width / 2 + "px";
      tip.style.top = r.top - 14 + "px";
      tip.classList.add("show");
    };
    const hide = () => tip.classList.remove("show");
    s.addEventListener("mouseenter", show);
    s.addEventListener("focus", show);
    s.addEventListener("mouseleave", hide);
    s.addEventListener("blur", hide);
  });

  /* ---------- buscador rápido (Ctrl+K) ---------- */
  const pal = document.getElementById("palette");
  if (pal) {
    const data = JSON.parse(document.getElementById("pal-data").textContent);
    const q = document.getElementById("pal-q");
    const list = document.getElementById("pal-list");
    const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
    const hl = (txt, term) => {
      if (!term) return esc(txt);
      const i = norm(txt).indexOf(norm(term));
      return i < 0 ? esc(txt) : esc(txt.slice(0, i)) + "<mark>" + esc(txt.slice(i, i + term.length)) + "</mark>" + esc(txt.slice(i + term.length));
    };
    const ini = (t) => t.split(/\s+/).filter((w) => w.length > 2).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    let items = [], sel = 0;

    const render = () => {
      const term = q.value.trim(), n = norm(term);
      items = [];
      let html = "";
      const books = data.libros.filter((b) => !n || norm(b.t).includes(n) || norm(b.a).includes(n) || b.i.includes(term)).slice(0, 6);
      if (books.length) {
        html += `<div class="pal-group">${term ? "Libros" : "Catálogo"}</div>`;
        books.forEach((b) => {
          const url = data.staff ? data.editar.replace("__ISBN__", encodeURIComponent(b.i)) : `${data.catalogo}?isbn=${encodeURIComponent(b.i)}`;
          items.push(url);
          html += `<a class="pal-item" href="${esc(url)}" role="option">
            <div class="mini-cover" style="--c:${esc(b.c)}">${esc(ini(b.t))}<img class="real" src="https://covers.openlibrary.org/b/isbn/${esc(b.i)}-M.jpg?default=false" alt="" onload="this.naturalWidth>10?this.classList.add('ok'):this.remove()" onerror="this.remove()"></div>
            <div><b>${hl(b.t, term)}</b><small>${hl(b.a, term)} · ${esc(b.i)}</small></div>
            <span class="avail ${b.d ? "" : "none"}">${b.d ? b.d + " de " + b.n + " disp." : "Sin disponibles"}</span></a>`;
        });
      }
      if (term) {
        html += `<div class="pal-group">Buscar «${esc(term)}»</div>`;
        data.buscar.forEach(([label, icon, base]) => {
          const url = base + encodeURIComponent(term);
          items.push(url);
          html += `<a class="pal-item" href="${esc(url)}" role="option"><span class="ico"><i data-lucide="${icon}"></i></span>
            <div><b>${esc(label)}</b><small>«${esc(term)}»</small></div><span class="go"><i data-lucide="corner-down-left"></i></span></a>`;
        });
      }
      const go = data.ir.filter(([label]) => !n || norm(label).includes(n));
      if (go.length) {
        html += `<div class="pal-group">Ir a</div>`;
        go.forEach(([label, icon, url]) => {
          items.push(url);
          html += `<a class="pal-item" href="${esc(url)}" role="option"><span class="ico"><i data-lucide="${icon}"></i></span>
            <div><b>${hl(label, term)}</b></div><span class="go"><i data-lucide="corner-down-left"></i></span></a>`;
        });
      }
      list.innerHTML = html || `<div class="pal-empty">Sin resultados para «${esc(term)}»</div>`;
      sel = 0;
      mark();
      icons();
    };
    const mark = () => {
      list.querySelectorAll(".pal-item").forEach((el, i) => {
        el.setAttribute("aria-selected", i === sel);
        if (i === sel) el.scrollIntoView({ block: "nearest" });
      });
    };
    const open = () => { q.value = ""; render(); pal.showModal(); q.focus(); };
    document.querySelectorAll("[data-palette]").forEach((b) => b.addEventListener("click", open));
    document.addEventListener("keydown", (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
      if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing && !pal.open)) {
        e.preventDefault();
        pal.open ? pal.close() : open();
      }
    });
    q.addEventListener("input", render);
    q.addEventListener("keydown", (e) => {
      const count = list.querySelectorAll(".pal-item").length;
      if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % count; mark(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = (sel - 1 + count) % count; mark(); }
      else if (e.key === "Enter" && items[sel]) { e.preventDefault(); location.href = items[sel]; }
    });
    list.addEventListener("mousemove", (e) => {
      const it = e.target.closest(".pal-item");
      if (!it) return;
      const i = [...list.querySelectorAll(".pal-item")].indexOf(it);
      if (i !== sel) { sel = i; mark(); }
    });
    pal.addEventListener("click", (e) => { if (e.target === pal) pal.close(); });
  }

  /* ---------- filtro instantáneo de tablas y catálogo ---------- */
  document.querySelectorAll("input[data-live]").forEach((inp) => {
    const scope = document.querySelector(inp.dataset.live);
    if (!scope) return;
    const rows = [...scope.querySelectorAll(scope.matches(".catalog") ? ".book" : "tbody tr")];
    const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    const texts = rows.map((r) => norm(r.textContent));
    let empty = null;
    inp.addEventListener("input", () => {
      const n = norm(inp.value.trim());
      let shown = 0;
      rows.forEach((r, i) => {
        const ok = !n || texts[i].includes(n);
        r.classList.toggle("hidden-row", !ok);
        shown += ok;
      });
      if (scope.tagName === "TABLE") {
        if (!shown && !empty) {
          empty = document.createElement("tr");
          empty.className = "live-empty";
          empty.innerHTML = `<td colspan="9">Nada coincide con lo que escribes. Pulsa Enter para buscar en la base de datos.</td>`;
          scope.querySelector("tbody").append(empty);
        } else if (shown && empty) { empty.remove(); empty = null; }
      }
    });
  });

  /* ---------- filtros que se envían solos ---------- */
  document.querySelectorAll("form[data-auto] select, form[data-auto] input[type=checkbox]").forEach((el) =>
    el.addEventListener("change", () => el.form.requestSubmit())
  );

  icons();
})();
