def ws_disambiguation(
    api_url: str, word: str, sentence: str, glosses: list[str]
) -> int:
    import requests

    if len(glosses) == 0:
        return 0

    prompt = """You're solving a word-sense disambiguation problem. Giving some glosses, a word and a sentence, you'll choose the word's gloss and return the gloss index number.

User:For these glosses:
"""
    for index, gloss in enumerate(glosses):
        prompt += f"{index}: {gloss}\n"

    prompt += f"""Return the gloss number of word "{word}" in sentence "{sentence}"
LLama:"""
    grammar = "root ::= " + "|".join(f'"{i}"' for i in range(len(glosses)))
    data = requests.post(api_url, json={"prompt": prompt, "grammar": grammar})
    if data.ok:
        result = data.json()
        return int(result["content"].removesuffix("<|eot_id|>"))
    return 0
