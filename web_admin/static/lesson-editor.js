(function () {
    "use strict";

    function escapeHTML(value) {
        return value.replace(/[&<>"']/g, function (character) {
            return {
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;"
            }[character];
        });
    }

    function formatInline(value) {
        return escapeHTML(value)
            .replace(/`([^`]+)`/g, "<code>$1</code>")
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.+?)\*/g, "<em>$1</em>");
    }

    function renderMarkdown(source) {
        const lines = source.replace(/\r\n/g, "\n").split("\n");
        const output = [];
        let paragraph = [];
        let listType = null;
        let codeLines = [];
        let inCode = false;

        function flushParagraph() {
            if (paragraph.length) {
                output.push("<p>" + formatInline(paragraph.join(" ")) + "</p>");
                paragraph = [];
            }
        }

        function closeList() {
            if (listType) {
                output.push("</" + listType + ">");
                listType = null;
            }
        }

        for (const line of lines) {
            if (line.trim().startsWith("```")) {
                flushParagraph();
                closeList();

                if (inCode) {
                    output.push("<pre><code>" +
                        escapeHTML(codeLines.join("\n")) +
                        "</code></pre>");
                    codeLines = [];
                    inCode = false;
                } else {
                    inCode = true;
                }
                continue;
            }

            if (inCode) {
                codeLines.push(line);
                continue;
            }

            if (!line.trim()) {
                flushParagraph();
                closeList();
                continue;
            }

            const heading = line.match(/^(#{1,3})\s+(.+)$/);
            if (heading) {
                flushParagraph();
                closeList();
                const level = heading[1].length;
                output.push("<h" + level + ">" +
                    formatInline(heading[2]) +
                    "</h" + level + ">");
                continue;
            }

            if (/^\s*[-*]\s+/.test(line)) {
                flushParagraph();
                if (listType !== "ul") {
                    closeList();
                    output.push("<ul>");
                    listType = "ul";
                }
                output.push("<li>" +
                    formatInline(line.replace(/^\s*[-*]\s+/, "")) +
                    "</li>");
                continue;
            }

            if (/^\s*\d+\.\s+/.test(line)) {
                flushParagraph();
                if (listType !== "ol") {
                    closeList();
                    output.push("<ol>");
                    listType = "ol";
                }
                output.push("<li>" +
                    formatInline(line.replace(/^\s*\d+\.\s+/, "")) +
                    "</li>");
                continue;
            }

            if (line.startsWith("> ")) {
                flushParagraph();
                closeList();
                output.push("<blockquote>" +
                    formatInline(line.slice(2)) +
                    "</blockquote>");
                continue;
            }

            closeList();
            paragraph.push(line.trim());
        }

        flushParagraph();
        closeList();

        if (inCode) {
            output.push("<pre><code>" +
                escapeHTML(codeLines.join("\n")) +
                "</code></pre>");
        }

        return output.join("") ||
            '<p class="preview-empty">Your formatted lesson will appear here.</p>';
    }

    function refresh(textarea) {
        const preview = document.querySelector(
            '[data-preview-for="' + textarea.id + '"]'
        );
        if (preview) {
            preview.innerHTML = renderMarkdown(textarea.value);
        }
    }

    document.querySelectorAll(".lesson-content-editor").forEach(function (textarea) {
        refresh(textarea);
        textarea.addEventListener("input", function () {
            refresh(textarea);
        });

        const section = textarea.closest(".language-section");
        if (!section) return;

        section.querySelectorAll(".lesson-toolbar button").forEach(function (button) {
            button.addEventListener("click", function () {
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                const selected = textarea.value.slice(start, end);

                let insertion = "";
                let cursorStart = start;
                let cursorEnd = start;

                if (button.dataset.wrap) {
                    const marker = button.dataset.wrap;
                    insertion = marker + (selected || "text") + marker;
                    cursorStart = start + marker.length;
                    cursorEnd = cursorStart + (selected || "text").length;
                } else if (button.dataset.prefix) {
                    const lineStart = textarea.value.lastIndexOf("\n", start - 1) + 1;
                    insertion = button.dataset.prefix;
                    textarea.setRangeText(insertion, lineStart, lineStart, "end");
                    textarea.focus();
                    refresh(textarea);
                    return;
                } else if (button.dataset.insert) {
                    insertion = button.dataset.insert.replace(/\\n/g, "\n");
                    cursorStart = start + insertion.indexOf("\n") + 1;
                    cursorEnd = cursorStart;
                }

                textarea.setRangeText(insertion, start, end, "end");
                textarea.focus();
                textarea.setSelectionRange(cursorStart, cursorEnd);
                refresh(textarea);
            });
        });
    });
})();
