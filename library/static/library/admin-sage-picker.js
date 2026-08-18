(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        var sagesSelect = document.getElementById("id_sages");
        if (!sagesSelect) return;

        sagesSelect.style.display = "none";

        var wrapper = document.createElement("div");
        wrapper.className = "sage-picker";
        wrapper.innerHTML =
            '<div class="admin-picker-controls">' +
            '  <select class="sage-picker-select"><option value="">Мудрец…</option></select>' +
            '  <button type="button" class="sage-picker-add admin-picker-add button">Добавить</button>' +
            "</div>" +
            '<ul class="admin-picker-chosen"></ul>';
        sagesSelect.parentNode.insertBefore(wrapper, sagesSelect);

        var sagePickerSelect = wrapper.querySelector(".sage-picker-select");
        var addBtn = wrapper.querySelector(".sage-picker-add");
        var chosenList = wrapper.querySelector(".admin-picker-chosen");

        Array.prototype.forEach.call(sagesSelect.options, function (opt) {
            var picked = document.createElement("option");
            picked.value = opt.value;
            picked.textContent = opt.text;
            sagePickerSelect.appendChild(picked);
        });

        function renderChosen() {
            chosenList.innerHTML = "";
            Array.prototype.forEach.call(sagesSelect.options, function (opt) {
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
                empty.textContent = "Мудрецы не выбраны";
                chosenList.appendChild(empty);
            }
        }

        addBtn.addEventListener("click", function () {
            if (!sagePickerSelect.value) return;
            var opt = sagesSelect.querySelector('option[value="' + sagePickerSelect.value + '"]');
            if (opt) {
                opt.selected = true;
                renderChosen();
            }
            sagePickerSelect.value = "";
        });

        renderChosen();
    });
})();
