/* Interactive example runner for the AnimaGeo guide.
 *
 * Each .ex.interactive block has a JSON template under data-example. Click
 * the "Edit" button → the pre/code swaps to a <textarea>, toolbar shows
 * Run/Reset/Close. Only one editor is active at a time; opening another
 * closes the current one.
 *
 * On boot: applies Python syntax highlighting to the displayed code and
 * stashes the raw text on ex.dataset.code so Edit gets unformatted input.
 *
 * Edit mode: textarea has zero padding/border, so the text starts at the
 * exact same pixel position as the displayed <pre>. An outline on
 * `.ex-code` signals edit mode without shifting content.
 */

(function () {
    'use strict';

    const ENDPOINT = (window.ANIMAGEO_RENDER_URL || '') + '/render';
    const STATUS_ENDPOINT = (window.ANIMAGEO_RENDER_URL || '') + '/';

    let activeExample = null;
    let serverOnline = null;

    // ── Python syntax highlighter ──────────────────────────────
    const PY_KEYWORDS = new Set([
        'for', 'if', 'else', 'elif', 'while', 'def', 'class', 'import', 'from',
        'return', 'with', 'as', 'in', 'not', 'and', 'or', 'is', 'lambda',
        'True', 'False', 'None', 'pass', 'break', 'continue', 'try', 'except',
        'finally', 'raise', 'yield', 'global', 'nonlocal', 'async', 'await',
    ]);

    const DSL_NAMES = new Set([
        // Primitives
        'Point', 'Segment', 'Line', 'Ray', 'Vector', 'Circle', 'CircleArc',
        'CircleSector', 'CircumcircleArc', 'CircumcircleSector',
        'Polygon', 'Angle', 'Arc', 'Semicircle',
        // Constructions
        'Midpoint', 'Intersect', 'OrthogonalLine', 'LineBisector',
        'AngularBisector', 'Centroid', 'Center', 'Tangent', 'Polar',
        'Mirror', 'Rotate', 'Translate', 'Touches',
        // Measurements
        'Distance', 'Area', 'Radius', 'Value',
        // Conic properties
        'Focus', 'Vertex', 'Directrix', 'Eccentricity', 'Axes',
        'MajorAxis', 'MinorAxis', 'SemiMajorAxisLength', 'SemiMinorAxisLength',
        // Curves
        'Conic', 'Function', 'ImplicitCurve', 'Ellipse', 'Parabola', 'Hyperbola',
        // Variables / sentinels
        'Measure', 'AngleSize', 'Boolean', 'If',
        // Namespace helpers
        'style', 'hide', 'show',
    ]);

    function escapeHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function highlightPython(code) {
        let out = '';
        let i = 0;
        const n = code.length;
        while (i < n) {
            const c = code[i];
            // comment
            if (c === '#') {
                const nl = code.indexOf('\n', i);
                const end = nl === -1 ? n : nl;
                out += '<span class="cmt">' + escapeHtml(code.slice(i, end)) + '</span>';
                i = end;
                continue;
            }
            // triple-quoted string (""" ... """)
            if ((c === '"' || c === "'") && code[i + 1] === c && code[i + 2] === c) {
                const q = c;
                let j = i + 3;
                while (j < n - 2 && !(code[j] === q && code[j + 1] === q && code[j + 2] === q)) {
                    j++;
                }
                const endJ = (j <= n - 3) ? j + 3 : n;
                out += '<span class="str">' + escapeHtml(code.slice(i, endJ)) + '</span>';
                i = endJ;
                continue;
            }
            // single-line string
            if (c === '"' || c === "'") {
                const q = c;
                let j = i + 1;
                while (j < n && code[j] !== q && code[j] !== '\n') {
                    if (code[j] === '\\' && j + 1 < n) j++;
                    j++;
                }
                const endJ = (j < n && code[j] === q) ? j + 1 : j;
                out += '<span class="str">' + escapeHtml(code.slice(i, endJ)) + '</span>';
                i = endJ;
                continue;
            }
            // number
            if (c >= '0' && c <= '9') {
                let j = i;
                while (j < n && /[0-9.]/.test(code[j])) j++;
                if (j < n && (code[j] === 'e' || code[j] === 'E')) {
                    j++;
                    if (j < n && (code[j] === '+' || code[j] === '-')) j++;
                    while (j < n && /[0-9]/.test(code[j])) j++;
                }
                out += '<span class="num">' + escapeHtml(code.slice(i, j)) + '</span>';
                i = j;
                continue;
            }
            // identifier
            if (/[a-zA-Z_]/.test(c)) {
                let j = i + 1;
                while (j < n && /[a-zA-Z0-9_]/.test(code[j])) j++;
                const word = code.slice(i, j);
                if (PY_KEYWORDS.has(word)) {
                    out += '<span class="kw">' + word + '</span>';
                } else if (DSL_NAMES.has(word)) {
                    out += '<span class="dsl">' + word + '</span>';
                } else {
                    out += escapeHtml(word);
                }
                i = j;
                continue;
            }
            out += escapeHtml(c);
            i++;
        }
        return out;
    }

    // ── Bash highlighter ───────────────────────────────────────
    const BASH_KEYWORDS = new Set([
        'if', 'then', 'else', 'elif', 'fi', 'for', 'do', 'done', 'while', 'until',
        'case', 'esac', 'function', 'in', 'return', 'break', 'continue', 'export',
        'source', 'local', 'readonly', 'unset', 'declare', 'typeset',
    ]);

    function highlightBash(code) {
        let out = '';
        let i = 0;
        const n = code.length;
        let atLineStart = true;
        while (i < n) {
            const c = code[i];
            // `$ ` prompt at line start
            if (atLineStart && c === '$' && (code[i + 1] === ' ' || code[i + 1] === '\t')) {
                out += '<span class="cmt">$</span>';
                i++;
                atLineStart = false;
                continue;
            }
            if (c === '#') {
                const nl = code.indexOf('\n', i);
                const end = nl === -1 ? n : nl;
                out += '<span class="cmt">' + escapeHtml(code.slice(i, end)) + '</span>';
                i = end;
                atLineStart = (code[i] === '\n');
                continue;
            }
            if (c === '"' || c === "'") {
                const q = c;
                let j = i + 1;
                while (j < n && code[j] !== q) {
                    if (code[j] === '\\' && j + 1 < n) j++;
                    if (code[j] === '\n') break;
                    j++;
                }
                const endJ = (j < n && code[j] === q) ? j + 1 : j;
                out += '<span class="str">' + escapeHtml(code.slice(i, endJ)) + '</span>';
                i = endJ;
                atLineStart = false;
                continue;
            }
            // $var or ${var}
            if (c === '$' && (/[a-zA-Z_{]/.test(code[i + 1] || ''))) {
                let j = i + 1;
                if (code[j] === '{') {
                    j++;
                    while (j < n && code[j] !== '}') j++;
                    if (j < n) j++;
                } else {
                    while (j < n && /[a-zA-Z0-9_]/.test(code[j])) j++;
                }
                out += '<span class="dsl">' + escapeHtml(code.slice(i, j)) + '</span>';
                i = j;
                atLineStart = false;
                continue;
            }
            // flag: -x or --xxx
            if (c === '-' && /[a-zA-Z\-]/.test(code[i + 1] || '')) {
                let j = i + 1;
                while (j < n && /[a-zA-Z0-9_\-]/.test(code[j])) j++;
                out += '<span class="num">' + escapeHtml(code.slice(i, j)) + '</span>';
                i = j;
                atLineStart = false;
                continue;
            }
            if (c >= '0' && c <= '9') {
                let j = i;
                while (j < n && /[0-9.]/.test(code[j])) j++;
                out += '<span class="num">' + escapeHtml(code.slice(i, j)) + '</span>';
                i = j;
                atLineStart = false;
                continue;
            }
            if (/[a-zA-Z_]/.test(c)) {
                let j = i + 1;
                while (j < n && /[a-zA-Z0-9_\-.]/.test(code[j])) j++;
                const word = code.slice(i, j);
                if (BASH_KEYWORDS.has(word)) {
                    out += '<span class="kw">' + word + '</span>';
                } else {
                    out += escapeHtml(word);
                }
                i = j;
                atLineStart = false;
                continue;
            }
            out += escapeHtml(c);
            if (c === '\n') atLineStart = true;
            else if (c !== ' ' && c !== '\t') atLineStart = false;
            i++;
        }
        return out;
    }

    // ── JSON highlighter ───────────────────────────────────────
    function highlightJson(code) {
        let out = '';
        let i = 0;
        const n = code.length;
        while (i < n) {
            const c = code[i];
            // inline // comment (non-standard, but used in guide annotations)
            if (c === '/' && code[i + 1] === '/') {
                const nl = code.indexOf('\n', i);
                const end = nl === -1 ? n : nl;
                out += '<span class="cmt">' + escapeHtml(code.slice(i, end)) + '</span>';
                i = end;
                continue;
            }
            if (c === '"') {
                let j = i + 1;
                while (j < n && code[j] !== '"') {
                    if (code[j] === '\\' && j + 1 < n) j++;
                    j++;
                }
                const endJ = (j < n) ? j + 1 : j;
                // Key? Check next non-ws char is `:`
                let k = endJ;
                while (k < n && /\s/.test(code[k])) k++;
                const isKey = code[k] === ':';
                const cls = isKey ? 'dsl' : 'str';
                out += '<span class="' + cls + '">' + escapeHtml(code.slice(i, endJ)) + '</span>';
                i = endJ;
                continue;
            }
            if ((c >= '0' && c <= '9') || (c === '-' && code[i + 1] >= '0' && code[i + 1] <= '9')) {
                let j = (c === '-') ? i + 1 : i;
                while (j < n && /[0-9.eE+-]/.test(code[j])) j++;
                out += '<span class="num">' + escapeHtml(code.slice(i, j)) + '</span>';
                i = j;
                continue;
            }
            if (/[a-zA-Z]/.test(c)) {
                let j = i + 1;
                while (j < n && /[a-zA-Z]/.test(code[j])) j++;
                const word = code.slice(i, j);
                if (word === 'true' || word === 'false' || word === 'null') {
                    out += '<span class="kw">' + word + '</span>';
                } else {
                    out += escapeHtml(word);
                }
                i = j;
                continue;
            }
            out += escapeHtml(c);
            i++;
        }
        return out;
    }

    // ── Language auto-detection ────────────────────────────────
    function detectLang(code) {
        const t = code.trim();
        // JSON: braces/brackets around key:value pairs
        if ((t.startsWith('{') && t.endsWith('}')) || (t.startsWith('[') && t.endsWith(']'))) {
            if (/"[\w_.-]+"\s*:/.test(t)) return 'json';
        }
        // Bash heuristics: shebang, `$ ` prompt, typical CLI starters
        if (/^\s*#!\/(bin\/)?(ba)?sh\b/.test(t) ||
            /^\s*\$\s+\S/m.test(code) ||
            /^\s*(pip|brew|apt|cd|python3?(\.\d+)?|manim|git|mkdir|ls|cat|curl|export|source|xdg-open|open)\s+\S/m.test(code)) {
            return 'bash';
        }
        return 'python';
    }

    function highlightCode(code, lang) {
        if (lang === 'bash') return highlightBash(code);
        if (lang === 'json') return highlightJson(code);
        return highlightPython(code);
    }

    // Apply highlighting to every <pre><code> block in main content.
    // Interactive blocks are skipped — setupExample handles those.
    function highlightAllBlocks() {
        document.querySelectorAll('main pre code').forEach((code) => {
            if (code.closest('.ex.interactive')) return;
            if (code.dataset.highlighted === '1') return;
            if (code.querySelector('span[class]')) return; // already hand-marked
            const raw = code.textContent;
            const lang = code.dataset.lang || detectLang(raw);
            code.innerHTML = highlightCode(raw, lang);
            code.dataset.highlighted = '1';
        });
    }

    // ── Server health check ─────────────────────────────────────
    async function checkServer() {
        try {
            const r = await fetch(STATUS_ENDPOINT, { method: 'HEAD', cache: 'no-store' });
            serverOnline = r.ok || r.status === 404;
        } catch (e) {
            serverOnline = false;
        }
        updateServerBanner();
    }

    function updateServerBanner() {
        let banner = document.querySelector('.server-status');
        if (!banner) {
            banner = document.createElement('div');
            banner.className = 'server-status';
            document.body.appendChild(banner);
        }
        if (serverOnline === false) {
            banner.innerHTML = 'Render-сервер не запущен. Запустите: <br><code>python3 docs/guide/server/serve.py</code>';
            banner.classList.add('visible');
        } else {
            banner.classList.remove('visible');
        }
    }

    // ── Scaffold (outer-layer Python) generation ───────────────
    function currentCode(ex) {
        const ta = ex.querySelector('textarea.ex-editor');
        if (ta) return ta.value;
        return (ex.dataset.code || '').replace(/^\n/, '').replace(/\n+$/, '');
    }

    function indentBlock(text, indent) {
        return text.split('\n').map(l => l ? indent + l : l).join('\n');
    }

    // ── Scaffold modes ─────────────────────────────────────────
    //
    // The same editable DSL block can be wired into AnimaGeoScene three
    // different ways. The scaffold panel shows how each one looks as
    // standalone Python — the rendered SVG is identical (all three end
    // up as one Construction after the DSL engine runs).
    //
    //   inline — code as a string; scene.putCode(code). Full DSL
    //            transform (LHS-name capture, loop-scope uniqueness).
    //   file   — same engine, but the code lives in a separate .ag.py
    //            loaded via scene.loadCode(path).
    //   pure   — no AST transform; plain Python inside
    //            `with dsl.scope(self.geo):`. IDE autocomplete works;
    //            elements need `name=` to get addressable names.
    const SCAFFOLD_MODES = ['inline', 'file', 'pure'];
    const SCAFFOLD_MODE_LABELS = {
        inline: 'Inline (putCode)',
        file:   'From file (loadCode)',
        pure:   'Pure Python (dsl.scope)',
    };

    function _scaffoldHeaderLines(spec) {
        const w = spec.w || 520;
        const h = spec.h || 340;
        const rend = spec.rendering_extra || null;
        const overlay = spec.overlay_extra || null;
        const lines = [
            'class Scene(AnimaGeoScene):',
            '    def construct(self):',
            '        self.applyStyle(',
            "            style='guide_style.json',",
            `            export={"size": {"width": ${w}, "height": ${h}}},`,
            '        )',
        ];
        if (rend) {
            lines.push(`        self.style.rendering.update(${JSON.stringify(rend)})`);
        }
        if (overlay?.angle_radius) {
            lines.push(`        self.style_config.overlay.angle_radius.update(${JSON.stringify(overlay.angle_radius)})`);
        }
        if (overlay?.label_placement) {
            lines.push(`        self.style_config.overlay.label_placement.update(${JSON.stringify(overlay.label_placement)})`);
        }
        if (overlay?.per_type) {
            lines.push(`        self.style_config.overlay.per_type.update(${JSON.stringify(overlay.per_type)})`);
        }
        if (overlay?.per_name) {
            lines.push(`        self.style_config.overlay.per_name.update(${JSON.stringify(overlay.per_name)})`);
        }
        return lines;
    }

    function _scaffoldTrailer(autoPlace) {
        const out = [
            '        self.addAllGeometry(show=True)',
            '        self.updateAllGeometry()',
        ];
        if (autoPlace) out.push('        self.autoPlaceLabels()');
        out.push("        self.exportSVG('out.svg')");
        out.push('', '', "if __name__ == '__main__':");
        out.push('    Scene().construct()');
        return out;
    }

    function generateScaffoldInline(ex) {
        const spec = JSON.parse(ex.dataset.example || '{}');
        const autoPlace = spec.auto_place !== false;
        const dsl = currentCode(ex).replace(/\n+$/, '');
        const lines = [
            '"""Inline — DSL приходит строкой.',
            '',
            'putCode() убирает общий отступ, запускает AST-transform',
            '(LHS-имена в Construction, loop-scope уникализация, sugar',
            'для f(x)=... и tuple-unpack), а потом exec в DSL-namespace.',
            '"""',
            'from animageo.animageo import AnimaGeoScene',
            '',
            '',
            ..._scaffoldHeaderLines(spec),
            '',
            '        self.putCode("""',
            indentBlock(dsl, ''),
            '""")',
            '',
            ..._scaffoldTrailer(autoPlace),
        ];
        return lines.join('\n');
    }

    function generateScaffoldFile(ex) {
        const spec = JSON.parse(ex.dataset.example || '{}');
        const autoPlace = spec.auto_place !== false;
        const dsl = currentCode(ex).replace(/\n+$/, '');
        const host = [
            '"""From file — DSL живёт в своём scene.ag.py.',
            '',
            'Тот же движок, что в inline (loadCode = open(path).read() + ',
            'putCode). Плюс в том, что редактор видит DSL как настоящий',
            'Python-файл: подсветка, линтер, стабы из <ggb>_stubs.pyi,',
            'нормальный git-diff.',
            '"""',
            'from animageo.animageo import AnimaGeoScene',
            '',
            '',
            ..._scaffoldHeaderLines(spec),
            '',
            "        self.loadCode('scene.ag.py')",
            '',
            ..._scaffoldTrailer(autoPlace),
        ];
        const companion = [
            '# scene.ag.py — тот же DSL, что был внутри putCode(""" … """).',
            '# Кладётся рядом со scene.py; scene.py загружает его на старте.',
            '',
            dsl,
        ];
        return host.join('\n') + '\n\n' +
               '# ─── scene.ag.py (соседний файл) ──────────────────────────\n' +
               companion.join('\n');
    }

    function generateScaffoldPure(ex) {
        const spec = JSON.parse(ex.dataset.example || '{}');
        const autoPlace = spec.auto_place !== false;
        const dsl = currentCode(ex).replace(/\n+$/, '');
        const lines = [
            '"""Pure Python — без AST-transform.',
            '',
            'dsl.scope(self.geo) привязывает Construction как текущую;',
            'фабрики из animageo.parsers.dsl.namespace (Point, Midpoint,',
            'Circle, …) регистрируются прямо в неё.',
            '',
            'Отличия от putCode:',
            "  * LHS-присвоение НЕ ловит имя — передавайте name='A'",
            '    явно, если нужен адресуемый элемент в графе.',
            '  * Нет loop-scope уникализации — повтор имени = коллизия.',
            '  * Нет сахара `f(x) = x^2` — пишите Function("y = x^2").',
            '',
            'Взамен — нормальный IDE autocomplete, линтеры, breakpoints.',
            '"""',
            'from animageo.animageo import AnimaGeoScene',
            'from animageo.parsers import dsl',
            'from animageo.parsers.dsl.namespace import (',
            '    Point, Segment, Line, Ray, Circle, Polygon, Midpoint,',
            '    Intersect, Center, Centroid, style, hide, show,',
            ')',
            '',
            '',
            ..._scaffoldHeaderLines(spec),
            '',
            '        with dsl.scope(self.geo):',
            indentBlock(dsl, '            '),
            '',
            '        self.geo.sortCommands()',
            '        self.updateAllGeometry()',
            '',
            ..._scaffoldTrailer(autoPlace),
        ];
        return lines.join('\n');
    }

    const SCAFFOLD_GENERATORS = {
        inline: generateScaffoldInline,
        file:   generateScaffoldFile,
        pure:   generateScaffoldPure,
    };

    function generateScaffold(ex, mode) {
        const m = SCAFFOLD_MODES.includes(mode) ? mode : 'inline';
        return SCAFFOLD_GENERATORS[m](ex);
    }

    function activeScaffoldMode(ex) {
        return ex.dataset.scaffoldMode || 'inline';
    }

    function toggleScaffold(ex) {
        let panel = ex.querySelector('.ex-scaffold');
        if (panel) {
            panel.remove();
            ex.classList.remove('scaffold-open');
            const btn = ex.querySelector('.btn.scaffold');
            if (btn) btn.textContent = 'Scaffold';
            return;
        }
        panel = document.createElement('div');
        panel.className = 'ex-scaffold';

        const header = document.createElement('div');
        header.className = 'ex-scaffold-header';
        const title = document.createElement('span');
        title.className = 'ex-label';
        title.textContent = 'scene.py · host-обёртка';
        header.appendChild(title);

        const tabs = document.createElement('div');
        tabs.className = 'ex-scaffold-tabs';
        const currentMode = activeScaffoldMode(ex);
        SCAFFOLD_MODES.forEach((m) => {
            const tab = document.createElement('button');
            tab.type = 'button';
            tab.className = 'ex-scaffold-tab' + (m === currentMode ? ' active' : '');
            tab.dataset.mode = m;
            tab.textContent = SCAFFOLD_MODE_LABELS[m];
            tab.addEventListener('click', () => {
                ex.dataset.scaffoldMode = m;
                tabs.querySelectorAll('.ex-scaffold-tab').forEach((t) => {
                    t.classList.toggle('active', t.dataset.mode === m);
                });
                refreshScaffold(ex);
            });
            tabs.appendChild(tab);
        });
        header.appendChild(tabs);
        panel.appendChild(header);

        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.innerHTML = highlightPython(generateScaffold(ex, currentMode));
        pre.appendChild(code);
        panel.appendChild(pre);
        ex.appendChild(panel);
        ex.classList.add('scaffold-open');
        const btn = ex.querySelector('.btn.scaffold');
        if (btn) btn.textContent = 'Hide scaffold';
    }

    function refreshScaffold(ex) {
        const panel = ex.querySelector('.ex-scaffold');
        if (!panel) return;
        const code = panel.querySelector('code');
        if (code) code.innerHTML = highlightPython(generateScaffold(ex, activeScaffoldMode(ex)));
    }

    // ── Editor activation ───────────────────────────────────────
    function openEditor(ex) {
        if (activeExample && activeExample !== ex) closeEditor(activeExample);
        if (ex.dataset.editing === '1') return;

        const codeEl = ex.querySelector('.ex-code');
        const pre = codeEl.querySelector('pre');
        const toolbar = codeEl.querySelector('.ex-toolbar');

        if (!ex._originalCode) {
            ex._originalCode = (ex.dataset.code || '').replace(/^\n/, '');
        }

        // Measure pre's rendered height BEFORE hiding so we can size the
        // editor wrapper identically — no jump on open.
        const preRect = pre.getBoundingClientRect();
        const preHeight = Math.max(preRect.height, 60);

        pre.style.display = 'none';

        // Overlay editor: transparent <textarea> on top of a highlighted
        // <pre> — syntax colors remain visible while typing.
        const wrap = document.createElement('div');
        wrap.className = 'ex-editor-wrap';
        wrap.style.height = preHeight + 'px';

        const bgPre = document.createElement('pre');
        bgPre.className = 'ex-editor-bg';
        bgPre.setAttribute('aria-hidden', 'true');
        const bgCode = document.createElement('code');
        bgPre.appendChild(bgCode);

        const ta = document.createElement('textarea');
        ta.className = 'ex-editor';
        ta.value = ex._originalCode;
        ta.spellcheck = false;
        ta.autocapitalize = 'off';
        ta.autocomplete = 'off';

        bgCode.innerHTML = highlightPython(ex._originalCode);

        const syncHighlight = () => {
            bgCode.innerHTML = highlightPython(ta.value);
        };
        const syncScroll = () => {
            bgPre.scrollTop = ta.scrollTop;
            bgPre.scrollLeft = ta.scrollLeft;
        };

        ta.addEventListener('input', () => { syncHighlight(); refreshScaffold(ex); });
        ta.addEventListener('scroll', syncScroll);
        ta.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const s = ta.selectionStart;
                const end = ta.selectionEnd;
                ta.value = ta.value.slice(0, s) + '    ' + ta.value.slice(end);
                ta.selectionStart = ta.selectionEnd = s + 4;
                syncHighlight();
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                runEditor(ex);
            }
        });

        wrap.appendChild(bgPre);
        wrap.appendChild(ta);
        codeEl.appendChild(wrap);

        toolbar.innerHTML = '';
        const runBtn = mkButton('Run', 'run', () => runEditor(ex));
        const resetBtn = mkButton('Reset', '', () => {
            ta.value = ex._originalCode;
            syncHighlight();
            ta.setSelectionRange(0, 0);
            ta.scrollTop = 0;
            ta.scrollLeft = 0;
            bgPre.scrollTop = 0;
            bgPre.scrollLeft = 0;
            ta.focus({ preventScroll: true });
        });
        const closeBtn = mkButton('Close', '', () => closeEditor(ex));
        toolbar.append(runBtn, resetBtn, closeBtn);

        ex.dataset.editing = '1';
        ex.classList.add('editing');
        activeExample = ex;

        // Cursor at position 0, no page scroll, no internal textarea scroll
        ta.setSelectionRange(0, 0);
        ta.scrollTop = 0;
        ta.scrollLeft = 0;
        bgPre.scrollTop = 0;
        bgPre.scrollLeft = 0;
        ta.focus({ preventScroll: true });
    }

    function closeEditor(ex) {
        if (ex.dataset.editing !== '1') return;
        const codeEl = ex.querySelector('.ex-code');
        const pre = codeEl.querySelector('pre');
        const toolbar = codeEl.querySelector('.ex-toolbar');
        const wrap = codeEl.querySelector('.ex-editor-wrap');
        if (wrap) wrap.remove();
        if (pre) pre.style.display = '';
        toolbar.innerHTML = '';
        const editBtn = mkButton('Edit', '', () => openEditor(ex));
        const scaffoldBtn = mkButton(
            ex.classList.contains('scaffold-open') ? 'Hide scaffold' : 'Scaffold',
            'scaffold', () => toggleScaffold(ex),
        );
        toolbar.append(editBtn, scaffoldBtn);
        ex.dataset.editing = '0';
        ex.classList.remove('editing');
        if (activeExample === ex) activeExample = null;

        if (ex._originalSrc) {
            const img = ex.querySelector('.ex-visual img');
            if (img) img.src = ex._originalSrc;
            ex.classList.remove('has-error', 'has-run');
        }
    }

    function mkButton(label, variant, onClick) {
        const b = document.createElement('button');
        b.className = 'btn' + (variant ? ' ' + variant : '');
        b.type = 'button';
        b.textContent = label;
        b.addEventListener('click', onClick);
        return b;
    }

    // ── Run ─────────────────────────────────────────────────────
    async function runEditor(ex) {
        const ta = ex.querySelector('textarea.ex-editor');
        const visual = ex.querySelector('.ex-visual');
        const img = visual.querySelector('img');
        const metaEl = visual.querySelector('.ex-meta');
        const runBtn = ex.querySelector('.btn.run');

        if (!ex._originalSrc && img) ex._originalSrc = img.src;

        const spec = JSON.parse(ex.dataset.example || '{}');
        spec.code = ta.value;

        ex.classList.add('rendering');
        ex.classList.remove('has-error');
        runBtn.classList.add('busy');
        const t0 = performance.now();

        let response;
        try {
            response = await fetch(ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(spec),
            });
        } catch (e) {
            showError(ex, 'Сервер недоступен. Запустите render-сервер:\n  python3 docs/guide/server/serve.py');
            ex.classList.remove('rendering');
            runBtn.classList.remove('busy');
            serverOnline = false;
            updateServerBanner();
            return;
        }

        ex.classList.remove('rendering');
        runBtn.classList.remove('busy');

        if (!response.ok) {
            let msg;
            try {
                const j = await response.json();
                msg = j.error || (`HTTP ${response.status}`);
            } catch (e) {
                msg = `HTTP ${response.status}`;
            }
            showError(ex, msg);
            return;
        }

        const svgText = await response.text();
        const elapsed = Math.round(performance.now() - t0);
        const cacheHit = response.headers.get('X-Cache') === 'hit';
        const serverMs = response.headers.get('X-Render-Time-Ms') || '?';

        img.src = 'data:image/svg+xml;base64,' + utf8ToBase64(svgText);
        ex.classList.add('has-run');
        if (metaEl) metaEl.textContent =
            cacheHit ? `кэш · ${elapsed}ms` : `рендер ${serverMs}ms · ${elapsed}ms total`;
        serverOnline = true;
        updateServerBanner();
    }

    function showError(ex, msg) {
        let errEl = ex.querySelector('.ex-error');
        if (!errEl) {
            errEl = document.createElement('div');
            errEl.className = 'ex-error';
            ex.querySelector('.ex-visual').appendChild(errEl);
        }
        errEl.textContent = msg;
        ex.classList.add('has-error');
    }

    function utf8ToBase64(str) {
        return btoa(unescape(encodeURIComponent(str)));
    }

    // ── Boot ────────────────────────────────────────────────────
    function boot() {
        document.querySelectorAll('.ex.interactive').forEach(setupExample);
        highlightAllBlocks();
        checkServer();
    }

    function setupExample(ex) {
        const pre = ex.querySelector('.ex-code pre');
        const codeEl = pre ? pre.querySelector('code') : null;
        if (codeEl && !ex.dataset.code) {
            const raw = codeEl.textContent.replace(/^\n+/, '').replace(/\n+$/, '') + '\n';
            ex.dataset.code = raw;
            codeEl.innerHTML = highlightPython(raw);
        }

        const exCodeEl = ex.querySelector('.ex-code');
        let toolbar = exCodeEl.querySelector('.ex-toolbar');
        if (!toolbar) {
            toolbar = document.createElement('div');
            toolbar.className = 'ex-toolbar';
            exCodeEl.appendChild(toolbar);
        }
        toolbar.innerHTML = '';
        toolbar.appendChild(mkButton('Edit', '', () => openEditor(ex)));
        toolbar.appendChild(mkButton('Scaffold', 'scaffold', () => toggleScaffold(ex)));

        const visual = ex.querySelector('.ex-visual');
        if (visual && !visual.querySelector('.ex-error')) {
            const err = document.createElement('div');
            err.className = 'ex-error';
            visual.appendChild(err);
        }
        if (visual && !visual.querySelector('.ex-spinner')) {
            const sp = document.createElement('div');
            sp.className = 'ex-spinner';
            sp.textContent = 'рендерю…';
            visual.appendChild(sp);
        }
        if (visual && !visual.querySelector('.ex-meta')) {
            const m = document.createElement('div');
            m.className = 'ex-meta';
            visual.appendChild(m);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
