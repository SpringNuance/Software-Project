import re

html_comments_re = re.compile(r"(<!--.*?-->)", flags=re.DOTALL)


def remove_html_comments(html):
    return html_comments_re.sub("", html)
