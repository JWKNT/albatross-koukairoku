(() => {
  "use strict";

  const MAX_RESULTS = 500;
  const state = {
    index: null,
    chapter: null,
    route: null,
    scope: "chapter",
    query: "",
    mode: "parallel",
    cache: new Map(),
    searchToken: 0,
  };

  const elements = {
    chapterCount: document.querySelector("#chapter-count"),
    lineCount: document.querySelector("#line-count"),
    updatedAt: document.querySelector("#updated-at"),
    parallelMode: document.querySelector("#parallel-mode"),
    englishMode: document.querySelector("#english-mode"),
    routeMapToggle: document.querySelector("#route-map-toggle"),
    routeMap: document.querySelector("#route-map"),
    routeMapFlow: document.querySelector("#route-map-flow"),
    routeTabs: document.querySelector("#route-tabs"),
    chapterPicker: document.querySelector("#chapter-picker"),
    chapterButton: document.querySelector("#chapter-menu-button"),
    chapterValue: document.querySelector("#chapter-menu-value"),
    chapterMenu: document.querySelector("#chapter-menu"),
    chapterMenuOptions: document.querySelector("#chapter-menu-options"),
    previousChapter: document.querySelector("#previous-chapter"),
    nextChapter: document.querySelector("#next-chapter"),
    search: document.querySelector("#script-search"),
    clearSearch: document.querySelector("#clear-search"),
    chapterRoute: document.querySelector("#chapter-route"),
    chapterTitle: document.querySelector("#chapter-title"),
    chapterProgress: document.querySelector("#chapter-progress"),
    chapterTitleArt: document.querySelector("#chapter-title-art"),
    resultStatus: document.querySelector("#result-status"),
    scriptLines: document.querySelector("#script-lines"),
    emptyState: document.querySelector("#empty-state"),
    lineTemplate: document.querySelector("#line-template"),
    endOrderLabel: document.querySelector("#end-order-label"),
    endActions: document.querySelector("#end-actions"),
  };

  const number = new Intl.NumberFormat("en-US");

  function routeMeta(routeId = state.route) {
    return state.index.routes.find((route) => route.id === routeId);
  }

  function chapterMeta(slug = state.chapter) {
    return state.index.chapters.find((chapter) => chapter.slug === slug);
  }

  function cleanText(value) {
    return String(value || "").replace(/<[^>]+>/g, "");
  }

  function queryTerms() {
    return state.query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  }

  function searchableText(line) {
    return [line.id, line.sj, line.se, line.jp, line.en]
      .map(cleanText)
      .join("\n")
      .toLocaleLowerCase();
  }

  function matches(line, terms) {
    if (!terms.length) return true;
    const haystack = searchableText(line);
    return terms.every((term) => haystack.includes(term));
  }

  function appendHighlighted(element, text, terms) {
    const value = cleanText(text);
    if (!terms.length) {
      element.append(document.createTextNode(value));
      return;
    }
    const escaped = [...new Set(terms)]
      .sort((a, b) => b.length - a.length)
      .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const expression = new RegExp(`(${escaped.join("|")})`, "giu");
    let cursor = 0;
    for (const match of value.matchAll(expression)) {
      element.append(document.createTextNode(value.slice(cursor, match.index)));
      const mark = document.createElement("mark");
      mark.textContent = match[0];
      element.append(mark);
      cursor = match.index + match[0].length;
    }
    element.append(document.createTextNode(value.slice(cursor)));
  }

  async function fetchJson(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Could not load ${path}`);
    return response.json();
  }

  function loadChapter(slug) {
    if (!state.cache.has(slug)) {
      state.cache.set(
        slug,
        fetchJson(`data/chapters/${encodeURIComponent(slug)}.json?v=${encodeURIComponent(state.index.generatedAt)}`),
      );
    }
    return state.cache.get(slug);
  }

  function updateUrl() {
    const url = new URL(window.location.href);
    url.searchParams.set("chapter", state.chapter);
    if (state.query) url.searchParams.set("q", state.query);
    else url.searchParams.delete("q");
    if (state.scope !== "chapter") url.searchParams.set("scope", state.scope);
    else url.searchParams.delete("scope");
    if (state.mode === "english") url.searchParams.set("mode", "en");
    else url.searchParams.delete("mode");
    history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }

  function updateReadingMode() {
    document.body.classList.toggle("english-reader-mode", state.mode === "english");
    elements.parallelMode.setAttribute("aria-pressed", String(state.mode === "parallel"));
    elements.englishMode.setAttribute("aria-pressed", String(state.mode === "english"));
    localStorage.setItem("albatross-reader-mode", state.mode);
  }

  function routeSequence(route = routeMeta()) {
    if (!route.fork) return route.chapters;
    const endingSlugs = new Set(route.fork.choices.map((choice) => choice.chapter));
    return route.chapters.filter((slug) => !endingSlugs.has(slug));
  }

  function adjacentChapters() {
    const route = routeMeta();
    const ending = route.fork?.choices.find((choice) => choice.chapter === state.chapter);
    if (ending) return { previous: route.fork.at, next: null };
    const sequence = routeSequence(route);
    const position = sequence.indexOf(state.chapter);
    return {
      previous: position > 0 ? sequence[position - 1] : null,
      next: position >= 0 && position < sequence.length - 1 ? sequence[position + 1] : null,
    };
  }

  function selectChapter(slug, { scroll = true } = {}) {
    const meta = chapterMeta(slug);
    if (!meta) return;
    state.chapter = slug;
    state.route = meta.route;
    closeChapterMenu();
    renderRouteNavigation();
    updateChapterControls();
    updateUrl();
    renderCurrentChapter();
    if (scroll) document.querySelector("#reader-controls").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function makeNavButton(label, slug, className = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", () => selectChapter(slug));
    return button;
  }

  function updateEndNavigation() {
    const route = routeMeta();
    const adjacent = adjacentChapters();
    elements.endActions.replaceChildren();

    if (route.fork?.at === state.chapter) {
      elements.endOrderLabel.textContent = "Choose an ending";
      for (const choice of route.fork.choices) {
        elements.endActions.append(makeNavButton(`${choice.label} →`, choice.chapter, "branch-action"));
      }
      return;
    }

    if (adjacent.next) {
      elements.endOrderLabel.textContent = `Continue ${route.label}`;
      elements.endActions.append(makeNavButton(`Next: ${chapterMeta(adjacent.next).title} →`, adjacent.next));
      return;
    }

    if (state.chapter === "1021") {
      elements.endOrderLabel.textContent = "Choose a character voyage";
      for (const routeId of ["kuro", "twins", "rui"]) {
        const nextRoute = routeMeta(routeId);
        elements.endActions.append(makeNavButton(`${nextRoute.shortLabel} →`, nextRoute.chapters[0], "branch-action"));
      }
      return;
    }

    if (["kuro", "twins", "rui"].includes(route.id)) {
      elements.endOrderLabel.textContent = "Parallel voyage complete";
      const finalRoute = routeMeta("final");
      elements.endActions.append(makeNavButton("Continue to the Final Voyage →", finalRoute.chapters[0]));
      return;
    }

    elements.endOrderLabel.textContent = "End of the available translation";
  }

  function updateChapterControls() {
    const meta = chapterMeta();
    const route = routeMeta();
    const adjacent = adjacentChapters();
    elements.chapterValue.textContent = `${meta.title} · ${number.format(meta.lineCount)} lines`;
    elements.previousChapter.disabled = !adjacent.previous;
    elements.nextChapter.disabled = !adjacent.next;
    elements.previousChapter.setAttribute(
      "aria-label",
      adjacent.previous ? `Previous: ${chapterMeta(adjacent.previous).title}` : "No previous chapter in this voyage",
    );
    elements.nextChapter.setAttribute(
      "aria-label",
      adjacent.next ? `Next: ${chapterMeta(adjacent.next).title}` : "Use the route choices below",
    );
    elements.chapterMenuOptions.querySelectorAll(".chapter-menu-option").forEach((option) => {
      option.setAttribute("aria-selected", String(option.dataset.slug === state.chapter));
    });
    elements.routeTabs.querySelectorAll("button").forEach((button) => {
      button.setAttribute("aria-current", button.dataset.route === route.id ? "page" : "false");
    });
    elements.routeMapFlow.querySelectorAll("button").forEach((button) => {
      button.setAttribute("aria-current", button.dataset.route === route.id ? "step" : "false");
    });
    updateEndNavigation();
  }

  function closeChapterMenu({ restoreFocus = false } = {}) {
    elements.chapterMenu.hidden = true;
    elements.chapterButton.setAttribute("aria-expanded", "false");
    if (restoreFocus) elements.chapterButton.focus();
  }

  function openChapterMenu() {
    elements.chapterMenu.hidden = false;
    elements.chapterButton.setAttribute("aria-expanded", "true");
    const selected = elements.chapterMenuOptions.querySelector('[aria-selected="true"]');
    selected?.scrollIntoView({ block: "nearest" });
    selected?.focus();
  }

  function buildChapterMenu() {
    const fragment = document.createDocumentFragment();
    for (const route of state.index.routes) {
      const group = document.createElement("section");
      group.className = "chapter-menu-group";
      const heading = document.createElement("div");
      heading.className = "chapter-menu-group-heading";
      const title = document.createElement("strong");
      title.textContent = route.label;
      const count = document.createElement("span");
      count.textContent = `${route.chapters.length} chapters`;
      heading.append(title, count);
      group.append(heading);

      for (const slug of route.chapters) {
        const meta = chapterMeta(slug);
        const option = document.createElement("button");
        option.type = "button";
        option.className = "chapter-menu-option";
        option.dataset.slug = slug;
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        const chapterNumber = document.createElement("span");
        chapterNumber.className = "chapter-option-number";
        chapterNumber.textContent = slug;
        const chapterLabel = document.createElement("span");
        chapterLabel.textContent = meta.title;
        const lineCount = document.createElement("span");
        lineCount.className = "chapter-option-lines";
        lineCount.textContent = number.format(meta.lineCount);
        option.append(chapterNumber, chapterLabel, lineCount);
        option.addEventListener("click", () => selectChapter(slug));
        group.append(option);
      }
      fragment.append(group);
    }
    elements.chapterMenuOptions.append(fragment);
  }

  function renderRouteNavigation() {
    elements.routeTabs.replaceChildren();
    for (const route of state.index.routes) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.route = route.id;
      button.innerHTML = `<span>${route.shortLabel}</span><small>${route.chapters.length} ch.</small>`;
      button.addEventListener("click", () => {
        const target = state.route === route.id ? state.chapter : route.chapters[0];
        selectChapter(target);
      });
      elements.routeTabs.append(button);
    }
    updateChapterControls();
  }

  function buildRouteMap() {
    const common = routeMeta("common");
    const final = routeMeta("final");
    const commonButton = makeNavButton(`${common.label}\n${common.chapters.length} chapters`, common.chapters[0], "route-node route-node-common");
    commonButton.dataset.route = common.id;
    const branches = document.createElement("div");
    branches.className = "route-branches";
    for (const id of ["kuro", "twins", "rui"]) {
      const route = routeMeta(id);
      const button = makeNavButton(`${route.label}\n${route.chapters.length} chapters · 2 endings`, route.chapters[0], "route-node route-node-branch");
      button.dataset.route = route.id;
      branches.append(button);
    }
    const finalButton = makeNavButton(`${final.label}\n${final.chapters.length} chapters`, final.chapters[0], "route-node route-node-final");
    finalButton.dataset.route = final.id;
    const arrow1 = document.createElement("span");
    arrow1.className = "route-arrow";
    arrow1.textContent = "→";
    const arrow2 = arrow1.cloneNode(true);
    elements.routeMapFlow.append(commonButton, arrow1, branches, arrow2, finalButton);
  }

  function makeLineArticle(line, meta, terms, includeChapter) {
    const article = elements.lineTemplate.content.firstElementChild.cloneNode(true);
    const anchorId = `line-${line.id.replace(":", "-")}`;
    article.id = anchorId;
    article.dataset.chapter = meta.slug;
    article.classList.toggle("choice-line", line.t === "choice");

    const lineNumber = article.querySelector(".line-number");
    lineNumber.href = `?chapter=${encodeURIComponent(meta.slug)}#${anchorId}`;
    lineNumber.textContent = includeChapter ? `${meta.slug} · ${line.i}` : String(line.i);
    lineNumber.setAttribute("aria-label", `Link to ${line.id}`);

    const japanese = article.querySelector(".japanese");
    appendHighlighted(japanese.querySelector(".speaker"), line.sj, terms);
    appendHighlighted(japanese.querySelector(".line-text"), line.jp, terms);

    const english = article.querySelector(".english");
    appendHighlighted(english.querySelector(".speaker"), line.se, terms);
    appendHighlighted(english.querySelector(".line-text"), line.en, terms);
    article.classList.toggle("has-speaker", Boolean(line.se));
    return article;
  }

  async function renderCurrentChapter() {
    const token = ++state.searchToken;
    const meta = chapterMeta();
    const route = routeMeta();
    const routePosition = route.chapters.indexOf(state.chapter) + 1;
    elements.resultStatus.hidden = false;
    elements.resultStatus.textContent = "Loading script…";
    elements.chapterRoute.textContent = route.label;
    elements.chapterTitle.textContent = meta.title;
    elements.chapterProgress.textContent = `Chapter ${routePosition} of ${route.chapters.length} · ${number.format(meta.lineCount)} translated lines`;
    elements.chapterTitleArt.hidden = false;
    elements.chapterTitleArt.src = meta.titleArt;
    elements.chapterTitleArt.onerror = () => { elements.chapterTitleArt.hidden = true; };

    const terms = queryTerms();
    let chapterSlugs;
    if (!terms.length || state.scope === "chapter") chapterSlugs = [state.chapter];
    else if (state.scope === "route") chapterSlugs = route.chapters;
    else chapterSlugs = state.index.chapters.map((chapter) => chapter.slug);

    try {
      const chapters = await Promise.all(chapterSlugs.map(loadChapter));
      if (token !== state.searchToken) return;
      const results = [];
      let totalMatches = 0;
      for (const chapter of chapters) {
        const chapterInfo = chapterMeta(chapter.slug);
        for (const line of chapter.lines) {
          if (!matches(line, terms)) continue;
          totalMatches += 1;
          if (results.length < MAX_RESULTS) results.push(makeLineArticle(line, chapterInfo, terms, chapterSlugs.length > 1));
        }
      }
      elements.scriptLines.replaceChildren(...results);
      elements.emptyState.hidden = results.length > 0;
      const searching = terms.length > 0;
      elements.resultStatus.hidden = !searching;
      if (searching) {
        const capped = totalMatches > MAX_RESULTS ? `Showing first ${number.format(MAX_RESULTS)} of ${number.format(totalMatches)}` : `${number.format(totalMatches)} ${totalMatches === 1 ? "match" : "matches"}`;
        elements.resultStatus.textContent = capped;
      }
      updateChapterControls();
      const hashTarget = window.location.hash && document.querySelector(window.location.hash);
      hashTarget?.scrollIntoView({ block: "center" });
    } catch (error) {
      elements.scriptLines.replaceChildren();
      elements.emptyState.hidden = false;
      elements.emptyState.querySelector("h2").textContent = "The script could not be loaded";
      elements.emptyState.querySelector("p").textContent = "Refresh the page to try again.";
      elements.resultStatus.hidden = true;
      console.error(error);
    }
  }

  function updateSearchPlaceholder() {
    const labels = { chapter: "Search this chapter", route: "Search this route", all: "Search all routes" };
    elements.search.placeholder = labels[state.scope];
  }

  function bindEvents() {
    elements.parallelMode.addEventListener("click", () => {
      state.mode = "parallel";
      updateReadingMode();
      updateUrl();
    });
    elements.englishMode.addEventListener("click", () => {
      state.mode = "english";
      updateReadingMode();
      updateUrl();
    });
    elements.routeMapToggle.addEventListener("click", () => {
      const open = elements.routeMap.hidden;
      elements.routeMap.hidden = !open;
      elements.routeMapToggle.setAttribute("aria-expanded", String(open));
    });
    elements.chapterButton.addEventListener("click", () => {
      if (elements.chapterMenu.hidden) openChapterMenu();
      else closeChapterMenu({ restoreFocus: true });
    });
    elements.previousChapter.addEventListener("click", () => {
      const slug = adjacentChapters().previous;
      if (slug) selectChapter(slug);
    });
    elements.nextChapter.addEventListener("click", () => {
      const slug = adjacentChapters().next;
      if (slug) selectChapter(slug);
    });
    document.querySelectorAll('input[name="search-scope"]').forEach((radio) => {
      radio.addEventListener("change", (event) => {
        state.scope = event.target.value;
        updateSearchPlaceholder();
        updateUrl();
        renderCurrentChapter();
      });
    });
    let searchTimer;
    elements.search.addEventListener("input", () => {
      state.query = elements.search.value;
      elements.clearSearch.hidden = !state.query;
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        updateUrl();
        renderCurrentChapter();
      }, 180);
    });
    elements.clearSearch.addEventListener("click", () => {
      state.query = "";
      elements.search.value = "";
      elements.clearSearch.hidden = true;
      updateUrl();
      renderCurrentChapter();
      elements.search.focus();
    });
    document.addEventListener("click", (event) => {
      if (!elements.chapterPicker.contains(event.target)) closeChapterMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !elements.chapterMenu.hidden) closeChapterMenu({ restoreFocus: true });
    });
  }

  async function initialize() {
    try {
      state.index = await fetchJson("data/index.json");
      const params = new URLSearchParams(window.location.search);
      const requested = params.get("chapter");
      state.chapter = chapterMeta(requested) ? requested : state.index.chapters[0].slug;
      state.route = chapterMeta().route;
      state.query = params.get("q") || "";
      state.scope = ["chapter", "route", "all"].includes(params.get("scope")) ? params.get("scope") : "chapter";
      const savedMode = localStorage.getItem("albatross-reader-mode");
      state.mode = params.get("mode") === "en" || (!params.has("mode") && savedMode === "english") ? "english" : "parallel";

      elements.chapterCount.textContent = number.format(state.index.chapterCount);
      elements.lineCount.textContent = number.format(state.index.lineCount);
      elements.updatedAt.textContent = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(state.index.generatedAt));
      elements.search.value = state.query;
      elements.clearSearch.hidden = !state.query;
      const scopeRadio = document.querySelector(`input[name="search-scope"][value="${state.scope}"]`);
      scopeRadio.checked = true;

      buildChapterMenu();
      buildRouteMap();
      renderRouteNavigation();
      updateSearchPlaceholder();
      updateReadingMode();
      bindEvents();
      updateUrl();
      await renderCurrentChapter();
    } catch (error) {
      elements.chapterTitle.textContent = "Reader unavailable";
      elements.chapterProgress.textContent = "The translation index could not be loaded.";
      elements.resultStatus.hidden = true;
      console.error(error);
    }
  }

  initialize();
})();
