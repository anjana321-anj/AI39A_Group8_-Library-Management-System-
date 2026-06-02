const navbar = document.querySelector("[data-navbar]");
const menu = document.querySelector("[data-menu]");
const menuToggle = document.querySelector("[data-menu-toggle]");

if (navbar) {
    window.addEventListener("scroll", () => {
        navbar.classList.toggle("is-scrolled", window.scrollY > 12);
    });
}

if (menu && menuToggle) {
    menuToggle.addEventListener("click", () => {
        const isOpen = menu.classList.toggle("is-open");
        menuToggle.setAttribute("aria-expanded", String(isOpen));
        document.body.classList.toggle("menu-open", isOpen);
    });

    menu.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            menu.classList.remove("is-open");
            menuToggle.setAttribute("aria-expanded", "false");
            document.body.classList.remove("menu-open");
        });
    });
}

const revealObserver = new IntersectionObserver(
    (entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                revealObserver.unobserve(entry.target);
            }
        });
    },
    { threshold: 0.12 }
);

document.querySelectorAll(".reveal").forEach((element) => revealObserver.observe(element));

const counterObserver = new IntersectionObserver(
    (entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;

            const element = entry.target;
            const target = Number(element.dataset.counter || 0);
            const duration = 900;
            const start = performance.now();

            const animate = (now) => {
                const progress = Math.min((now - start) / duration, 1);
                const value = Math.floor(progress * target);
                element.textContent = value.toLocaleString();
                if (progress < 1) requestAnimationFrame(animate);
            };

            requestAnimationFrame(animate);
            counterObserver.unobserve(element);
        });
    },
    { threshold: 0.6 }
);

document.querySelectorAll("[data-counter]").forEach((element) => counterObserver.observe(element));

document.querySelectorAll("[data-ripple]").forEach((button) => {
    button.addEventListener("click", (event) => {
        const rect = button.getBoundingClientRect();
        const ripple = document.createElement("span");
        ripple.className = "ripple";
        ripple.style.left = `${event.clientX - rect.left}px`;
        ripple.style.top = `${event.clientY - rect.top}px`;
        button.appendChild(ripple);
        ripple.addEventListener("animationend", () => ripple.remove());
    });
});

document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", () => {
        const field = toggle.closest(".password-field");
        const input = field ? field.querySelector("[data-password-input]") : null;
        if (!input) return;

        const show = input.type === "password";
        input.type = show ? "text" : "password";
        toggle.textContent = show ? "Hide" : "Show";
    });
});

document.querySelectorAll("[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector("button[type='submit']");
        if (button) {
            button.classList.add("is-loading");
            button.disabled = true;
        }
    });
});

const filterButtons = document.querySelectorAll("[data-filter]");
const filterCards = document.querySelectorAll("[data-category]");

filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const filter = button.dataset.filter;
        filterButtons.forEach((item) => item.classList.toggle("active", item === button));
        filterCards.forEach((card) => {
            const visible = filter === "all" || card.dataset.category === filter;
            card.hidden = !visible;
        });
    });
});

/* ================================================================
   BOOKVERSE EXTENDED JS – new feature interactions
   ================================================================ */

/* ---------- Password-toggle (new [data-pw-toggle] attribute) ---------- */
document.querySelectorAll("[data-pw-toggle]").forEach((toggle) => {
    toggle.addEventListener("click", function () {
        const wrap  = toggle.closest(".input-pw-wrap");
        const input = wrap ? wrap.querySelector("input") : null;
        if (!input) return;
        const show  = input.type === "password";
        input.type  = show ? "text" : "password";
        // Swap icon opacity as visual feedback
        toggle.style.opacity = show ? "1" : "0.55";
    });
});

/* ---------- Auto-dismiss flash messages after 5 s ---------- */
(function () {
    const flashes = document.querySelectorAll(".flash");
    flashes.forEach((flash) => {
        setTimeout(() => {
            flash.style.transition = "opacity .5s, max-height .5s, padding .5s, margin .5s";
            flash.style.opacity    = "0";
            flash.style.maxHeight  = "0";
            flash.style.padding    = "0";
            flash.style.margin     = "0";
            flash.addEventListener("transitionend", () => flash.remove());
        }, 5000);
    });
})();

/* ---------- Stat-card hover glow ---------- */
document.querySelectorAll(".stat-card").forEach((card) => {
    card.addEventListener("mouseenter", () => {
        card.style.boxShadow = "0 8px 32px rgba(31,143,255,.22)";
        card.style.transform = "translateY(-3px)";
    });
    card.addEventListener("mouseleave", () => {
        card.style.boxShadow = "";
        card.style.transform = "";
    });
});

/* ---------- Table row highlight on click ---------- */
document.querySelectorAll(".data-table tbody tr").forEach((row) => {
    row.addEventListener("click", function (e) {
        // Don't intercept button/link clicks
        if (e.target.closest("button, a, form")) return;
        document.querySelectorAll(".data-table tbody tr.row-selected")
            .forEach((r) => r.classList.remove("row-selected"));
        row.classList.toggle("row-selected");
    });
});

/* ---------- Confirm-on-submit for delete forms (fallback) ---------- */
document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
        const msg = form.dataset.confirm || "Are you sure?";
        if (!window.confirm(msg)) e.preventDefault();
    });
});

/* ---------- Book catalog live search ---------- */
(function () {
    const searchInput = document.getElementById("catalogSearch");
    if (!searchInput) return;
    searchInput.addEventListener("input", function () {
        const q = this.value.toLowerCase().trim();
        document.querySelectorAll(".book-card-catalog").forEach((card) => {
            const title  = (card.querySelector("h3")  || {}).textContent || "";
            const author = (card.querySelector(".book-author") || {}).textContent || "";
            card.style.display = (title + author).toLowerCase().includes(q) ? "" : "none";
        });
    });
})();

/* ---------- Profile avatar initials colour cycle ---------- */
(function () {
    const avatar = document.querySelector(".profile-avatar");
    if (!avatar) return;
    const colours = [
        "linear-gradient(135deg,#1f8fff,#7c6af7)",
        "linear-gradient(135deg,#1f9d6a,#4ab8ff)",
        "linear-gradient(135deg,#c37a12,#c64d70)",
        "linear-gradient(135deg,#7c6af7,#c64d70)",
    ];
    const idx = (avatar.textContent.charCodeAt(0) || 0) % colours.length;
    avatar.style.background = colours[idx];
})();

/* ---------- Form validation feedback ---------- */
document.querySelectorAll(".form-control").forEach((input) => {
    input.addEventListener("blur", function () {
        if (this.required && !this.value.trim()) {
            this.style.borderColor = "var(--rose, #c64d70)";
        } else {
            this.style.borderColor = "";
        }
    });
    input.addEventListener("input", function () {
        this.style.borderColor = "";
    });
});

/* ---------- Smooth scroll for anchor links ---------- */
document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
        const target = document.querySelector(this.getAttribute("href"));
        if (target) {
            e.preventDefault();
            target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    });
});

/* ---------- Tilt card effect (home shelf) ---------- */
document.querySelectorAll(".tilt-card").forEach((card) => {
    card.addEventListener("mousemove", (e) => {
        const rect   = card.getBoundingClientRect();
        const x      = e.clientX - rect.left;
        const y      = e.clientY - rect.top;
        const cx     = rect.width  / 2;
        const cy     = rect.height / 2;
        const rx     = ((y - cy) / cy) * 6;
        const ry     = ((x - cx) / cx) * -6;
        card.style.transform = `perspective(600px) rotateX(${rx}deg) rotateY(${ry}deg) scale(1.02)`;
    });
    card.addEventListener("mouseleave", () => {
        card.style.transform = "";
    });
});

/* ---------- Badge click ripple ---------- */
document.querySelectorAll(".badge").forEach((badge) => {
    badge.style.cursor = "default";
});

/* ---------- Admin: preview book cover image URL ---------- */
(function () {
    const imageInput = document.getElementById("image");
    if (!imageInput) return;
    let preview = document.getElementById("coverPreview");
    if (!preview) {
        preview = document.createElement("img");
        preview.id              = "coverPreview";
        preview.style.cssText   = "max-width:100%;max-height:140px;object-fit:cover;border-radius:8px;margin-top:.5rem;display:none;";
        imageInput.parentNode.insertBefore(preview, imageInput.nextSibling);
    }
    function updatePreview() {
        const url = imageInput.value.trim();
        if (url) {
            preview.src          = url;
            preview.style.display = "block";
            preview.onerror      = () => (preview.style.display = "none");
        } else {
            preview.style.display = "none";
        }
    }
    imageInput.addEventListener("input", updatePreview);
    updatePreview();
})();

/* ---------- Dashboard: highlight current user row ---------- */
(function () {
    const currentUserId = document.body.dataset.userId;
    if (!currentUserId) return;
    document.querySelectorAll("tr[data-user-id]").forEach((row) => {
        if (row.dataset.userId === currentUserId) {
            row.style.background = "rgba(31,143,255,.06)";
        }
    });
})();
