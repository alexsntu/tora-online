import random


def report_error_captcha(request):
    """Капча для виджета "Нашли ошибку" (_report_error.html) - он встроен как
    {% include %} на десятках разных страниц, а не на одной выделенной странице
    формы (как у Question, см. views._new_captcha), поэтому генерировать
    target/options приходится не в одном view, а централизованно здесь - тогда
    они попадают в контекст любой страницы автоматически, без правки каждого
    view по отдельности. Отдельный от Question ключ сессии ("report_error_captcha"),
    чтобы не затирать капчу вопроса, если она была показана в другой вкладке.
    """
    target = random.randint(1, 9)
    decoys = random.sample([n for n in range(1, 10) if n != target], 2)
    options = [target] + decoys
    random.shuffle(options)
    request.session["report_error_captcha"] = target
    return {"report_error_captcha_target": target, "report_error_captcha_options": options}
