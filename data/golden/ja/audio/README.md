# Japanese speech evaluation

The `passages` suite has eight continuous recordings with reference text. The [manifest](cases.jsonl) lists the local clip, source, transcription, timestamps, and license for each one.

| Source | Clips | Duration | Evaluation target |
| --- | ---: | --- | --- |
| Government Public Relations podcast, 「明日への声」 | 2 | 154.2–183.0 s | Multi-minute two-speaker questions and answers with published scripts |
| IngCrowd Japanese Themed Casual Conversation Corpus | 4 | 29.62–85.93 s | Two-speaker, unscripted dialogue with fillers, backchannels, and overlapping speech |
| Japanese Spoken Wikipedia, 「タチバナ」 | 2 | 20.70–22.50 s | Single-speaker narration with terminology and kanji compounds |

## Government Public Relations podcast

Two consecutive, multi-minute passages from the public [政府広報オンラインポッドキャスト feed](https://anchor.fm/s/10d733d28/podcast/rss). The source describes both episodes as also published in the accessibility audio series 「明日への声」. Government Public Relations supplies the complete scripts, including a female questioner and male respondent. The two cases share a speaker group.

| Case | Continuous range | Scope | Podcast | Published reference |
| --- | ---: | --- | --- | --- |
| Unknown copyright holders | 82.35–265.35 s (3m03s) | Questions 1–3 and their complete answers | [Episode](https://podcasters.spotify.com/pod/show/0msb0sikilg/episodes/ep-e3sho14) | [Volume 112, track 5](https://www.gov-online.go.jp/media/cd/202611/202611_05.html) |
| Responsibilities of pet owners | 52.90–207.10 s (2m34s) | Question 1 and its complete answer | [Episode](https://podcasters.spotify.com/pod/show/0msb0sikilg/episodes/ep-e3shni2) | [Volume 111, track 5](https://www.gov-online.go.jp/media/cd/202609/202609_05.html) |

The references use the publisher’s scripts. Printed Q/A labels and bullet formatting are omitted and spoken list numbers use Arabic digits. The clips were cut inside silent pauses using the script and acoustic landmarks and encoded as 24 kHz mono MP3. The speech is scripted dialogue and is scored in a separate category from unscripted conversation.

出典は「政府広報オンラインポッドキャスト」。内閣府大臣官房政府広報室の[ソーシャルメディア運用方針](https://www.gov-online.go.jp/sns_policy/)第5節に基づき、Learnit Ankiが音声を切り出して変換した。正解テキストは政府広報オンライン「明日への声」の掲載原稿を、[コンテンツ利用ルール](https://www.gov-online.go.jp/tos/)に基づき抜粋・整形した。The publisher’s podcast terms are compatible with [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Unscripted conversation

Credit **IngCrowd Inc.** for the [Japanese Themed Casual Conversation Corpus](https://huggingface.co/datasets/IngCrowd/japanese-themed-dialogue) under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/). Excerpts from the unmodified mixed audio cover hobbies, internet and communications, and education and science. The 86-second clip is a second, non-overlapping excerpt from the hobbies conversation. References use the original human ELAN segments, listed by annotation ID, in chronological order. The text preserves fillers, repetitions, and source punctuation. Nonverbal laughter tags are omitted. Overlapping passages are reported in their own category because a single linear prediction can place concurrent speech in a different order. The clips share one evaluation group because stable speaker identifiers across conversations are unavailable.

## Narration

Credit **段ボーリャ** for the [recording](https://commons.wikimedia.org/wiki/File:%E6%97%A5%E6%9C%AC%E8%AA%9E%E7%89%88%E3%82%A6%E3%82%A3%E3%82%AD%E3%83%9A%E3%83%87%E3%82%A3%E3%82%A2%E9%8C%B2%E9%9F%B3%E8%A8%98%E4%BA%8B%E3%80%8C%E3%82%BF%E3%83%81%E3%83%90%E3%83%8A%E3%80%8D2023%E5%B9%B410%E6%9C%8819%E6%97%A5%E7%89%88.ogg) and **Wikipedia contributors** for the [article revision](https://ja.wikipedia.org/w/index.php?title=%E3%82%BF%E3%83%81%E3%83%90%E3%83%8A&oldid=97494714). The two excerpts and their references are available under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The source recording was clipped and converted to mono MP3. The labels use the published script and omit ruby readings and citation markers. Boundaries were located with acoustic anchors near pauses. Minor deviations from the published script are possible. Both clips share one speaker group.

## Smoke tests

Six original recordings preserve the published references for short words and stock phrases. The media bytes are unchanged. Local filenames are shorter than the originals.

- The five WAVs are by **Fukujinzuke** (speaker and recorder), contributed to [Lingua Libre](https://lingualibre.org/) and hosted on Wikimedia Commons. Each original file title and its published transcription are linked in [cases.jsonl](cases.jsonl).
- [Koyuki.ogg](https://commons.wikimedia.org/wiki/File:Koyuki.ogg) is credited to **Quatrogatos**. The file page identifies the speaker as a native Japanese speaker and the name as 小雪.

The six recordings are distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
