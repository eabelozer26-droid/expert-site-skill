"""Проверка сайта эксперта по правилам скилла sait-eksperta.

Только читает файлы в указанной папке. Без сети, без запуска программ.
Запуск: python -I scripts/proverka_saita.py <папка сайта или index.html>
Код выхода: 0 нет ошибок, 1 есть замечания, 2 есть ошибки.
"""
import os
import re
import sys

NO_CYRILLIC = ["DM Sans", "DM Serif Display", "Syne", "Outfit", "Fraunces", "Space Grotesk"]
TIRED_FONTS = ["Inter", "Roboto", "Arial", "Open Sans", "Montserrat"]
CLICHES = [
    "не просто", "в современном мире", "раскройте свой потенциал", "уникальн",
    "оставляют главное", "на чём стою", "на чем стою", "погрузитесь", "трансформ",
    "выведем на новый уровень", "мы поможем вам достичь",
]
INTERNAL = [r"\b\d+\s*(ИИ[‑-])?отдел", r"проверк[аеи] на \d+ вопрос", r"\b0\s*выдум"]
NEON = re.compile(r"#(?:39ff14|ccff00|00ff88|00ffff|ff00ff|e4f58e|d1e030|fdff00)\b", re.I)


def rel(path):
    try:
        return os.path.relpath(path)
    except ValueError:
        return path


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def text_only(html):
    html = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.I)
    return re.sub(r"<[^>]+>", " ", html)


def check_html(path, out):
    html = read(path)
    css = " ".join(re.findall(r"<style[^>]*>([\s\S]*?)</style>", html, re.I))
    for link in re.findall(r'href="([^"]+\.css)"', html):
        p = os.path.normpath(os.path.join(os.path.dirname(path), link))
        if os.path.isfile(p):
            css += read(p)
    text = text_only(html)
    name = rel(path)

    def add(level, msg):
        out.append((level, name, msg))

    if "—" in text:
        add("ОШИБКА", "длинное тире в тексте: %d шт." % text.count("—"))
    low = text.lower()
    for c in CLICHES:
        if c in low:
            add("ЗАМЕЧАНИЕ", "штамп или слабая фраза: «%s»" % c)
    for pat in INTERNAL:
        if re.search(pat, text, re.I):
            add("ЗАМЕЧАНИЕ", "внутренняя кухня в тексте (%s): объясните пользу или уберите" % pat)
    fonts = " ".join(re.findall(r"family=([^&\"']+)", html)) + " " + css
    for f in NO_CYRILLIC:
        if re.search(re.escape(f).replace("\\ ", r"[ +]"), fonts):
            add("ОШИБКА", "шрифт без кириллицы: %s" % f)
    for f in TIRED_FONTS:
        if re.search(r"font-family:\s*['\"]?%s\b" % re.escape(f), css) or re.search(r"--(head|body)[^;]*\b%s\b" % re.escape(f), css):
            add("ЗАМЕЧАНИЕ", "усталый шрифт как голос сайта: %s" % f)
    if NEON.search(css + html):
        add("ЗАМЕЧАНИЕ", "неоновый или кислотный цвет")
    if re.search(r"linear-gradient\([^)]*(#8b5cf6|#a855f7|#7c3aed|#6366f1)[^)]*(#ec4899|#d946ef|#f472b6)", css, re.I):
        add("ЗАМЕЧАНИЕ", "фиолетово-розовый градиент, признак ИИ-шаблона")
    if re.search(r"background-clip:\s*text", css) and re.search(r"gradient", css):
        add("ЗАМЕЧАНИЕ", "возможен градиентный текст: проверьте")
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    for tag in imgs:
        if "alt=" not in tag:
            add("ОШИБКА", "картинка без alt: %s" % tag[:80])
    lazy = sum(1 for t in imgs if "loading=" in t)
    if len(imgs) > 3 and lazy == 0:
        add("ЗАМЕЧАНИЕ", "ни одна картинка не грузится лениво (loading=\"lazy\")")
    for tag in re.findall(r"<video\b[^>]*>", html, re.I):
        if "autoplay" in tag and "muted" not in tag:
            add("ОШИБКА", "видео с автозапуском без muted")
        if "poster=" not in tag:
            add("ЗАМЕЧАНИЕ", "видео без poster")
        if "playsinline" not in tag:
            add("ЗАМЕЧАНИЕ", "видео без playsinline (iPhone откроет на весь экран)")
    if re.search(r"(animation|transition|transform)", css) and "prefers-reduced-motion" not in css:
        add("ЗАМЕЧАНИЕ", "есть движение, но нет prefers-reduced-motion")
    if css.count("backdrop-filter") > 6:
        add("ЗАМЕЧАНИЕ", "много размытия backdrop-filter: тормозит на слабых телефонах")
    if re.search(r"(three(\.module)?(\.min)?\.js|WebGLRenderer)", html):
        add("ЗАМЕЧАНИЕ", "WebGL/3D-сцена: для эксперта обычно лишняя тяжесть")
    if 'name="viewport"' not in html:
        add("ОШИБКА", "нет meta viewport")


def check_weight(root, out):
    total = 0
    for dirpath, _, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            size = os.path.getsize(p)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                total += size
                if size > 400 * 1024:
                    out.append(("ЗАМЕЧАНИЕ", rel(p), "тяжёлая картинка %d КБ, сожмите до 250 КБ" % (size // 1024)))
    if total > 4 * 1024 * 1024:
        out.append(("ЗАМЕЧАНИЕ", rel(root), "все картинки вместе %d КБ" % (total // 1024)))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    target = sys.argv[1]
    out = []
    if os.path.isfile(target):
        check_html(target, out)
    else:
        for dirpath, _, files in os.walk(target):
            for f in files:
                if f.lower().endswith(".html"):
                    check_html(os.path.join(dirpath, f), out)
        check_weight(target, out)
    errors = [o for o in out if o[0] == "ОШИБКА"]
    for level, name, msg in out:
        print("%s | %s | %s" % (level, name, msg))
    print("Итог: ошибок %d, замечаний %d" % (len(errors), len(out) - len(errors)))
    return 2 if errors else (1 if out else 0)


if __name__ == "__main__":
    sys.exit(main())
