(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var textarea = document.getElementById("id_article_text");
        if (!textarea) return;

        textarea.style.display = "none";

        var wrapper = document.createElement("div");
        wrapper.className = "richtext-wrap richtext-wrap-article";
        wrapper.innerHTML =
            '<div class="richtext-toolbar">' +
            '<button type="button" data-cmd="bold" title="Жирный"><b>Ж</b></button>' +
            '<button type="button" data-cmd="italic" title="Курсив"><i>К</i></button>' +
            '<button type="button" data-cmd="underline" title="Подчёркнутый"><u>Ч</u></button>' +
            '<button type="button" data-block="h2" title="Заголовок 2">Заголовок 2</button>' +
            '<button type="button" data-block="h3" title="Заголовок 3">Заголовок 3</button>' +
            '<button type="button" data-block="p" title="Обычный текст">Обычный текст</button>' +
            "</div>" +
            '<div class="richtext-editor" contenteditable="true"></div>';
        textarea.parentNode.insertBefore(wrapper, textarea);

        var editor = wrapper.querySelector(".richtext-editor");
        editor.innerHTML = textarea.value;

        function sync() {
            textarea.value = editor.innerHTML;
        }

        Array.prototype.forEach.call(wrapper.querySelectorAll(".richtext-toolbar button[data-cmd]"), function (btn) {
            btn.addEventListener("click", function () {
                editor.focus();
                document.execCommand(btn.dataset.cmd, false, null);
                sync();
            });
        });

        Array.prototype.forEach.call(wrapper.querySelectorAll(".richtext-toolbar button[data-block]"), function (btn) {
            btn.addEventListener("click", function () {
                editor.focus();
                document.execCommand("formatBlock", false, btn.dataset.block);
                sync();
            });
        });

        editor.addEventListener("input", sync);
        editor.addEventListener("blur", sync);

        var form = textarea.closest("form");
        if (form) form.addEventListener("submit", sync);
    });
})();
