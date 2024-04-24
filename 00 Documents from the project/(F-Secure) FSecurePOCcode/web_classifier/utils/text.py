import string

_str_rep = str.maketrans("", "", string.punctuation)


def remove_punctuation(text):
    return text.translate(_str_rep)
