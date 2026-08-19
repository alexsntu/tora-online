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
            '  <div class="sage-picker-list" role="listbox" tabindex="0"></div>' +
            '  <button type="button" class="sage-picker-add admin-picker-add button">Добавить</button>' +
            "</div>" +
            '<p class="sage-picker-hint">Дважды щёлкните по имени, чтобы сразу добавить мудреца</p>' +
            '<ul class="admin-picker-chosen"></ul>';
        sagesSelect.parentNode.insertBefore(wrapper, sagesSelect);

        var availableList = wrapper.querySelector(".sage-picker-list");
        var addBtn = wrapper.querySelector(".sage-picker-add");
        var chosenList = wrapper.querySelector(".admin-picker-chosen");
        var highlightedOpt = null;

        function addSage(opt) {
            if (!opt) return;
            opt.selected = true;
            highlightedOpt = null;
            render();
        }

        function render() {
            // Доступные для выбора - список
            availableList.innerHTML = "";
            Array.prototype.forEach.call(sagesSelect.options, function (opt) {
                if (opt.selected) return;
                var item = document.createElement("div");
                item.className = "sage-picker-item";
                item.textContent = opt.text;
                item.setAttribute("role", "option");
                if (opt === highlightedOpt) item.classList.add("selected");
                item.addEventListener("click", function () {
                    highlightedOpt = opt;
                    render();
                });
                item.addEventListener("dblclick", function () {
                    addSage(opt);
                });
                availableList.appendChild(item);
            });
            if (!availableList.children.length) {
                var empty = document.createElement("div");
                empty.className = "sage-picker-item sage-picker-empty";
                empty.textContent = "Все мудрецы выбраны";
                availableList.appendChild(empty);
            }

            // Уже выбранные - список с удалением
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
                    render();
                });
                li.appendChild(rm);
                chosenList.appendChild(li);
            });
            if (!chosenList.children.length) {
                var emptyChosen = document.createElement("li");
                emptyChosen.className = "admin-picker-empty";
                emptyChosen.textContent = "Мудрецы не выбраны";
                chosenList.appendChild(emptyChosen);
            }
        }

        addBtn.addEventListener("click", function () {
            addSage(highlightedOpt);
        });

        render();
    });
})();
