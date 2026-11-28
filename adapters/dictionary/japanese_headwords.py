"""Extract dictionary forms of content words using MeCab's passage context."""

from adapters.readings.mecab import reading_tagger

_CONTENT = {"名詞", "動詞", "形容詞", "形状詞", "副詞", "代名詞", "連体詞", "感動詞"}
_AUXILIARY_FORMS_KANA = {
    "アゲル", "アル", "イク", "イタダク", "イル", "オク", "オル", "クル", "クレル", "クダサル", "シマウ", "ミル", "モラウ",
}
_ADJECTIVE_SUFFIXES = {"らしい", "っぽい"}


def passage_headwords(passage: str) -> list[str]:
    tagger = reading_tagger()
    words = {}
    for line in passage.splitlines():
        tokens = list(tagger(line))
        for index, token in enumerate(tokens):
            if token.is_unk:
                continue
            feature = token.feature
            if feature.pos1 not in _CONTENT or feature.pos2 == "数詞":
                continue
            previous = tokens[index - 1] if index else None
            if previous is not None and previous.feature.pos2 == "数詞" and feature.pos3 == "助数詞可能":
                continue
            if feature.pos1 == "動詞" and feature.lemma == "為る":
                continue
            if (previous is not None and previous.feature.pos2 == "接続助詞" and previous.surface in {"て", "で"}
                    and feature.pos2 == "非自立可能" and feature.kanaBase in _AUXILIARY_FORMS_KANA):
                continue
            headword = feature.orthBase or token.surface
            if index + 1 < len(tokens):
                following = tokens[index + 1]
                suffix = following.feature.orthBase
                if following.feature.pos1 == "接尾辞" and suffix in _ADJECTIVE_SUFFIXES:
                    headword += suffix
            words[headword] = None
    return list(words)
