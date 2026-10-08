(() => {
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
    window.matchMedia("(min-width: 640px)").addEventListener("change", (event) => {
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

  document.querySelectorAll("[data-upload-preview]").forEach((preview) => {
    const input = document.getElementById(preview.dataset.uploadPreview);
    if (!input) return;

    let currentUrls = [];
    const renderPreview = () => {
      currentUrls.forEach((url) => URL.revokeObjectURL(url));
      currentUrls = [];
      preview.replaceChildren();

      const files = Array.from(input.files || []);
      files.slice(0, input.multiple ? 8 : 1).forEach((file, index) => {
        if (!file.type.startsWith("image/")) return;
        const url = URL.createObjectURL(file);
        currentUrls.push(url);

        const figure = document.createElement("div");
        figure.className = "relative overflow-hidden rounded-lg border border-stone-200 bg-white";

        const image = document.createElement("img");
        image.className = "h-28 w-full object-cover";
        image.src = url;
        image.alt = `Preview of ${file.name}`;

        const caption = document.createElement("p");
        caption.className = "truncate px-2 py-1.5 pr-9 text-xs text-muted";
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
        count.textContent = `${files.length} photo${files.length === 1 ? "" : "s"} selected`;
        preview.append(count);
      }
    };

    input.addEventListener("change", renderPreview);
    window.addEventListener("pagehide", () => {
      currentUrls.forEach((url) => URL.revokeObjectURL(url));
    });
  });

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
    let currentIndex = 0;
    let pointerStartX = null;

    const showImage = (index) => {
      currentIndex = (index + gallery.length) % gallery.length;
      image.src = gallery[currentIndex].src;
      image.alt = gallery[currentIndex].caption;
      caption.textContent = gallery[currentIndex].caption;
      counter.textContent = `${currentIndex + 1} / ${gallery.length}`;
    };

    document.querySelectorAll("[data-gallery-image]").forEach((button, index) => {
      button.addEventListener("click", () => {
        showImage(index);
        dialog.showModal();
      });
    });

    dialog.querySelector("[data-lightbox-close]")?.addEventListener("click", () => {
      dialog.close();
    });
    dialog.querySelector("[data-lightbox-previous]")?.addEventListener("click", () => {
      showImage(currentIndex - 1);
    });
    dialog.querySelector("[data-lightbox-next]")?.addEventListener("click", () => {
      showImage(currentIndex + 1);
    });
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
    });
  }
})();
