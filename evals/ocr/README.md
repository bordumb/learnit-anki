# 日本語手書き OCR の評価

[実験計画](../../docs/papers/japanese-handwriting-ocr-protocol.md)に沿って、JaWildText の画像を Apple Vision と Google Cloud Vision に通すための作業中のコード。評価ランナーはケースごとの認識結果を記録し、同じマニフェストと設定で途中から再開できる。

## 準備と実行

リポジトリのルートから実行する。Python 環境には Learnit の依存関係に加え、Pillow 13、PyArrow 26、RapidFuzz 3 が必要。Apple の実行には macOS と Swift が必要。

```bash
study=output/ocr-ja/jawildtext-r1
revision=627ca7ea7c224ffe1accff8737991fc2240784fa
mkdir -p "$study/shards"

curl -fLsS "https://huggingface.co/api/datasets/llm-jp/jawildtext/tree/$revision/handwriting_ocr" \
  -o "$study/shards/tree.json"

for i in 0 1 2 3 4 5; do
  file="$(printf 'train-%05d-of-00006.parquet' "$i")"
  if [ ! -f "$study/shards/$file" ]; then
    curl -fLsS --continue-at - \
      "https://huggingface.co/datasets/llm-jp/jawildtext/resolve/$revision/handwriting_ocr/$file" \
      -o "$study/shards/$file.part" || break
    mv "$study/shards/$file.part" "$study/shards/$file"
  fi
done

python -m evals.ocr.prepare "$study"
swiftc -o "$study/apple-ocr" \
  evals/ocr/main.swift learnit-deck/learnit-deck/ImageOCR.swift
```

`prepare.py` はシャードのハッシュを照合し、画像、転記、分割マニフェストを準備する。正解の読み順に修正が必要な場合は、ケース ID を行ポリゴン ID の配列に対応づけた JSON を `--reference-order` で指定する。実験計画に沿って、人手監査と対象の固定を認識実行前に行う。`fetch_rows.py` は Hugging Face のビューアーを調べる補助スクリプト。全データの取得には固定リビジョンの Parquet を使う。

パイロットは少数のケースから開始し、接続と出力を確認してから再開する。Google は既存の Learnit 設定から認証する。別の設定ファイルは `--env-file` で指定できる。

```bash
python -m evals.ocr.run apple "$study/pilot.jsonl" "$study/apple-pilot.jsonl" \
  --media-root "$study" --apple-cli "$study/apple-ocr" --limit 3
python -m evals.ocr.run google "$study/pilot.jsonl" "$study/google-pilot.jsonl" \
  --media-root "$study" --limit 3
```

## 進捗

Google の既存アダプターで公開画像1枚の読み取りを確認した。Apple のバッチ CLI はビルドできたが、使用した macOS 27.0 の制限付き実行環境では認識モデルの初期化に失敗した。実行可能な macOS 環境での動作確認、人手による読み順の監査、比較集計、論文 PDF が残っている。認識画像、生出力、資格情報は `output/` または既存のローカル設定で管理する。
