from typing import Any


def load_wsd_model():
    from transformers import AutoModel, AutoTokenizer

    model_name = "google-bert/bert-base-multilingual-cased"
    model = AutoModel.from_pretrained(
        model_name, output_hidden_states=True, torch_dtype="auto", device_map="auto"
    )
    model.eval()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    return model, tokenizer


def sentence_embedding(model, tokenizer, sentences: list[str]):
    import torch

    encodings = tokenizer(
        sentences,
        return_offsets_mapping=True,
        return_tensors="pt",
        padding=True,
        truncation=True,
    ).to(model.device)
    with torch.no_grad():
        hidden_states = model(
            input_ids=encodings["input_ids"], attention_mask=encodings["attention_mask"]
        ).hidden_states

    # remove special tokens and padding
    masks = []
    for sen_offsets in encodings["offset_mapping"]:
        masks.append(
            [0 if t_offset.tolist() == [0, 0] else 1 for t_offset in sen_offsets]
        )
    masks = torch.tensor(masks, device=model.device)
    # https://github.com/danlou/LMMS/blob/master/data/weights/lmms-sp-wsd.bert-large-cased.weights.txt
    weights = torch.tensor(
        [0.01473, 0.05975, 0.36144, 0.53920], dtype=torch.float32, device=model.device
    ).view(4, 1, 1, 1)
    weight_sum_layers = (weights * torch.stack(hidden_states[-5:-1])).sum(dim=1)

    sent_embeds = []
    filtered_offsets = []
    for sent_embed, offset, mask in zip(
        weight_sum_layers, encodings["offset_mapping"], masks
    ):
        sent_embeds.append(sent_embed[mask.bool()])
        filtered_offsets.append(offset[mask.bool()])

    return sent_embeds, filtered_offsets


EMBED_CACHE: dict[str, tuple[Any, Any]] = {}


def wsd(model, tokenizer, sent: str, word_offset: tuple[int, int], sense_embeds) -> int:
    import numpy as np

    if sent in EMBED_CACHE:
        batch_embeds, batch_offsets = EMBED_CACHE[sent]
    else:
        batch_embeds, batch_offsets = sentence_embedding(model, tokenizer, [sent])
        EMBED_CACHE.clear()
        EMBED_CACHE[sent] = (batch_embeds, batch_offsets)
    word_start, word_end = word_offset
    vec = []
    for embed, (token_start, token_end) in zip(batch_embeds[0], batch_offsets[0]):
        if token_start < word_end and token_end > word_start:
            vec.append(embed.cpu().numpy())
    if len(vec) == 0:
        return 0
    target_embedding = np.array(vec).mean(axis=0)
    target_embedding /= np.linalg.norm(target_embedding)
    sense_embeds = [
        np.array(list(map(float, sense_embed.split())), dtype=np.float32)
        for sense_embed in sense_embeds
    ]
    sims = np.dot(sense_embeds, target_embedding)
    return sims.argmax()
