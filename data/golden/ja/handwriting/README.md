# Japanese handwritten OCR fixtures

This starter set contains six historical handwritten hiragana glyphs with an authoritative modern equivalent for each glyph. Each row in `cases.jsonl` is one transcription case, with the image path relative to the manifest. Gold labels come from the first column of the original chart, verified against the row for each crop.

## Source and attribution

**KMNIST Dataset** (created by CODH), adapted from **Kuzushiji Dataset** (created by NIJL and others), DOI [10.20676/00000341](https://doi.org/10.20676/00000341). See the [dataset repository and its license](https://github.com/rois-codh/kmnist#license), the [source chart](https://github.com/rois-codh/kmnist/blob/master/images/kmnist_examples.png), and [Clanuwat et al.](https://arxiv.org/abs/1812.01718).

The chart and adapted image crops are licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This applies to the fixture images and adapted data in this directory. The source chart was **cropped, converted to grayscale, inverted to dark-on-white, enlarged fourfold with nearest-neighbor resampling, and padded with 12 white pixels** on each side. The original image is identified by GitHub blob SHA `7df90cbc30296cc9d7ad6afabddaee0ac79aaa8e` and SHA-256 `6b5bee58fa1272f2647f4b24534eae993d38fef531deb3fa5203cafceb139f1e`. The crop rectangles in `source_crop_box` are zero-based `[x, y, width, height]` in original chart pixels. Each row includes its own image checksum.

These are from the dataset's published preview. Writer identities and underlying train/test record IDs are unavailable, so every crop shares the same source group. Keep their scores separate from contemporary handwritten words and phrases used in Learnit. A future contemporary eval should use transcribed, appropriately licensed samples and report distinct writers or document sources.
