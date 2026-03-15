(function () {
    "use strict";

    const PADDING = { top: 20, right: 20, bottom: 50, left: 60 };
    const DOT_RADIUS = 2.5;
    const HIGHLIGHT_RADIUS = 4;
    const SELECTED_RADIUS = 6;
    const HOVER_RADIUS = 8;

    const SELECTED_COLORS = [
        "#dc3220", "#e87d1e", "#7b2d8b", "#1a9850",
        "#d4a017", "#2166ac", "#b2182b", "#35978f",
    ];

    // TABLE_COLUMNS is set via a <script> tag in the HTML

    var visibleColumns = new Set();
    TABLE_COLUMNS.forEach(function (col) {
        if (col.defaultOn) visibleColumns.add(col.key);
    });

    var tableSortKey = null;  // null means sort by xField
    var tableSortAsc = false;
    var tableSelectedOnly = false;

    var rankCache = {};

    let allSchools = [];
    let filteredSchools = [];
    let selectedUrns = new Set();
    let canvas, ctx, tooltip;
    let searchInput, searchResults, selectedContainer;
    let width, height, plotW, plotH;
    let viewMode = "scatter";  // "scatter" or "hist"
    let histField = DEFAULTS.hist;
    let xField, yField;
    let xMin, xMax, yMin, yMax;
    let rankedSchools = [];  // sorted schools for rank plot
    let hoveredSchool = null;
    let dpr = window.devicePixelRatio || 1;
    let activeResultIndex = -1;

    function init() {
        canvas = document.getElementById("scatterplot");
        ctx = canvas.getContext("2d");
        tooltip = document.getElementById("tooltip");
        searchInput = document.getElementById("search-input");
        searchResults = document.getElementById("search-results");
        selectedContainer = document.getElementById("selected-schools");

        restoreStateFromURL();

        document.getElementById("x-axis").addEventListener("change", onControlChange);
        document.getElementById("y-axis").addEventListener("change", onControlChange);
        document.getElementById("hist-var").addEventListener("change", onControlChange);
        document.getElementById("view-scatter").addEventListener("click", function () { setViewMode("scatter"); });
        document.getElementById("view-hist").addEventListener("click", function () { setViewMode("hist"); });
        document.getElementById("add-filter").addEventListener("click", function () {
            addFilterRow("", "", "");
        });

        searchInput.addEventListener("input", onSearchInput);
        searchInput.addEventListener("keydown", onSearchKeydown);
        document.addEventListener("click", function (e) {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                hideSearchResults();
            }
        });

        var helpModal = document.getElementById("help-modal");
        document.getElementById("help-btn").addEventListener("click", function () {
            helpModal.classList.add("visible");
        });
        document.getElementById("help-close").addEventListener("click", function () {
            helpModal.classList.remove("visible");
        });
        helpModal.addEventListener("click", function (e) {
            if (e.target === helpModal) helpModal.classList.remove("visible");
        });

        canvas.addEventListener("mousemove", onMouseMove);
        canvas.addEventListener("click", onCanvasClick);
        canvas.addEventListener("mouseleave", onMouseLeave);
        window.addEventListener("resize", onResize);
        window.addEventListener("popstate", function () {
            restoreStateFromURL();
            onDataReady();
        });

        fetchData();
    }

    function setViewMode(mode) {
        viewMode = mode;
        document.getElementById("view-scatter").classList.toggle("active", mode === "scatter");
        document.getElementById("view-hist").classList.toggle("active", mode === "hist");
        document.getElementById("scatter-controls").style.display = mode === "scatter" ? "" : "none";
        document.getElementById("hist-controls").style.display = mode === "hist" ? "" : "none";
        onControlChange();
    }

    // --- URL state ---

    function restoreStateFromURL() {
        var params = new URLSearchParams(window.location.search);
        if (params.has("view") && params.get("view") === "rank") {
            viewMode = "hist";
            document.getElementById("view-hist").classList.add("active");
            document.getElementById("view-scatter").classList.remove("active");
            document.getElementById("scatter-controls").style.display = "none";
            document.getElementById("hist-controls").style.display = "";
        }
        if (params.has("x")) setSelectValue("x-axis", params.get("x"));
        if (params.has("y")) setSelectValue("y-axis", params.get("y"));
        if (params.has("var")) setSelectValue("hist-var", params.get("var"));
        if (params.has("f")) {
            params.get("f").split(",").forEach(function (pair) {
                var sep = pair.indexOf(":");
                if (sep > 0) addFilterRow(pair.slice(0, sep), pair.slice(sep + 1));
            });
        }
        // Legacy params
        if (params.has("la")) addFilterRow("la", params.get("la"));
        if (params.has("type")) addFilterRow("type", params.get("type"));
        if (params.has("religion")) addFilterRow("religion", params.get("religion"));

        if (params.has("cols")) {
            visibleColumns = new Set(params.get("cols").split(","));
        }
        if (params.has("sort")) {
            var sortVal = params.get("sort");
            if (sortVal.charAt(0) === "-") {
                tableSortKey = sortVal.slice(1);
                tableSortAsc = false;
            } else {
                tableSortKey = sortVal;
                tableSortAsc = true;
            }
        }

        selectedUrns = new Set();
        if (params.has("schools")) {
            var urns = params.get("schools").split(",");
            for (var i = 0; i < urns.length; i++) {
                var urn = parseInt(urns[i], 10);
                if (!isNaN(urn)) selectedUrns.add(urn);
            }
        }
    }

    function setSelectValue(id, value) {
        var el = document.getElementById(id);
        var options = el.options;
        for (var i = 0; i < options.length; i++) {
            if (options[i].value === value) {
                el.value = value;
                return;
            }
        }
    }

    function pushStateToURL() {
        var params = new URLSearchParams();
        var x = document.getElementById("x-axis").value;
        var y = document.getElementById("y-axis").value;
        var hv = document.getElementById("hist-var").value;

        var filters = getFilters();

        if (viewMode === "hist") params.set("view", "rank");
        if (x !== DEFAULTS.x) params.set("x", x);
        if (y !== DEFAULTS.y) params.set("y", y);
        if (hv !== DEFAULTS.hist) params.set("var", hv);

        if (filters.length > 0) {
            params.set("f", filters.map(function (f) {
                return f.key + ":" + f.value;
            }).join(","));
        }
        if (selectedUrns.size > 0) {
            params.set("schools", Array.from(selectedUrns).join(","));
        }

        if (tableSortKey) {
            params.set("sort", (tableSortAsc ? "" : "-") + tableSortKey);
        }

        // Only include cols param if non-default
        var defaultCols = new Set();
        TABLE_COLUMNS.forEach(function (c) { if (c.defaultOn) defaultCols.add(c.key); });
        var isDefault = visibleColumns.size === defaultCols.size &&
            Array.from(visibleColumns).every(function (k) { return defaultCols.has(k); });
        if (!isDefault) {
            params.set("cols", Array.from(visibleColumns).join(","));
        }

        var qs = params.toString();
        var url = window.location.pathname + (qs ? "?" + qs : "");
        history.replaceState(null, "", url);
    }

    // --- Dynamic filters ---

    var OFSTED_GRADE_LABELS = { "1": "1 – Outstanding", "2": "2 – Good", "3": "3 – Requires improvement", "4": "4 – Inadequate" };

    var FILTER_CATEGORIES = [
        { key: "la", label: "Local authority", group: "School info", type: "select", options: FILTER_OPTIONS.la_names, schoolKey: "la_name" },
        { key: "type", label: "School type", group: "School info", type: "select", options: FILTER_OPTIONS.school_types, schoolKey: "school_type" },
        { key: "religion", label: "Religious character", group: "School info", type: "select", options: FILTER_OPTIONS.religious_characters, schoolKey: "religious_character" },
        { key: "trust", label: "Academy trust", group: "School info", type: "select", options: FILTER_OPTIONS.trust_names, schoolKey: "trust_name" },
    ];

    var OFSTED_FILTER_FIELDS = [
        { key: "ofsted", label: "Overall", schoolKey: "ofsted_overall" },
        { key: "ofsted_quality", label: "Quality of education", schoolKey: "ofsted_quality" },
        { key: "ofsted_behaviour", label: "Behaviour & attitudes", schoolKey: "ofsted_behaviour" },
        { key: "ofsted_personal", label: "Personal development", schoolKey: "ofsted_personal" },
        { key: "ofsted_leadership", label: "Leadership & management", schoolKey: "ofsted_leadership" },
        { key: "ofsted_early_years", label: "Early years", schoolKey: "ofsted_early_years" },
        { key: "ofsted_sixth_form", label: "Sixth form", schoolKey: "ofsted_sixth_form" },
    ];
    for (var oi = 0; oi < OFSTED_FILTER_FIELDS.length; oi++) {
        var of_ = OFSTED_FILTER_FIELDS[oi];
        if (FIELD_LABELS[of_.schoolKey]) {
            FILTER_CATEGORIES.push({
                key: of_.key, label: of_.label, group: "Ofsted", type: "select",
                options: FILTER_OPTIONS.ofsted_grades, schoolKey: of_.schoolKey,
                optionLabels: OFSTED_GRADE_LABELS, numeric: true
            });
        }
    }

    var NF_FILTER_FIELDS = [
        { key: "nf_inclusion", label: "Inclusion", schoolKey: "nf_inclusion" },
        { key: "nf_curriculum", label: "Curriculum & teaching", schoolKey: "nf_curriculum" },
        { key: "nf_achievement", label: "Achievement", schoolKey: "nf_achievement" },
        { key: "nf_attendance", label: "Attendance & behaviour", schoolKey: "nf_attendance" },
        { key: "nf_personal", label: "Personal development", schoolKey: "nf_personal" },
        { key: "nf_early_years", label: "Early years", schoolKey: "nf_early_years" },
        { key: "nf_leadership", label: "Leadership & governance", schoolKey: "nf_leadership" },
    ];
    for (var ni = 0; ni < NF_FILTER_FIELDS.length; ni++) {
        var nf = NF_FILTER_FIELDS[ni];
        if (FIELD_LABELS[nf.schoolKey]) {
            FILTER_CATEGORIES.push({
                key: nf.key, label: nf.label, group: "Ofsted (new framework)", type: "select",
                options: FILTER_OPTIONS.nf_judgements, schoolKey: nf.schoolKey
            });
        }
    }

    // Add a percentile entry for each demographic field
    for (var di = 0; di < DEMOGRAPHIC_FIELDS.length; di++) {
        var df = DEMOGRAPHIC_FIELDS[di];
        FILTER_CATEGORIES.push({
            key: df,
            label: FIELD_LABELS[df],
            group: "Demographics",
            type: "percentile",
            schoolKey: df,
        });
    }

    function addFilterRow(categoryKey, value) {
        var container = document.getElementById("filter-rows");
        var row = document.createElement("div");
        row.className = "filter-row";

        // Category select with optgroups
        var catSelect = document.createElement("select");
        catSelect.className = "filter-cat-select";
        catSelect.innerHTML = '<option value="">Choose...</option>';
        var currentGroup = null;
        var currentOptgroup = null;
        for (var i = 0; i < FILTER_CATEGORIES.length; i++) {
            var cat = FILTER_CATEGORIES[i];
            if (cat.group !== currentGroup) {
                currentGroup = cat.group;
                currentOptgroup = document.createElement("optgroup");
                currentOptgroup.label = currentGroup;
                catSelect.appendChild(currentOptgroup);
            }
            var opt = document.createElement("option");
            opt.value = cat.key;
            opt.textContent = cat.label;
            if (cat.key === categoryKey) opt.selected = true;
            currentOptgroup.appendChild(opt);
        }

        var valueContainer = document.createElement("span");
        valueContainer.className = "filter-value-container";

        function buildValueControl() {
            valueContainer.innerHTML = "";
            var selectedCat = catSelect.value;
            var catDef = FILTER_CATEGORIES.find(function (c) { return c.key === selectedCat; });
            if (!catDef) return;

            if (catDef.type === "select") {
                var valSelect = document.createElement("select");
                valSelect.innerHTML = '<option value="">All</option>';
                for (var j = 0; j < catDef.options.length; j++) {
                    var o = document.createElement("option");
                    o.value = catDef.options[j];
                    o.textContent = catDef.optionLabels ? catDef.optionLabels[catDef.options[j]] || catDef.options[j] : catDef.options[j];
                    if (catDef.options[j] === value) o.selected = true;
                    valSelect.appendChild(o);
                }
                valSelect.addEventListener("change", onControlChange);
                valueContainer.appendChild(valSelect);
            } else if (catDef.type === "percentile") {
                var parts = value ? String(value).split("-") : [];
                var minVal = parts[0] || "0";
                var maxVal = parts[1] || "100";

                var wrapper = document.createElement("div");
                wrapper.className = "dual-slider";

                var track = document.createElement("div");
                track.className = "dual-slider-track";
                var range = document.createElement("div");
                range.className = "dual-slider-range";
                track.appendChild(range);

                var sliderMin = document.createElement("input");
                sliderMin.type = "range";
                sliderMin.min = "0";
                sliderMin.max = "100";
                sliderMin.value = minVal;

                var sliderMax = document.createElement("input");
                sliderMax.type = "range";
                sliderMax.min = "0";
                sliderMax.max = "100";
                sliderMax.value = maxVal;

                var label = document.createElement("span");
                label.className = "pct-slider-label";

                function updateDualSlider() {
                    var lo = parseInt(sliderMin.value, 10);
                    var hi = parseInt(sliderMax.value, 10);
                    if (lo > hi) {
                        // Swap if dragged past each other
                        var tmp = lo; lo = hi; hi = tmp;
                        sliderMin.value = lo;
                        sliderMax.value = hi;
                    }
                    range.style.left = lo + "%";
                    range.style.width = (hi - lo) + "%";
                    label.textContent = "p" + lo + "\u2013" + "p" + hi;
                }

                sliderMin.addEventListener("input", function () { updateDualSlider(); onControlChange(); });
                sliderMax.addEventListener("input", function () { updateDualSlider(); onControlChange(); });

                wrapper.appendChild(track);
                wrapper.appendChild(sliderMin);
                wrapper.appendChild(sliderMax);
                valueContainer.appendChild(wrapper);
                valueContainer.appendChild(label);
                updateDualSlider();
            }
        }

        catSelect.addEventListener("change", function () {
            buildValueControl();
            onControlChange();
        });

        var removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "filter-remove";
        removeBtn.textContent = "\u00d7";
        removeBtn.addEventListener("click", function () {
            row.remove();
            onControlChange();
        });

        var valueRow = document.createElement("div");
        valueRow.className = "filter-value-row";
        valueRow.appendChild(valueContainer);
        valueRow.appendChild(removeBtn);

        row.appendChild(catSelect);
        row.appendChild(valueRow);
        container.appendChild(row);

        if (categoryKey) buildValueControl();
    }

    function getFilters() {
        var rows = document.querySelectorAll(".filter-row");
        var filters = [];
        for (var i = 0; i < rows.length; i++) {
            var catKey = rows[i].querySelector(".filter-cat-select").value;
            var catDef = FILTER_CATEGORIES.find(function (c) { return c.key === catKey; });
            if (!catDef) continue;

            if (catDef.type === "select") {
                var selects = rows[i].querySelectorAll(".filter-value-container select");
                var val = selects.length ? selects[0].value : "";
                if (val) filters.push({ type: "match", key: catDef.key, schoolKey: catDef.schoolKey, value: val, numeric: !!catDef.numeric });
            } else if (catDef.type === "percentile") {
                var sliders = rows[i].querySelectorAll(".dual-slider input");
                if (sliders.length === 2) {
                    var lo = parseInt(sliders[0].value, 10);
                    var hi = parseInt(sliders[1].value, 10);
                    if (lo > hi) { var tmp = lo; lo = hi; hi = tmp; }
                    if (lo > 0 || hi < 100) {
                        filters.push({ type: "percentile", key: catDef.key, schoolKey: catDef.schoolKey, min: lo, max: hi, value: lo + "-" + hi });
                    }
                }
            }
        }
        return filters;
    }

    // --- Search and selection ---

    function onSearchInput() {
        const query = searchInput.value.trim().toLowerCase();
        if (query.length < 2) {
            hideSearchResults();
            return;
        }

        var urnQuery = parseInt(query, 10);
        var isUrnSearch = String(urnQuery) === query;

        var matches = allSchools
            .filter(function (s) {
                if (selectedUrns.has(s.urn)) return false;
                if (isUrnSearch) return s.urn === urnQuery;
                return s.name.toLowerCase().includes(query);
            })
            .sort(function (a, b) {
                if (isUrnSearch) return 0;
                var aStarts = a.name.toLowerCase().startsWith(query) ? 0 : 1;
                var bStarts = b.name.toLowerCase().startsWith(query) ? 0 : 1;
                if (aStarts !== bStarts) return aStarts - bStarts;
                return a.name.localeCompare(b.name);
            })
            .slice(0, 15);

        if (matches.length === 0) {
            hideSearchResults();
            return;
        }

        searchResults.innerHTML = "";
        activeResultIndex = -1;
        for (const s of matches) {
            const li = document.createElement("li");
            li.textContent = s.name + " ";
            const hint = document.createElement("span");
            hint.className = "la-hint";
            hint.textContent = "(" + s.la_name + ")";
            li.appendChild(hint);
            li.addEventListener("click", function () {
                selectSchool(s.urn);
            });
            searchResults.appendChild(li);
        }
        searchResults.classList.add("visible");
    }

    function onSearchKeydown(e) {
        const items = searchResults.querySelectorAll("li");
        if (!items.length) return;

        if (e.key === "ArrowDown") {
            e.preventDefault();
            activeResultIndex = Math.min(activeResultIndex + 1, items.length - 1);
            updateActiveResult(items);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            activeResultIndex = Math.max(activeResultIndex - 1, 0);
            updateActiveResult(items);
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (activeResultIndex >= 0 && activeResultIndex < items.length) {
                items[activeResultIndex].click();
            }
        } else if (e.key === "Escape") {
            hideSearchResults();
        }
    }

    function updateActiveResult(items) {
        for (let i = 0; i < items.length; i++) {
            items[i].classList.toggle("active", i === activeResultIndex);
        }
        if (activeResultIndex >= 0) {
            items[activeResultIndex].scrollIntoView({ block: "nearest" });
        }
    }

    function hideSearchResults() {
        searchResults.classList.remove("visible");
        searchResults.innerHTML = "";
        activeResultIndex = -1;
    }

    function selectSchool(urn) {
        selectedUrns.add(urn);
        searchInput.value = "";
        hideSearchResults();
        renderSelectedChips();
        renderSelectedTable();
        pushStateToURL();
        draw();
    }

    function deselectSchool(urn) {
        selectedUrns.delete(urn);
        renderSelectedChips();
        renderSelectedTable();
        pushStateToURL();
        draw();
    }

    function toggleSchool(urn) {
        if (selectedUrns.has(urn)) {
            deselectSchool(urn);
        } else {
            selectSchool(urn);
        }
    }

    function isInFilteredSet(urn) {
        for (var i = 0; i < filteredSchools.length; i++) {
            if (filteredSchools[i].urn === urn) return true;
        }
        return false;
    }

    function renderSelectedChips() {
        selectedContainer.innerHTML = "";
        let colorIdx = 0;
        for (const urn of selectedUrns) {
            const school = allSchools.find(function (s) { return s.urn === urn; });
            if (!school) continue;
            const chip = document.createElement("span");
            chip.className = "school-chip";
            const color = SELECTED_COLORS[colorIdx % SELECTED_COLORS.length];
            chip.style.borderColor = color;
            chip.style.background = color + "18";

            const dot = document.createElement("span");
            dot.style.color = color;
            dot.textContent = "\u25cf ";
            chip.appendChild(dot);

            chip.appendChild(document.createTextNode(school.name));

            const btn = document.createElement("button");
            btn.textContent = "\u00d7";
            btn.addEventListener("click", function () { deselectSchool(urn); });
            chip.appendChild(btn);

            selectedContainer.appendChild(chip);
            colorIdx++;
        }
    }

    function buildRanks(key) {
        // Always sorts ascending: rank 1 = lowest value, rank N = highest value.
        // Percentiles match: low value = low percentile, high value = high percentile.
        if (rankCache[key]) return rankCache[key];

        var valid = [];
        for (var i = 0; i < allSchools.length; i++) {
            var s = allSchools[i];
            if (s[key] != null) {
                valid.push({ urn: s.urn, val: s[key] });
            }
        }

        valid.sort(function (a, b) { return a.val - b.val; });

        var national = {};
        for (var n = 0; n < valid.length; n++) {
            national[valid[n].urn] = { rank: n + 1, total: valid.length };
        }

        rankCache[key] = national;
        return national;
    }


    function formatRank(rankObj) {
        if (!rankObj) return "\u2013";
        var pctile = Math.round(((rankObj.rank - 1) / (rankObj.total - 1)) * 100);
        return "p" + pctile;
    }

    var columnSelectorOpen = false;

    function renderColumnSelector() {
        var container = document.getElementById("column-selector");
        container.innerHTML = "";

        var header = document.createElement("div");
        header.className = "col-selector-header";

        var toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "col-selector-toggle";
        toggleBtn.textContent = (columnSelectorOpen ? "\u25bc" : "\u25b6") + " Table columns";
        toggleBtn.addEventListener("click", function () {
            columnSelectorOpen = !columnSelectorOpen;
            renderColumnSelector();
        });
        header.appendChild(toggleBtn);

        // Selected-only toggle (always visible)
        if (selectedUrns.size > 0) {
            var toggleLabel = document.createElement("label");
            toggleLabel.className = "col-toggle selected-only-toggle";
            var toggleCb = document.createElement("input");
            toggleCb.type = "checkbox";
            toggleCb.checked = tableSelectedOnly;
            toggleCb.addEventListener("change", function () {
                tableSelectedOnly = toggleCb.checked;
                renderSelectedTable();
            });
            toggleLabel.appendChild(toggleCb);
            toggleLabel.appendChild(document.createTextNode(" Highlighted only"));
            header.appendChild(toggleLabel);
        }

        container.appendChild(header);

        if (!columnSelectorOpen) return;

        var body = document.createElement("div");
        body.className = "col-selector-body";

        var groups = [];
        var groupMap = {};
        TABLE_COLUMNS.forEach(function (col) {
            if (!groupMap[col.group]) {
                groupMap[col.group] = [];
                groups.push(col.group);
            }
            groupMap[col.group].push(col);
        });

        groups.forEach(function (groupName) {
            var groupEl = document.createElement("span");
            groupEl.className = "col-group";

            var groupLabel = document.createElement("span");
            groupLabel.className = "col-group-label";
            groupLabel.textContent = groupName + ": ";
            groupEl.appendChild(groupLabel);

            groupMap[groupName].forEach(function (col) {
                var label = document.createElement("label");
                label.className = "col-toggle";
                var cb = document.createElement("input");
                cb.type = "checkbox";
                cb.checked = visibleColumns.has(col.key);
                cb.addEventListener("change", function () {
                    if (cb.checked) {
                        visibleColumns.add(col.key);
                    } else {
                        visibleColumns.delete(col.key);
                    }
                    renderSelectedTable();
                    pushStateToURL();
                });
                label.appendChild(cb);
                label.appendChild(document.createTextNode(" " + col.label));
                groupEl.appendChild(label);
            });

            body.appendChild(groupEl);
        });

        container.appendChild(body);
    }

    var TABLE_MAX_ROWS = 500;

    function renderSelectedTable() {
        var container = document.getElementById("selected-table-container");
        var colSelector = document.getElementById("column-selector");
        var hasFilters = getFilters().length > 0;


        // Build color map for selected schools
        var selectedColorMap = {};
        var colorIdx = 0;
        for (var urn of selectedUrns) {
            selectedColorMap[urn] = SELECTED_COLORS[colorIdx % SELECTED_COLORS.length];
            colorIdx++;
        }

        // Build school list
        var defaultSortKey = viewMode === "hist" ? histField : xField;
        var sortKey = tableSortKey || defaultSortKey;
        var sortDir = tableSortKey ? tableSortAsc : false;
        var sortFn = function (a, b) {
            var av = a[sortKey], bv = b[sortKey];
            if (av == null && bv == null) return 0;
            if (av == null) return 1;
            if (bv == null) return -1;
            if (typeof av === "string") {
                return sortDir ? av.localeCompare(bv) : bv.localeCompare(av);
            }
            return sortDir ? av - bv : bv - av;
        };

        var totalCount;
        var schoolList;
        var truncated = false;
        var tableRankMap = {};

        if (tableSelectedOnly) {
            schoolList = [];
            for (var su of selectedUrns) {
                var school = allSchools.find(function (s) { return s.urn === su; });
                if (school) schoolList.push(school);
            }
            totalCount = schoolList.length;
            schoolList.sort(sortFn);
            for (var ri2 = 0; ri2 < schoolList.length; ri2++) {
                tableRankMap[schoolList[ri2].urn] = ri2 + 1;
            }
        } else {
            // All filtered schools + any selected schools not in filtered set
            var all = filteredSchools.slice();
            var seen = new Set();
            for (var i = 0; i < filteredSchools.length; i++) {
                seen.add(filteredSchools[i].urn);
            }
            for (var su2 of selectedUrns) {
                if (!seen.has(su2)) {
                    var sch = allSchools.find(function (s) { return s.urn === su2; });
                    if (sch) all.push(sch);
                }
            }
            totalCount = all.length;
            all.sort(sortFn);

            // Build rank map from full sorted list
            tableRankMap = {};
            for (var ri = 0; ri < all.length; ri++) {
                tableRankMap[all[ri].urn] = ri + 1;
            }

            // Truncate but ensure selected schools are always included
            if (all.length > TABLE_MAX_ROWS) {
                var topSlice = all.slice(0, TABLE_MAX_ROWS);
                // Add any selected schools that didn't make the cut
                for (var j = TABLE_MAX_ROWS; j < all.length; j++) {
                    if (selectedUrns.has(all[j].urn)) topSlice.push(all[j]);
                }
                schoolList = topSlice;
                truncated = true;
            } else {
                schoolList = all;
            }
        }

        var cols = TABLE_COLUMNS.filter(function (c) { return visibleColumns.has(c.key); });

        renderColumnSelector();

        // Header
        var nameArrow = (sortKey === "name") ? (sortDir ? " \u25b2" : " \u25bc") : "";
        var html = "<table><thead><tr><th class='rank-col'>#</th><th class='school-name-col sortable' data-sort-key='name'>School" + nameArrow + "</th>";
        for (var c = 0; c < cols.length; c++) {
            var arrow = (sortKey === cols[c].key) ? (sortDir ? " \u25b2" : " \u25bc") : "";
            html += "<th class='sortable' data-sort-key='" + cols[c].key + "'>" + (cols[c].headerLabel || cols[c].label) + arrow + "</th>";
        }
        html += "</tr></thead><tbody>";

        // Pre-build rank lookups for visible rank columns
        var rankData = {};
        for (var rc = 0; rc < cols.length; rc++) {
            if (cols[rc].rank) {
                rankData[cols[rc].key] = buildRanks(cols[rc].key);
            }
        }

        // One row per school
        for (var s = 0; s < schoolList.length; s++) {
            var sch = schoolList[s];
            var isSelected = selectedColorMap[sch.urn];

            // Value row
            html += "<tr data-urn='" + sch.urn + "'" + (isSelected ? " class='selected-row clickable-row'" : " class='clickable-row'") + ">";
            html += "<td class='rank-col'>" + tableRankMap[sch.urn] + "</td>";
            var inFilter = isInFilteredSet(sch.urn);
            html += "<th class='school-name-col'>";
            if (isSelected) {
                html += "<span class='color-dot' style='background:" + isSelected + "'></span>";
            }
            if (isSelected && !inFilter) {
                html += "<span class='name-greyed'>" + sch.name + "</span>";
            } else {
                html += sch.name;
            }
            html += "</th>";
            for (var v = 0; v < cols.length; v++) {
                var val = sch[cols[v].key];
                var display;
                if (val == null) {
                    display = "\u2013";
                } else if (cols[v].fmt === "pct") {
                    display = val.toFixed(1) + "%";
                } else {
                    display = String(val);
                }

                // Append national percentile inline
                if (cols[v].rank && val != null) {
                    var nr = rankData[cols[v].key];
                    if (nr) display += " <span class='pct-inline'>" + formatRank(nr[sch.urn]) + "</span>";
                }

                html += "<td>" + display + "</td>";
            }
            html += "</tr>";
        }

        html += "</tbody></table>";
        if (truncated) {
            html += "<div class='table-truncated'>Showing " + schoolList.length +
                " of " + totalCount + " schools</div>";
        }
        container.innerHTML = html;

        // Attach sort handlers
        container.querySelectorAll(".sortable").forEach(function (th) {
            th.addEventListener("click", function (e) {
                e.stopPropagation();
                var key = th.getAttribute("data-sort-key");
                var effectiveKey = tableSortKey || (viewMode === "hist" ? histField : xField);
                if (effectiveKey === key) {
                    tableSortAsc = !tableSortAsc;
                } else {
                    tableSortAsc = false;
                }
                tableSortKey = key;
                pushStateToURL();
                renderSelectedTable();
            });
        });

        // Attach row click handlers
        container.querySelectorAll(".clickable-row").forEach(function (tr) {
            tr.addEventListener("click", function () {
                var urn = parseInt(tr.getAttribute("data-urn"), 10);
                if (!isNaN(urn)) toggleSchool(urn);
            });
        });
    }

    function getSelectedColor(urn) {
        let idx = 0;
        for (const u of selectedUrns) {
            if (u === urn) return SELECTED_COLORS[idx % SELECTED_COLORS.length];
            idx++;
        }
        return SELECTED_COLORS[0];
    }

    // --- Data loading and filtering ---

    function fetchData() {
        fetch(typeof DATA_URL !== "undefined" ? DATA_URL : API_URL)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                allSchools = data;
                onDataReady();
            });
    }

    function onDataReady() {
        renderSelectedChips();
        renderSelectedTable();
        onControlChange();
    }

    function schoolPercentile(ranks, urn) {
        var r = ranks[urn];
        if (!r) return null;
        return Math.round(((r.rank - 1) / (r.total - 1)) * 100);
    }

    function onControlChange() {
        var prevX = xField;
        var prevHist = histField;
        xField = document.getElementById("x-axis").value;
        yField = document.getElementById("y-axis").value;
        histField = document.getElementById("hist-var").value;
        if (xField !== prevX && !tableSortKey) tableSortAsc = false;
        if (histField !== prevHist && !tableSortKey) tableSortAsc = false;

        var filters = getFilters();
        var resolvedFilters = filters.map(function (f) {
            if (f.type === "percentile") {
                return {
                    type: "percentile",
                    schoolKey: f.schoolKey,
                    ranks: buildRanks(f.schoolKey),
                    lo: f.min,
                    hi: f.max,
                };
            }
            return f;
        });

        var requiredField = viewMode === "hist" ? histField : null;
        filteredSchools = allSchools.filter(function (s) {
            if (viewMode === "scatter") {
                if (s[xField] == null || s[yField] == null) return false;
            } else {
                if (s[requiredField] == null) return false;
            }
            for (var i = 0; i < resolvedFilters.length; i++) {
                var f = resolvedFilters[i];
                if (f.type === "match") {
                    if (f.numeric ? s[f.schoolKey] !== Number(f.value) : s[f.schoolKey] !== f.value) return false;
                } else if (f.type === "percentile") {
                    var pct = schoolPercentile(f.ranks, s.urn);
                    if (pct == null || pct < f.lo || pct > f.hi) return false;
                }
            }
            return true;
        });

        computeExtents();
        if (viewMode === "hist") computeRankData();
        onResize();
        updateStats();
        renderSelectedTable();
        pushStateToURL();
    }

    function computeExtents() {
        var validAll = allSchools.filter(function (s) {
            return s[xField] != null && s[yField] != null;
        });
        if (validAll.length === 0) {
            xMin = 0; xMax = 100; yMin = 0; yMax = 100;
            return;
        }
        var xs = validAll.map(function (s) { return s[xField]; });
        var ys = validAll.map(function (s) { return s[yField]; });
        xMin = Math.min.apply(null, xs);
        xMax = Math.max.apply(null, xs);
        yMin = Math.min.apply(null, ys);
        yMax = Math.max.apply(null, ys);

        var xPad = (xMax - xMin) * 0.02 || 1;
        var yPad = (yMax - yMin) * 0.02 || 1;
        xMin -= xPad;
        xMax += xPad;
        yMin -= yPad;
        yMax += yPad;
    }

    function computeRankData() {
        var field = histField;
        rankedSchools = allSchools.filter(function (s) { return s[field] != null; })
            .slice()
            .sort(function (a, b) { return a[field] - b[field]; });
    }

    // --- Drawing ---

    function onResize() {
        var container = canvas.parentElement;
        width = container.clientWidth - 2 * 16;
        height = Math.min(width * 0.6, 600);

        canvas.style.width = width + "px";
        canvas.style.height = height + "px";
        canvas.width = width * dpr;
        canvas.height = height * dpr;

        plotW = width - PADDING.left - PADDING.right;
        plotH = height - PADDING.top - PADDING.bottom;

        draw();
    }

    function toCanvasX(val) {
        return PADDING.left + ((val - xMin) / (xMax - xMin)) * plotW;
    }

    function toCanvasY(val) {
        return PADDING.top + plotH - ((val - yMin) / (yMax - yMin)) * plotH;
    }

    function draw() {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);
        if (viewMode === "hist") {
            drawRankPlot();
        } else {
            drawAxes();
            drawMedians();
            drawDots();
        }
        updateLegend();
    }

    function computeMedian(arr, key) {
        var vals = [];
        for (var i = 0; i < arr.length; i++) {
            if (arr[i][key] != null) vals.push(arr[i][key]);
        }
        if (vals.length === 0) return null;
        vals.sort(function (a, b) { return a - b; });
        var mid = vals.length / 2;
        if (vals.length % 2 === 1) return vals[Math.floor(mid)];
        return (vals[Math.floor(mid) - 1] + vals[Math.floor(mid)]) / 2;
    }

    function drawMedianLine(val, axis, color, dashed) {
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        if (dashed) ctx.setLineDash([8, 5]);
        ctx.beginPath();
        if (axis === "x") {
            var x = toCanvasX(val);
            ctx.moveTo(x, PADDING.top);
            ctx.lineTo(x, PADDING.top + plotH);
        } else {
            var y = toCanvasY(val);
            ctx.moveTo(PADDING.left, y);
            ctx.lineTo(PADDING.left + plotW, y);
        }
        ctx.stroke();
        ctx.restore();
    }

    function drawMedians() {
        var filterActive = getFilters().length > 0;

        var natXMed = computeMedian(allSchools, xField);
        var natYMed = computeMedian(allSchools, yField);
        if (natXMed != null) drawMedianLine(natXMed, "x", "#888", false);
        if (natYMed != null) drawMedianLine(natYMed, "y", "#888", false);

        if (filterActive) {
            var filtXMed = computeMedian(filteredSchools, xField);
            var filtYMed = computeMedian(filteredSchools, yField);
            if (filtXMed != null) drawMedianLine(filtXMed, "x", "#888", true);
            if (filtYMed != null) drawMedianLine(filtYMed, "y", "#888", true);
        }
    }

    function drawAxes() {
        ctx.strokeStyle = "#ccc";
        ctx.lineWidth = 1;
        ctx.strokeRect(PADDING.left, PADDING.top, plotW, plotH);

        ctx.fillStyle = "#666";
        ctx.font = "11px -apple-system, sans-serif";
        ctx.textAlign = "center";

        var xTicks = niceTicksFor(xMin, xMax);
        for (var i = 0; i < xTicks.length; i++) {
            var x = toCanvasX(xTicks[i]);
            ctx.beginPath();
            ctx.moveTo(x, PADDING.top);
            ctx.lineTo(x, PADDING.top + plotH);
            ctx.strokeStyle = "#eee";
            ctx.stroke();
            ctx.fillStyle = "#666";
            ctx.fillText(formatTick(xTicks[i]), x, height - PADDING.bottom + 18);
        }

        ctx.textAlign = "right";
        var yTicks = niceTicksFor(yMin, yMax);
        for (var j = 0; j < yTicks.length; j++) {
            var y = toCanvasY(yTicks[j]);
            ctx.beginPath();
            ctx.moveTo(PADDING.left, y);
            ctx.lineTo(PADDING.left + plotW, y);
            ctx.strokeStyle = "#eee";
            ctx.stroke();
            ctx.fillStyle = "#666";
            ctx.fillText(formatTick(yTicks[j]), PADDING.left - 8, y + 4);
        }

        ctx.fillStyle = "#333";
        ctx.font = "12px -apple-system, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(FIELD_LABELS[xField] || xField, PADDING.left + plotW / 2, height - 5);

        ctx.save();
        ctx.translate(14, PADDING.top + plotH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText(FIELD_LABELS[yField] || yField, 0, 0);
        ctx.restore();
    }

    function drawRankPlot() {
        // Draw axes
        ctx.strokeStyle = "#ccc";
        ctx.lineWidth = 1;
        ctx.strokeRect(PADDING.left, PADDING.top, plotW, plotH);

        if (rankedSchools.length === 0) return;

        var field = histField;
        var n = rankedSchools.length;
        var vMin = rankedSchools[0][field];
        var vMax = rankedSchools[n - 1][field];
        var vPad = (vMax - vMin) * 0.02 || 1;
        vMin -= vPad;
        vMax += vPad;

        function rankToX(i) {
            return PADDING.left + (i / (n - 1 || 1)) * plotW;
        }
        function valToY(val) {
            return PADDING.top + plotH - ((val - vMin) / (vMax - vMin)) * plotH;
        }

        // X-axis label (rank)
        ctx.fillStyle = "#333";
        ctx.font = "12px -apple-system, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("Rank", PADDING.left + plotW / 2, height - 5);

        // X-axis ticks
        ctx.fillStyle = "#666";
        ctx.font = "11px -apple-system, sans-serif";
        var xTicks = niceTicksFor(1, n);
        for (var t = 0; t < xTicks.length; t++) {
            var tx = rankToX(xTicks[t] - 1);
            ctx.beginPath();
            ctx.moveTo(tx, PADDING.top);
            ctx.lineTo(tx, PADDING.top + plotH);
            ctx.strokeStyle = "#eee";
            ctx.stroke();
            ctx.fillStyle = "#666";
            ctx.textAlign = "center";
            ctx.fillText(formatTick(xTicks[t]), tx, height - PADDING.bottom + 18);
        }

        // Y-axis ticks
        ctx.textAlign = "right";
        var yTicks = niceTicksFor(vMin, vMax);
        for (var yt = 0; yt < yTicks.length; yt++) {
            var yy = valToY(yTicks[yt]);
            ctx.beginPath();
            ctx.moveTo(PADDING.left, yy);
            ctx.lineTo(PADDING.left + plotW, yy);
            ctx.strokeStyle = "#eee";
            ctx.stroke();
            ctx.fillStyle = "#666";
            ctx.fillText(formatTick(yTicks[yt]), PADDING.left - 8, yy + 4);
        }

        // Y-axis label
        ctx.fillStyle = "#333";
        ctx.font = "12px -apple-system, sans-serif";
        ctx.save();
        ctx.translate(14, PADDING.top + plotH / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.textAlign = "center";
        ctx.fillText(FIELD_LABELS[field] || field, 0, 0);
        ctx.restore();

        // Draw lines for each school
        var baseline = PADDING.top + plotH;
        var filterActive = getFilters().length > 0;
        var filteredSet = null;
        if (filterActive) {
            filteredSet = new Set();
            for (var fi = 0; fi < filteredSchools.length; fi++) {
                filteredSet.add(filteredSchools[fi].urn);
            }
        }
        var lw = Math.max(1, plotW / n);

        // First pass: grey lines for unfiltered schools (or all if no filter)
        for (var i = 0; i < n; i++) {
            if (selectedUrns.has(rankedSchools[i].urn)) continue;
            if (filterActive && filteredSet.has(rankedSchools[i].urn)) continue;
            var x = rankToX(i);
            var y = valToY(rankedSchools[i][field]);
            ctx.strokeStyle = filterActive ? "rgba(180, 180, 180, 0.3)" : "rgba(51, 119, 204, 0.4)";
            ctx.lineWidth = lw;
            ctx.beginPath();
            ctx.moveTo(x, baseline);
            ctx.lineTo(x, y);
            ctx.stroke();
        }

        // Second pass: blue lines for filtered schools
        if (filterActive) {
            for (var i2 = 0; i2 < n; i2++) {
                if (selectedUrns.has(rankedSchools[i2].urn)) continue;
                if (!filteredSet.has(rankedSchools[i2].urn)) continue;
                var x2 = rankToX(i2);
                var y2 = valToY(rankedSchools[i2][field]);
                ctx.strokeStyle = "rgba(51, 119, 204, 0.4)";
                ctx.lineWidth = lw;
                ctx.beginPath();
                ctx.moveTo(x2, baseline);
                ctx.lineTo(x2, y2);
                ctx.stroke();
            }
        }

        // Draw median lines (horizontal)
        var natMed = computeMedian(allSchools, field);
        if (natMed != null) {
            ctx.save();
            ctx.strokeStyle = "#888";
            ctx.lineWidth = 2;
            ctx.beginPath();
            var my = valToY(natMed);
            ctx.moveTo(PADDING.left, my);
            ctx.lineTo(PADDING.left + plotW, my);
            ctx.stroke();
            ctx.restore();
        }
        if (filterActive) {
            var filtMed = computeMedian(filteredSchools, field);
            if (filtMed != null) {
                ctx.save();
                ctx.strokeStyle = "#888";
                ctx.lineWidth = 2;
                ctx.setLineDash([8, 5]);
                ctx.beginPath();
                var fmy = valToY(filtMed);
                ctx.moveTo(PADDING.left, fmy);
                ctx.lineTo(PADDING.left + plotW, fmy);
                ctx.stroke();
                ctx.restore();
            }
        }

        // Draw selected school lines on top
        for (var j = 0; j < n; j++) {
            var s = rankedSchools[j];
            if (!selectedUrns.has(s.urn)) continue;
            var sx = rankToX(j);
            var sy = valToY(s[field]);
            var color = getSelectedColor(s.urn);
            ctx.strokeStyle = color;
            ctx.lineWidth = Math.max(2, plotW / n);
            ctx.beginPath();
            ctx.moveTo(sx, baseline);
            ctx.lineTo(sx, sy);
            ctx.stroke();
            // Label
            ctx.fillStyle = isInFilteredSet(s.urn) ? color : "#aaa";
            ctx.font = "bold 11px -apple-system, sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(s.name, sx + 4, sy - 4);
        }

    }


    function updateLegend() {
        var legend = document.getElementById("chart-legend");
        var filterActive = getFilters().length > 0;
        var html = '<span class="chart-legend-item"><span class="chart-legend-line"></span> National median</span>';
        if (filterActive) {
            html += '<span class="chart-legend-item"><span class="chart-legend-line dashed"></span> Filtered median</span>';
        }
        legend.innerHTML = html;
    }

    function drawDots() {
        var filterActive = getFilters().length > 0;
        var allValid = allSchools.filter(function (s) {
            return s[xField] != null && s[yField] != null;
        });

        // Grey dots for all schools (when filtering)
        if (filterActive) {
            ctx.fillStyle = "rgba(180, 180, 180, 0.25)";
            for (var a = 0; a < allValid.length; a++) {
                if (selectedUrns.has(allValid[a].urn)) continue;
                ctx.beginPath();
                ctx.arc(toCanvasX(allValid[a][xField]), toCanvasY(allValid[a][yField]), DOT_RADIUS, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // Blue dots for filtered schools (or all if no filter)
        ctx.fillStyle = "rgba(51, 119, 204, 0.35)";
        for (var k = 0; k < filteredSchools.length; k++) {
            var su = filteredSchools[k];
            if (selectedUrns.has(su.urn)) continue;
            ctx.beginPath();
            ctx.arc(toCanvasX(su[xField]), toCanvasY(su[yField]), filterActive ? HIGHLIGHT_RADIUS : DOT_RADIUS, 0, Math.PI * 2);
            ctx.fill();
        }

        // Draw selected schools on top
        for (var urn of selectedUrns) {
            var school = allSchools.find(function (s) { return s.urn === urn; });
            if (!school || school[xField] == null || school[yField] == null) continue;
            var cx = toCanvasX(school[xField]);
            var cy = toCanvasY(school[yField]);
            var color = getSelectedColor(urn);
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(cx, cy, SELECTED_RADIUS, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = "white";
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Label
            ctx.fillStyle = isInFilteredSet(urn) ? color : "#aaa";
            ctx.font = "bold 11px -apple-system, sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(school.name, cx + SELECTED_RADIUS + 4, cy + 4);
        }

        // Hovered school (drawn last, on top of everything)
        if (hoveredSchool && !selectedUrns.has(hoveredSchool.urn)) {
            var hx = toCanvasX(hoveredSchool[xField]);
            var hy = toCanvasY(hoveredSchool[yField]);
            ctx.fillStyle = "rgba(220, 50, 50, 0.9)";
            ctx.beginPath();
            ctx.arc(hx, hy, HOVER_RADIUS, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    // --- Mouse interaction ---

    function onMouseMove(e) {
        var rect = canvas.getBoundingClientRect();
        var mx = e.clientX - rect.left;
        var my = e.clientY - rect.top;

        if (viewMode === "hist") return;

        var bestDist = Infinity;
        var best = null;
        var schools = filteredSchools;
        for (var i = 0; i < schools.length; i++) {
            var s = schools[i];
            if (s[xField] == null || s[yField] == null) continue;
            var dist = Math.hypot(mx - toCanvasX(s[xField]), my - toCanvasY(s[yField]));
            if (dist < bestDist && dist < 20) {
                bestDist = dist;
                best = s;
            }
        }

        if (best !== hoveredSchool) {
            hoveredSchool = best;
            draw();
        }

        if (best) {
            var xLabel = FIELD_LABELS[xField] || xField;
            var yLabel = FIELD_LABELS[yField] || yField;
            tooltip.innerHTML =
                "<strong>" + best.name + "</strong><br>" +
                best.la_name + " \u00b7 " + (best.town || "") + "<br>" +
                best.school_type + "<br>" +
                xLabel + ": " + formatValue(best[xField]) + "<br>" +
                yLabel + ": " + formatValue(best[yField]);
            tooltip.classList.add("visible");

            var tx = mx + 15;
            var ty = my - 10;
            if (tx + 300 > width) tx = mx - 260;
            if (ty < 0) ty = my + 15;
            tooltip.style.left = tx + "px";
            tooltip.style.top = ty + "px";
        } else {
            tooltip.classList.remove("visible");
        }
    }


    function onCanvasClick() {
        if (hoveredSchool) {
            toggleSchool(hoveredSchool.urn);
        }
    }

    function onMouseLeave() {
        hoveredSchool = null;
        tooltip.classList.remove("visible");
        draw();
    }

    // --- Stats ---

    function updateStats() {
        var stats = document.getElementById("stats");
        var n = filteredSchools.length;
        if (n === 0) {
            stats.textContent = "No schools match the current filters.";
            return;
        }

        var mean = function (arr) { return arr.reduce(function (a, b) { return a + b; }, 0) / arr.length; };
        var median = function (arr) {
            var sorted = arr.slice().sort(function (a, b) { return a - b; });
            var mid = Math.floor(sorted.length / 2);
            return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
        };

        if (viewMode === "hist") {
            var hVals = filteredSchools.map(function (s) { return s[histField]; }).filter(function (v) { return v != null; });
            var hLabel = FIELD_LABELS[histField] || histField;
            stats.innerHTML =
                "<strong>" + n + " schools</strong> \u00b7 " +
                hLabel + ": mean " + mean(hVals).toFixed(1) + ", median " + median(hVals).toFixed(1);
        } else {
            var xVals = filteredSchools.map(function (s) { return s[xField]; }).filter(function (v) { return v != null; });
            var yVals = filteredSchools.map(function (s) { return s[yField]; }).filter(function (v) { return v != null; });
            var xLabel = FIELD_LABELS[xField] || xField;
            var yLabel = FIELD_LABELS[yField] || yField;
            stats.innerHTML =
                "<strong>" + n + " schools</strong> \u00b7 " +
                xLabel + ": mean " + mean(xVals).toFixed(1) + ", median " + median(xVals).toFixed(1) + " \u00b7 " +
                yLabel + ": mean " + mean(yVals).toFixed(1) + ", median " + median(yVals).toFixed(1);
        }
    }

    // --- Utilities ---

    function niceTicksFor(min, max) {
        var range = max - min;
        if (range <= 0) return [min];
        var rough = range / 6;
        var mag = Math.pow(10, Math.floor(Math.log10(rough)));
        var step;
        if (rough / mag < 1.5) step = mag;
        else if (rough / mag < 3.5) step = 2 * mag;
        else if (rough / mag < 7.5) step = 5 * mag;
        else step = 10 * mag;

        var ticks = [];
        var t = Math.ceil(min / step) * step;
        while (t <= max) {
            ticks.push(t);
            t += step;
        }
        return ticks;
    }

    function formatValue(val) {
        if (val == null) return "\u2013";
        if (typeof val === "number") return +val.toFixed(2) + "";
        return val;
    }

    function formatTick(val) {
        if (Math.abs(val) >= 1000) return val.toLocaleString();
        if (val === Math.floor(val)) return val.toString();
        return val.toFixed(1);
    }

    document.addEventListener("DOMContentLoaded", init);
})();
