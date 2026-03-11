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

    var TABLE_ROWS = [
        { section: "School info" },
        { key: "la_name", label: "Local authority" },
        { key: "school_type", label: "Type" },
        { key: "religious_character", label: "Religious character" },
        { key: "number_on_roll", label: "Number on roll", rank: true },
        { section: "Demographics" },
        { key: "pct_fsm_ever", label: "% FSM ever", fmt: "pct", rank: true },
        { key: "pct_eal", label: "% EAL", fmt: "pct", rank: true },
        { key: "pct_sen", label: "% SEN (total)", fmt: "pct", rank: true },
        { key: "pct_sen_support", label: "% SEN support", fmt: "pct", rank: true },
        { key: "pct_sen_ehcp", label: "% SEN EHCP", fmt: "pct", rank: true },
        { key: "eligible_pupils", label: "KS2 eligible pupils", rank: true },
        { section: "Attainment" },
        { key: "pct_rwm_expected", label: "% RWM expected", fmt: "pct", rank: true },
        { key: "pct_rwm_higher", label: "% RWM higher", fmt: "pct", rank: true },
        { key: "pct_reading_expected", label: "% reading expected", fmt: "pct", rank: true },
        { key: "pct_reading_higher", label: "% reading higher", fmt: "pct", rank: true },
        { key: "pct_writing_expected", label: "% writing expected", fmt: "pct", rank: true },
        { key: "pct_writing_higher", label: "% writing higher", fmt: "pct", rank: true },
        { key: "pct_maths_expected", label: "% maths expected", fmt: "pct", rank: true },
        { key: "pct_maths_higher", label: "% maths higher", fmt: "pct", rank: true },
        { key: "reading_average", label: "Reading avg scaled score", rank: true },
        { key: "maths_average", label: "Maths avg scaled score", rank: true },
        { section: "Disadvantage gap" },
        { key: "pct_rwm_exp_fsm", label: "% RWM expected (FSM)", fmt: "pct", rank: true },
        { key: "pct_rwm_exp_not_fsm", label: "% RWM expected (non-FSM)", fmt: "pct", rank: true },
    ];

    var rankCache = {};

    let allSchools = [];
    let filteredSchools = [];
    let selectedUrns = new Set();
    let canvas, ctx, tooltip;
    let searchInput, searchResults, selectedContainer;
    let width, height, plotW, plotH;
    let xField, yField;
    let xMin, xMax, yMin, yMax;
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
        canvas.addEventListener("mouseleave", onMouseLeave);
        window.addEventListener("resize", onResize);
        window.addEventListener("popstate", function () {
            restoreStateFromURL();
            onDataReady();
        });

        fetchData();
    }

    // --- URL state ---

    function restoreStateFromURL() {
        var params = new URLSearchParams(window.location.search);
        if (params.has("x")) setSelectValue("x-axis", params.get("x"));
        if (params.has("y")) setSelectValue("y-axis", params.get("y"));
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

        var filters = getFilters();

        if (x !== "pct_fsm_ever") params.set("x", x);
        if (y !== "pct_rwm_expected") params.set("y", y);

        if (filters.length > 0) {
            params.set("f", filters.map(function (f) {
                return f.key + ":" + f.value;
            }).join(","));
        }
        if (selectedUrns.size > 0) {
            params.set("schools", Array.from(selectedUrns).join(","));
        }

        var qs = params.toString();
        var url = window.location.pathname + (qs ? "?" + qs : "");
        history.replaceState(null, "", url);
    }

    // --- Dynamic filters ---

    var FILTER_CATEGORIES = [
        { key: "la", label: "Local authority", type: "select", options: FILTER_OPTIONS.la_names, schoolKey: "la_name" },
        { key: "type", label: "School type", type: "select", options: FILTER_OPTIONS.school_types, schoolKey: "school_type" },
        { key: "religion", label: "Religious character", type: "select", options: FILTER_OPTIONS.religious_characters, schoolKey: "religious_character" },
    ];

    // Add a "min ..." entry for each demographic field
    for (var di = 0; di < DEMOGRAPHIC_FIELDS.length; di++) {
        var df = DEMOGRAPHIC_FIELDS[di];
        FILTER_CATEGORIES.push({
            key: df,
            label: "Min " + FIELD_LABELS[df],
            type: "percentile",
            schoolKey: df,
        });
    }

    function addFilterRow(categoryKey, value) {
        var container = document.getElementById("filter-rows");
        var row = document.createElement("div");
        row.className = "filter-row";

        // Category select
        var catSelect = document.createElement("select");
        catSelect.className = "filter-cat-select";
        catSelect.innerHTML = '<option value="">Choose...</option>';
        for (var i = 0; i < FILTER_CATEGORIES.length; i++) {
            var cat = FILTER_CATEGORIES[i];
            var opt = document.createElement("option");
            opt.value = cat.key;
            opt.textContent = cat.label;
            if (cat.key === categoryKey) opt.selected = true;
            catSelect.appendChild(opt);
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
                    o.textContent = catDef.options[j];
                    if (catDef.options[j] === value) o.selected = true;
                    valSelect.appendChild(o);
                }
                valSelect.addEventListener("change", onControlChange);
                valueContainer.appendChild(valSelect);
            } else if (catDef.type === "percentile") {
                var slider = document.createElement("input");
                slider.type = "range";
                slider.min = "0";
                slider.max = "100";
                slider.value = value || "0";
                slider.className = "pct-slider";
                var label = document.createElement("span");
                label.className = "pct-slider-label";
                label.textContent = "p" + (value || "0");
                slider.addEventListener("input", function () {
                    label.textContent = "p" + slider.value;
                    onControlChange();
                });
                valueContainer.appendChild(slider);
                valueContainer.appendChild(label);
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

        row.appendChild(catSelect);
        row.appendChild(valueContainer);
        row.appendChild(removeBtn);
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
                if (val) filters.push({ type: "match", key: catDef.key, schoolKey: catDef.schoolKey, value: val });
            } else if (catDef.type === "percentile") {
                var inputs = rows[i].querySelectorAll(".filter-value-container input");
                var pctVal = inputs.length ? parseInt(inputs[0].value, 10) : NaN;
                if (!isNaN(pctVal) && pctVal > 0) {
                    filters.push({ type: "percentile", key: catDef.key, schoolKey: catDef.schoolKey, value: pctVal });
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
                valid.push({ urn: s.urn, la: s.la_name, val: s[key] });
            }
        }

        valid.sort(function (a, b) { return a.val - b.val; });

        var national = {};
        var totalNational = valid.length;
        for (var n = 0; n < valid.length; n++) {
            national[valid[n].urn] = { rank: n + 1, total: totalNational };
        }

        var byLA = {};
        for (var j = 0; j < valid.length; j++) {
            var la = valid[j].la;
            if (!byLA[la]) byLA[la] = [];
            byLA[la].push(valid[j]);
        }

        var laRanks = {};
        for (var laName in byLA) {
            var laSchools = byLA[laName];
            for (var k = 0; k < laSchools.length; k++) {
                laRanks[laSchools[k].urn] = { rank: k + 1, total: laSchools.length };
            }
        }

        rankCache[key] = { national: national, la: laRanks };
        return rankCache[key];
    }

    function formatRank(rankObj) {
        if (!rankObj) return "\u2013";
        var pctile = Math.round(((rankObj.rank - 1) / (rankObj.total - 1)) * 100);
        return "p" + pctile;
    }

    function renderSelectedTable() {
        var container = document.getElementById("selected-table-container");
        if (selectedUrns.size === 0) {
            container.innerHTML = "";
            return;
        }

        var selectedList = [];
        var colorIdx = 0;
        for (var urn of selectedUrns) {
            var school = allSchools.find(function (s) { return s.urn === urn; });
            if (!school) continue;
            selectedList.push({
                school: school,
                color: SELECTED_COLORS[colorIdx % SELECTED_COLORS.length],
            });
            colorIdx++;
        }

        var numSchools = selectedList.length;

        // Header row: blank label cell, then one column per school
        var html = "<table><thead><tr><th></th>";
        for (var h = 0; h < numSchools; h++) {
            html += "<th class='school-col-header'>" +
                "<span class='color-dot' style='background:" + selectedList[h].color + "'></span>" +
                selectedList[h].school.name + "</th>";
        }
        html += "</tr></thead><tbody>";

        // One row per TABLE_ROWS entry
        for (var r = 0; r < TABLE_ROWS.length; r++) {
            var rowDef = TABLE_ROWS[r];

            if (rowDef.section) {
                html += "<tr class='section-row'><th colspan='" + (numSchools + 1) + "'>" +
                    rowDef.section + "</th></tr>";
                continue;
            }

            // Value row
            html += "<tr><th>" + rowDef.label + "</th>";
            for (var s = 0; s < numSchools; s++) {
                var val = selectedList[s].school[rowDef.key];
                var display;
                if (val == null) {
                    display = "\u2013";
                } else if (rowDef.fmt === "pct") {
                    display = val.toFixed(1) + "%";
                } else {
                    display = String(val);
                }
                html += "<td>" + display + "</td>";
            }
            html += "</tr>";

            // Percentile row (if applicable)
            if (rowDef.rank) {
                var ranks = buildRanks(rowDef.key);

                html += "<tr class='rank-row'><th>percentile (national / LA)</th>";
                for (var sn = 0; sn < numSchools; sn++) {
                    var urn = selectedList[sn].school.urn;
                    html += "<td>" + formatRank(ranks.national[urn]) +
                        " / " + formatRank(ranks.la[urn]) + "</td>";
                }
                html += "</tr>";
            }
        }

        html += "</tbody></table>";
        container.innerHTML = html;
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

    function percentileThreshold(key, pct) {
        var vals = allSchools
            .map(function (s) { return s[key]; })
            .filter(function (v) { return v != null; })
            .sort(function (a, b) { return a - b; });
        if (vals.length === 0) return -Infinity;
        var idx = Math.round((pct / 100) * (vals.length - 1));
        return vals[idx];
    }

    function onControlChange() {
        xField = document.getElementById("x-axis").value;
        yField = document.getElementById("y-axis").value;

        var filters = getFilters();
        var resolvedFilters = filters.map(function (f) {
            if (f.type === "percentile") {
                return { type: "percentile", schoolKey: f.schoolKey, threshold: percentileThreshold(f.schoolKey, f.value) };
            }
            return f;
        });

        filteredSchools = allSchools.filter(function (s) {
            if (s[xField] == null || s[yField] == null) return false;
            for (var i = 0; i < resolvedFilters.length; i++) {
                var f = resolvedFilters[i];
                if (f.type === "match") {
                    if (s[f.schoolKey] !== f.value) return false;
                } else if (f.type === "percentile") {
                    if (s[f.schoolKey] == null || s[f.schoolKey] < f.threshold) return false;
                }
            }
            return true;
        });

        computeExtents();
        onResize();
        updateStats();
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
        drawAxes();
        drawDots();
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

    function drawDots() {
        var filterActive = getFilters().length > 0;

        if (filterActive) {
            ctx.fillStyle = "rgba(200, 200, 200, 0.3)";
            for (var i = 0; i < allSchools.length; i++) {
                var s = allSchools[i];
                if (s[xField] == null || s[yField] == null) continue;
                if (selectedUrns.has(s.urn)) continue;
                ctx.beginPath();
                ctx.arc(toCanvasX(s[xField]), toCanvasY(s[yField]), DOT_RADIUS, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.fillStyle = "rgba(51, 119, 204, 0.6)";
            for (var j = 0; j < filteredSchools.length; j++) {
                var sf = filteredSchools[j];
                if (selectedUrns.has(sf.urn)) continue;
                ctx.beginPath();
                ctx.arc(toCanvasX(sf[xField]), toCanvasY(sf[yField]), HIGHLIGHT_RADIUS, 0, Math.PI * 2);
                ctx.fill();
            }
        } else {
            ctx.fillStyle = "rgba(51, 119, 204, 0.35)";
            for (var k = 0; k < filteredSchools.length; k++) {
                var su = filteredSchools[k];
                if (selectedUrns.has(su.urn)) continue;
                ctx.beginPath();
                ctx.arc(toCanvasX(su[xField]), toCanvasY(su[yField]), DOT_RADIUS, 0, Math.PI * 2);
                ctx.fill();
            }
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
            ctx.fillStyle = color;
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

        var bestDist = Infinity;
        var best = null;
        var schools = filteredSchools.length > 0 ? filteredSchools : [];
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
                xLabel + ": " + best[xField] + "<br>" +
                yLabel + ": " + best[yField];
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

        var xVals = filteredSchools.map(function (s) { return s[xField]; }).filter(function (v) { return v != null; });
        var yVals = filteredSchools.map(function (s) { return s[yField]; }).filter(function (v) { return v != null; });

        var mean = function (arr) { return arr.reduce(function (a, b) { return a + b; }, 0) / arr.length; };
        var median = function (arr) {
            var sorted = arr.slice().sort(function (a, b) { return a - b; });
            var mid = Math.floor(sorted.length / 2);
            return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
        };

        var xLabel = FIELD_LABELS[xField] || xField;
        var yLabel = FIELD_LABELS[yField] || yField;

        stats.innerHTML =
            "<strong>" + n + " schools</strong> \u00b7 " +
            xLabel + ": mean " + mean(xVals).toFixed(1) + ", median " + median(xVals).toFixed(1) + " \u00b7 " +
            yLabel + ": mean " + mean(yVals).toFixed(1) + ", median " + median(yVals).toFixed(1);
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

    function formatTick(val) {
        if (Math.abs(val) >= 1000) return val.toLocaleString();
        if (val === Math.floor(val)) return val.toString();
        return val.toFixed(1);
    }

    document.addEventListener("DOMContentLoaded", init);
})();
