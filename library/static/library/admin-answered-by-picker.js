(function () {
    "use strict";

    var PRESET = "Дмитрий Калашник";
    var OTHER = "Другой автор…";

    document.addEventListener("DOMContentLoaded", function () {
        var input = document.getElementById("id_answered_by");
        if (!input) return;

        input.style.display = "none";

        var wrapper = document.createElement("div");
        wrapper.className = "answered-by-picker";

        var select = document.createElement("select");
        select.className = "answered-by-picker-select";
        [PRESET, OTHER].forEach(function (label) {
            var opt = document.createElement("option");
            opt.value = label;
            opt.textContent = label;
            select.appendChild(opt);
        });

        var customInput = document.createElement("input");
        customInput.type = "text";
        customInput.className = "answered-by-picker-custom vTextField";
        customInput.placeholder = "Введите имя автора ответа";

        var startValue = input.value || PRESET;
        var startIsCustom = startValue !== PRESET;
        select.value = startIsCustom ? OTHER : PRESET;
        customInput.value = startIsCustom ? startValue : "";
        customInput.style.display = startIsCustom ? "" : "none";

        function sync() {
            input.value = select.value === PRESET ? PRESET : customInput.value.trim();
        }

        select.addEventListener("change", function () {
            customInput.style.display = select.value === PRESET ? "none" : "";
            if (select.value !== PRESET) customInput.focus();
            sync();
        });
        customInput.addEventListener("input", sync);

        wrapper.appendChild(select);
        wrapper.appendChild(customInput);
        input.parentNode.insertBefore(wrapper, input);
        sync();
    });
})();
