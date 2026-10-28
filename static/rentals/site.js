(() => {
  /* ---------------- Mobile navigation ---------------- */
  const menuButton = document.querySelector("[data-menu-toggle]");
  const navigation = document.querySelector("#main-navigation");

  if (menuButton && navigation) {
    const openIcon = menuButton.querySelector("[data-menu-open-icon]");
    const closeIcon = menuButton.querySelector("[data-menu-close-icon]");

    const setMenuOpen = (isOpen) => {
      navigation.classList.toggle("hidden", !isOpen);
      menuButton.setAttribute("aria-expanded", String(isOpen));
      menuButton.setAttribute(
        "aria-label",
        isOpen ? "Close navigation menu" : "Open navigation menu",
      );
      openIcon?.classList.toggle("hidden", isOpen);
      closeIcon?.classList.toggle("hidden", !isOpen);
    };

    menuButton.addEventListener("click", () => {
      setMenuOpen(menuButton.getAttribute("aria-expanded") !== "true");
    });
    navigation.addEventListener("click", (event) => {
      if (event.target.closest("a, button")) setMenuOpen(false);
    });
    window
      .matchMedia("(min-width: 640px)")
      .addEventListener("change", (event) => {
        if (event.matches) setMenuOpen(false);
      });
    document.addEventListener("click", (event) => {
      if (
        menuButton.getAttribute("aria-expanded") === "true" &&
        !navigation.contains(event.target) &&
        !menuButton.contains(event.target)
      ) {
        setMenuOpen(false);
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setMenuOpen(false);
    });
  }

  /* ---------------- Password visibility toggle ---------------- */
  document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
    const input = document.querySelector(btn.dataset.target);
    if (!input) return;
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Hide" : "Show";
      btn.setAttribute("aria-pressed", String(show));
    });
  });

  /* ---------------- Upload preview ---------------- */
  document.querySelectorAll("[data-upload-preview]").forEach((preview) => {
    const input = document.getElementById(preview.dataset.uploadPreview);
    if (!input) return;

    let currentUrls = [];
    const renderPreview = () => {
      currentUrls.forEach((url) => URL.revokeObjectURL(url));
      currentUrls = [];
      preview.replaceChildren();

      const files = Array.from(input.files || []);
      const max = input.multiple ? 8 : 1;
      files.slice(0, max).forEach((file, index) => {
        if (!file.type.startsWith("image/")) return;
        const url = URL.createObjectURL(file);
        currentUrls.push(url);

        const figure = document.createElement("div");
        figure.className =
          "relative overflow-hidden rounded-lg border border-stone-200 bg-white";

        const image = document.createElement("img");
        image.className = "h-28 w-full object-cover";
        image.src = url;
        image.alt = `Preview of ${file.name}`;
        image.loading = "lazy";

        const caption = document.createElement("p");
        caption.className =
          "truncate px-2 py-1.5 pr-9 text-xs text-muted";
        caption.textContent = file.name;

        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className =
          "absolute right-1 top-1 flex h-8 w-8 items-center justify-center rounded-full bg-slate-950/80 text-lg text-white shadow hover:bg-rose-700";
        removeButton.setAttribute("aria-label", `Remove ${file.name}`);
        removeButton.textContent = "×";
        removeButton.addEventListener("click", () => {
          const transfer = new DataTransfer();
          files.forEach((selected, selectedIndex) => {
            if (selectedIndex !== index) transfer.items.add(selected);
          });
          input.files = transfer.files;
          renderPreview();
        });

        figure.append(image, caption, removeButton);
        preview.append(figure);
      });

      if (files.length) {
        const count = document.createElement("p");
        count.className = "col-span-full text-xs text-muted";
        count.textContent = `${files.length} photo${
          files.length === 1 ? "" : "s"
        } selected${files.length > max ? ` (only first ${max} kept)` : ""}`;
        preview.append(count);
      }
    };

    input.addEventListener("change", renderPreview);
    window.addEventListener("pagehide", () => {
      currentUrls.forEach((url) => URL.revokeObjectURL(url));
    });
  });

  /* ---------------- Photo lightbox ---------------- */
  const gallery = Array.from(
    document.querySelectorAll("[data-gallery-image]"),
  ).map((button) => ({
    src: button.dataset.gallerySrc,
    caption: button.dataset.galleryCaption || "",
  }));
  const dialog = document.querySelector("#photo-lightbox");

  if (dialog && gallery.length) {
    const image = dialog.querySelector("[data-lightbox-image]");
    const caption = dialog.querySelector("[data-lightbox-caption]");
    const counter = dialog.querySelector("[data-lightbox-counter]");
    const previousBtn = dialog.querySelector("[data-lightbox-previous]");
    const nextBtn = dialog.querySelector("[data-lightbox-next]");
    const closeBtn = dialog.querySelector("[data-lightbox-close]");
    const focusables = [closeBtn, previousBtn, nextBtn].filter(Boolean);

    let currentIndex = 0;
    let pointerStartX = null;
    let lastFocused = null;

    const showImage = (index) => {
      currentIndex = (index + gallery.length) % gallery.length;
      image.src = gallery[currentIndex].src;
      image.alt = gallery[currentIndex].caption;
      caption.textContent = gallery[currentIndex].caption;
      counter.textContent = `${currentIndex + 1} / ${gallery.length}`;
    };

    document
      .querySelectorAll("[data-gallery-image]")
      .forEach((button, index) => {
        button.addEventListener("click", () => {
          lastFocused = document.activeElement;
          showImage(index);
          dialog.showModal();
          closeBtn?.focus();
        });
      });

    closeBtn?.addEventListener("click", () => dialog.close());
    previousBtn?.addEventListener("click", () => showImage(currentIndex - 1));
    nextBtn?.addEventListener("click", () => showImage(currentIndex + 1));

    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });

    dialog.addEventListener("pointerdown", (event) => {
      pointerStartX = event.clientX;
    });
    dialog.addEventListener("pointerup", (event) => {
      if (pointerStartX === null) return;
      const distance = event.clientX - pointerStartX;
      pointerStartX = null;
      if (Math.abs(distance) < 55) return;
      showImage(currentIndex + (distance < 0 ? 1 : -1));
    });

    dialog.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight") showImage(currentIndex + 1);
      if (event.key === "ArrowLeft") showImage(currentIndex - 1);
      // Focus trap
      if (event.key === "Tab" && focusables.length) {
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });

    dialog.addEventListener("close", () => {
      lastFocused?.focus?.();
    });
  }

  /* ---------------- Confirm destructive actions ---------------- */
  document.addEventListener("submit", (event) => {
    const msg = event.target.dataset.confirm;
    if (msg && !window.confirm(msg)) {
      event.preventDefault();
    }
  });

  /* ---------------- Auto-submit filter forms on change ---------------- */
  document.querySelectorAll("[data-autosubmit]").forEach((el) => {
    el.addEventListener("change", () => el.form?.requestSubmit());
  });

  /* ---------------- Description character counter ---------------- */
  document.querySelectorAll("[data-char-counter]").forEach((input) => {
    const target = document.getElementById(input.dataset.charCounter);
    if (!target) return;
    const update = () => {
      target.textContent = `${input.value.length} characters`;
    };
    input.addEventListener("input", update);
    update();
  });
})();