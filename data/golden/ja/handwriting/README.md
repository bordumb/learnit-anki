# Japanese handwriting evaluation

The [manifest](cases.jsonl) records the published text, per-image reference, original image, reading order, and usage terms. The `passages` suite covers five real handwriting samples.

| Source | Cases | Image content |
| --- | ---: | --- |
| IngCrowd, *Japanese Handwriting — Office Memo* | 2 | The same two-sentence Japanese memo in two different native writers' hands. One example fits on one line and one wraps onto two. |
| Ryūnosuke Akutagawa, 『河童』 | 1 | Four contiguous manuscript columns from the passage about mist. |
| Kenji Miyazawa, 「雨ニモマケズ」 | 2 | Two pages from his pocket notebook with six or seven columns of text. |

## Contemporary handwriting

Credit **IngCrowd Inc.** for [Japanese Handwriting — Office Memo](https://huggingface.co/datasets/IngCrowd/japanese-handwriting-office-memo) under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). The two unmodified scans are from different native writers. The publisher provides a shared prompt. The reference for each image was visually checked against the prompt, including punctuation and the numeral. Both scans belong to one evaluation group because they share a prompt and should stay together in a train/test split.

## Original manuscripts

- **Ryūnosuke Akutagawa, 『河童』**, from the [National Diet Library's autograph manuscript scan](https://commons.wikimedia.org/wiki/File:NDL2541083_%E6%B2%B3%E7%AB%A5.pdf). The crop comes from IIIF canvas `R0000005`, written page 7. The four main-text columns were checked against the [old-kana Aozora Bunko text](https://www.aozora.gr.jp/cards/000879/files/45761_39095.html). The reference preserves historical kana and omits small ruby readings. Wikimedia Commons marks the mechanical scan as public domain.
- **Kenji Miyazawa, 「雨ニモマケズ」**, from a [public-domain photograph of the notebook](https://commons.wikimedia.org/wiki/File:Ame_ni_mo_makezu_poem_in_Miyazawa_Kenji%27s_pocket_notebook.jpg) published in Soichi Mori's 1943 biography. The two crops preserve the penmanship and the author's handwritten additions. Their main text was checked against [Aozora Bunko](https://www.aozora.gr.jp/cards/000081/files/45630_23908.html). The handwritten date is outside the crops. Both pages belong to the same evaluation group.

The modern memo and historical manuscripts are reported separately. The manuscript results reflect vertical reading order, historical orthography, and the condition of the original scan.

## Smoke tests

Six historical handwritten hiragana glyphs use the authoritative modern equivalent for each glyph. Labels come from the first column of the original chart, verified against each crop.

**KMNIST Dataset** (created by CODH), adapted from **Kuzushiji Dataset** (created by NIJL and others), DOI [10.20676/00000341](https://doi.org/10.20676/00000341). See the [dataset repository and its license](https://github.com/rois-codh/kmnist#license), the [source chart](https://github.com/rois-codh/kmnist/blob/master/images/kmnist_examples.png), and [Clanuwat et al.](https://arxiv.org/abs/1812.01718).

The chart and adapted smoke images are licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The source chart was cropped, converted to grayscale, inverted to dark-on-white, enlarged fourfold with nearest-neighbor resampling, and padded with 12 white pixels on each side. The original image is identified by GitHub blob SHA `7df90cbc30296cc9d7ad6afabddaee0ac79aaa8e` and SHA-256 `6b5bee58fa1272f2647f4b24534eae993d38fef531deb3fa5203cafceb139f1e`. The crop rectangles in `source_crop_box` are zero-based `[x, y, width, height]` in original chart pixels. Each row includes its own image checksum.

Writer identities and underlying train/test record IDs are unavailable in the preview, so the six crops share one source group.
