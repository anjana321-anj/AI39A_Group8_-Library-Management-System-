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

const confirmModal = document.querySelector("[data-confirm-modal]");
const confirmMessage = document.querySelector("[data-confirm-message]");
const confirmAccept = document.querySelector("[data-confirm-accept]");
const confirmCancel = document.querySelector("[data-confirm-cancel]");
let pendingConfirmation = null;
let defaultConfirmAcceptLabel = confirmAccept ? confirmAccept.textContent : "Confirm";

const closeConfirmModal = () => {
    if (!confirmModal) return;
    confirmModal.hidden = true;
    document.body.classList.remove("modal-open");
    if (confirmAccept) confirmAccept.textContent = defaultConfirmAcceptLabel;
    pendingConfirmation = null;
};

const openConfirmModal = (message, onConfirm, acceptLabel) => {
    if (!confirmModal || !confirmMessage) {
        if (window.confirm(message)) onConfirm();
        return;
    }
    confirmMessage.textContent = message;
    if (confirmAccept && acceptLabel) confirmAccept.textContent = acceptLabel;
    pendingConfirmation = onConfirm;
    confirmModal.hidden = false;
    document.body.classList.add("modal-open");
};

document.addEventListener(
    "submit",
    (event) => {
        const form = event.target.closest("form[data-confirm]");
        if (!form || form.dataset.confirmed === "true") return;
        event.preventDefault();
        event.stopImmediatePropagation();
        openConfirmModal(form.dataset.confirm || "Are you sure you want to continue?", () => {
            form.dataset.confirmed = "true";
            form.submit();
        }, form.dataset.confirmAcceptLabel);
    },
    true
);

if (confirmAccept) {
    confirmAccept.addEventListener("click", () => {
        const action = pendingConfirmation;
        closeConfirmModal();
        if (action) action();
    });
}

if (confirmCancel) {
    confirmCancel.addEventListener("click", closeConfirmModal);
}

document.querySelectorAll("[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
        const button = form.querySelector("button[type='submit']");
        if (button) {
            button.classList.add("is-loading");
            button.disabled = true;
        }
    });
});

const catalogGrid = document.querySelector("[data-catalog-grid]");
const catalogCards = catalogGrid ? Array.from(catalogGrid.querySelectorAll("[data-book-card]")) : [];
const catalogSearch = document.querySelector("[data-catalog-search]");
const catalogSort = document.querySelector("[data-catalog-sort]");
const catalogFilters = Array.from(document.querySelectorAll("[data-filter-field]"));
const catalogEmpty = document.querySelector("[data-catalog-empty]");
const filterButtons = document.querySelectorAll("[data-filter]");
let shortcutCategory = "all";

const normalize = (value) => String(value || "").toLowerCase().trim();

const getFilterValue = (name) => {
    const field = catalogFilters.find((filter) => filter.dataset.filterField === name);
    return field ? normalize(field.value) : "";
};

const sortCards = (cards) => {
    const sort = catalogSort ? catalogSort.value : "az";
    return [...cards].sort((first, second) => {
        const firstTitle = first.dataset.title || "";
        const secondTitle = second.dataset.title || "";
        const firstYear = Number(first.dataset.year || 0);
        const secondYear = Number(second.dataset.year || 0);
        const firstRating = Number(first.dataset.rating || 0);
        const secondRating = Number(second.dataset.rating || 0);
        const firstReviews = Number(first.dataset.reviews || 0);
        const secondReviews = Number(second.dataset.reviews || 0);

        if (sort === "za") return secondTitle.localeCompare(firstTitle);
        if (sort === "newest") return secondYear - firstYear;
        if (sort === "oldest") return firstYear - secondYear;
        if (sort === "rated") return secondRating - firstRating;
        if (sort === "reviewed") return secondReviews - firstReviews;
        return firstTitle.localeCompare(secondTitle);
    });
};

const updateCatalog = () => {
    if (!catalogGrid) return;

    const query = normalize(catalogSearch ? catalogSearch.value : "");
    const selectedCategory = getFilterValue("category");
    const activeCategory = selectedCategory || (shortcutCategory === "all" ? "" : shortcutCategory);
    const selectedAvailability = getFilterValue("availability");
    const selectedYear = getFilterValue("year");
    const selectedLanguage = getFilterValue("language");
    let visibleCount = 0;

    sortCards(catalogCards).forEach((card) => {
        catalogGrid.appendChild(card);
        const searchable = [
            card.dataset.title,
            card.dataset.author,
            card.dataset.category,
            card.dataset.isbn,
            card.dataset.publisher,
        ].join(" ");

        const visible =
            (!query || searchable.includes(query)) &&
            (!activeCategory || normalize(card.dataset.category) === activeCategory || card.dataset.categorySlug === activeCategory) &&
            (!selectedAvailability || normalize(card.dataset.availability) === selectedAvailability) &&
            (!selectedYear || normalize(card.dataset.year) === selectedYear) &&
            (!selectedLanguage || normalize(card.dataset.language) === selectedLanguage);

        card.hidden = !visible;
        if (visible) visibleCount += 1;
    });

    if (catalogEmpty) {
        catalogGrid.appendChild(catalogEmpty);
        catalogEmpty.hidden = visibleCount > 0;
    }
};

filterButtons.forEach((button) => {
    button.addEventListener("click", () => {
        shortcutCategory = button.dataset.filter;
        filterButtons.forEach((item) => item.classList.toggle("active", item === button));
        updateCatalog();
    });
});

[catalogSearch, catalogSort, ...catalogFilters].forEach((control) => {
    if (!control) return;
    control.addEventListener("input", updateCatalog);
    control.addEventListener("change", updateCatalog);
});

updateCatalog();

const usernameInput = document.querySelector("[data-username-check]");
const usernameMessage = document.querySelector("[data-username-message]");

if (usernameInput && usernameMessage) {
    let usernameTimer = null;
    usernameInput.addEventListener("input", () => {
        clearTimeout(usernameTimer);
        const username = usernameInput.value.trim();
        usernameInput.setCustomValidity("");
        usernameMessage.textContent = "";
        usernameMessage.classList.remove("is-error", "is-success");
        if (!username) return;

        usernameTimer = setTimeout(async () => {
            const url = `${usernameInput.dataset.usernameUrl}?username=${encodeURIComponent(username)}`;
            try {
                const response = await fetch(url);
                const data = await response.json();
                if (!data.available) {
                    usernameInput.setCustomValidity("Username already taken.");
                    usernameMessage.textContent = "Username already taken.";
                    usernameMessage.classList.add("is-error");
                } else {
                    usernameMessage.textContent = "Username available.";
                    usernameMessage.classList.add("is-success");
                }
            } catch (error) {
                usernameMessage.textContent = "";
            }
        }, 250);
    });
}
