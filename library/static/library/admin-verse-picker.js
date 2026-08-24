(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var versesSelect = document.getElementById("id_verses");
        if (!versesSelect) return;

        var path = window.location.pathname;
        var base = path.replace(/(add|\d+\/change)\/$/, "");
        var dataUrl = base + "verse-picker-data.json/";

        versesSelect.style.display = "none";

        var wrapper = document.createElement("div");
        wrapper.className = "verse-picker";
        wrapper.innerHTML =
            '<div class="admin-picker-controls">' +
            '  <select class="verse-picker-book"><option value="">Книга…</option></select>' +
            '  <select class="verse-picker-chapter" disabled><option value="">Глава…</option></select>' +
            '  <select class="verse-picker-verse" disabled><option value="">Стих…</option></select>' +
            '  <button type="button" class="verse-picker-add admin-picker-add button">Добавить</button>' +
            "</div>" +
            '<ul class="admin-picker-chosen"></ul>' +
            '<p class="admin-picker-error" style="display:none">Нужно выбрать хотя бы один стих.</p>';
        versesSelect.parentNode.insertBefore(wrapper, versesSelect);

        var bookSelect = wrapper.querySelector(".verse-picker-book");
        var chapterSelect = wrapper.querySelector(".verse-picker-chapter");
        var verseSelect = wrapper.querySelector(".verse-picker-verse");
        var addBtn = wrapper.querySelector(".verse-picker-add");
        var chosenList = wrapper.querySelector(".admin-picker-chosen");
        var errorMsg = wrapper.querySelector(".admin-picker-error");

        var DATA = null;

        function fillSelect(select, items, placeholder) {
            select.innerHTML = "";
            var ph = document.createElement("option");
            ph.value = "";
            ph.textContent = placeholder;
            select.appendChild(ph);
            items.forEach(function (item) {
                var opt = document.createElement("option");
                opt.value = item[0];
                opt.textContent = item[1];
                select.appendChild(opt);
            });
            select.disabled = items.length === 0;
        }

        function renderChosen() {
            chosenList.innerHTML = "";
            Array.prototype.forEach.call(versesSelect.options, function (opt) {
                if (!opt.selected) return;
                var li = document.createElement("li");
                li.appendChild(document.createTextNode(opt.text));
                var rm = document.createElement("button");
                rm.type = "button";
                rm.className = "admin-picker-remove";
                rm.textContent = "✕";
                rm.title = "Убрать";
                rm.addEventListener("click", function () {
                    opt.selected = false;
                    renderChosen();
                });
                li.appendChild(rm);
                chosenList.appendChild(li);
            });
            if (!chosenList.children.length) {
                var empty = document.createElement("li");
                empty.className = "admin-picker-empty";
                empty.textContent = "Стихи не выбраны";
                chosenList.appendChild(empty);
            }
        }

        bookSelect.addEventListener("change", function () {
            chapterSelect.innerHTML = '<option value="">Глава…</option>';
            chapterSelect.disabled = true;
            verseSelect.innerHTML = '<option value="">Стих…</option>';
            verseSelect.disabled = true;
            if (!DATA || !bookSelect.value) return;
            var chapters = DATA.verses[bookSelect.value] || {};
            var chapterNums = Object.keys(chapters)
                .map(Number)
                .sort(function (a, b) {
                    return a - b;
                });
            fillSelect(
                chapterSelect,
                chapterNums.map(function (n) {
                    return [n, n];
                }),
                "Глава…"
            );
        });

        chapterSelect.addEventListener("change", function () {
            verseSelect.innerHTML = '<option value="">Стих…</option>';
            verseSelect.disabled = true;
            if (!DATA || !bookSelect.value || !chapterSelect.value) return;
            var verses = (DATA.verses[bookSelect.value] || {})[chapterSelect.value] || [];
            verses = verses.slice().sort(function (a, b) {
                return a[1] - b[1];
            });
            fillSelect(
                verseSelect,
                verses.map(function (v) {
                    return [v[0], v[1]];
                }),
                "Стих…"
            );
        });

        addBtn.addEventListener("click", function () {
            if (!verseSelect.value) return;
            // Сервер больше не рендерит <option> на каждый стих в базе (см. MaterialForm
            // в admin.py) - только на уже выбранные, поэтому для нового стиха создаём
            // <option> сами; на отправку формы это не влияет, т.к. валидация идёт по
            // полному queryset поля, а не по тому, что было отрендерено изначально.
            var opt = versesSelect.querySelector('option[value="' + verseSelect.value + '"]');
            if (!opt) {
                opt = document.createElement("option");
                opt.value = verseSelect.value;
                opt.textContent =
                    bookSelect.options[bookSelect.selectedIndex].textContent +
                    " " + chapterSelect.value + ":" +
                    verseSelect.options[verseSelect.selectedIndex].textContent;
                versesSelect.appendChild(opt);
            }
            opt.selected = true;
            errorMsg.style.display = "none";
            renderChosen();
        });

        var form = versesSelect.closest("form");
        if (form) {
            form.addEventListener("submit", function (e) {
                var hasVerse = Array.prototype.some.call(versesSelect.options, function (opt) {
                    return opt.selected;
                });
                if (!hasVerse) {
                    e.preventDefault();
                    errorMsg.style.display = "";
                    wrapper.scrollIntoView({ block: "center" });
                }
            });
        }

        renderChosen();

        fetch(dataUrl, { credentials: "same-origin" })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                DATA = data;
                fillSelect(
                    bookSelect,
                    data.books.map(function (b) {
                        return [b.id, b.name_ru];
                    }),
                    "Книга…"
                );
            });
    });
})();
