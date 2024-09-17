from config import get_config_by_name

language_models = {}


def create_language_models():
    global language_models
    from ai4bharat.transliteration import XlitEngine
    for lang in get_config_by_name("LANGUAGE_LIST"):
        language_models[lang] = XlitEngine(lang, beam_width=10, rescore=True)


def transliterate_using_model(lang_code, text):
    global language_models
    resp = language_models[lang_code].translit_sentence(text)
    return resp[lang_code]


