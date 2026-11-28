# 日本語手書き OCR の評価

[実験計画](../../docs/papers/japanese-handwriting-ocr-protocol.md)に沿って、同一の JaWildText 画像を Learnit の Apple Vision と Google Cloud Vision に通す。

## データと正解の再構築

リポジトリのルートから実行する。Python 3.13、Learnit の依存関係、Pillow 13.0.0、PyArrow 26.0.1、RapidFuzz 3.14.6 を使った。JPEG コーデックの版は `cohort-lock.json` にある。認識の実行には画像準備用の追加パッケージは不要。

```bash
python -m pip install pillow==13.0.0 pyarrow==26.0.1 rapidfuzz==3.14.6
study=output/ocr-ja/jawildtext-r1
paper=docs/papers/japanese-handwriting-ocr
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

python -m evals.ocr.prepare "$study" --reference-order "$paper/evidence/reference-order.json"
python -m evals.ocr.freeze "$study" "$study/reproduced"
cmp "$study/reproduced/cohort-lock.json" "$paper/evidence/cohort-lock.json"
```

準備コードは入力の Parquet ハッシュを照合し、原本と共通の前処理画像のハッシュを取る。公開版に `image_id` の衝突があるため、ケースは一意のファイル名全体で識別する。`freeze` は分割をまたぐ書き手・関連グループの重複と画像バイト列の重複を検査し、正解と画像のハッシュを記録する。取得済みのファイルを再利用して続けられる。別の Pillow や JPEG コーデックでハッシュが変わる場合は、記録した版で画像を再生成する。

読み順を再監査する場合は `python -m evals.ocr.audit "$study" pilot` と `python -m evals.ocr.audit "$study" heldout` で確認画像を作る。監査記録には行ポリゴン ID の順序と理由がある。変更した場合は `prepare` と `freeze` を再実行し、新しいマニフェストで実測する。

## 認識を実行

Apple は通常の macOS Terminal で、CLI の起動と実画像から文字が返ることを確認する。Google は Learnit の既存設定と認証をそのまま使う。ローカル設定が別の場所にある場合はランナーに `--env-file` を指定できる。

```bash
swiftc -o "$study/apple-ocr" evals/ocr/main.swift learnit-deck/learnit-deck/ImageOCR.swift

python -m evals.ocr.run apple "$study/prepared-smoke.jsonl" "$study/apple-smoke.jsonl" \
  --media-root "$study" --apple-cli "$study/apple-ocr"
python -m evals.ocr.run google "$study/prepared-smoke.jsonl" "$study/google-smoke.jsonl" \
  --media-root "$study"

bash evals/ocr/run-study.sh "$study" "$(command -v python)"
```

`run-study.sh` は監査済みのパイロット、最終評価の順に実行し、認識結果を `terminal-runs/` に保存する。Apple の事前試験が失敗しても Google は独立に進む。エンジンや件数を指定して再開する例を以下に示す。

```bash
python -m evals.ocr.run google "$study/pilot.jsonl" "$study/terminal-runs/google-pilot.jsonl" \
  --media-root "$study" --smoke-manifest "$study/prepared-smoke.jsonl" \
  --lock "$study/cohort-lock.json" --limit 10
```

最後まで実行するには `--limit` を外す。変更した画像や別のエンジン設定を混ぜず、同じマニフェストと出力ファイルで再開する。認証または接続が失敗した時点で処理を停止し、正常なレコードを保持する。各実行の事前試験は採点対象外の画像を使い、結果は `.preflight.json` に残す。

## 集計と論文

```bash
python -m evals.ocr.score "$study/heldout.jsonl" "$study/heldout-summary.json" \
  --apple "$study/terminal-runs/apple-heldout.jsonl" \
  --google "$study/terminal-runs/google-heldout.jsonl"

"$paper/build.sh"
```

片側が完了した時点では、そのエンジンのオプションだけを渡して集計できる。完了した全ページを集計し、途中の出力はエラーとして止める。両者を渡すと同一ページの差と、書き手・文書グループを再抽出した95%信頼区間が出る。ページ別の調査には `--page-scores` を使う。

論文のビルドには Pandoc と XeLaTeX、Libertinus、原ノ味明朝を使う。図は TikZ で描画する。Pandoc の変換後に XeLaTeX を2回実行し、生成した [PDF](../../docs/papers/japanese-handwriting-ocr/japanese-handwriting-ocr.pdf) を更新する。データのハッシュ、参照順序、事前試験の集計は [evidence](../../docs/papers/japanese-handwriting-ocr/evidence) にある。データ本体、OCR の生出力、資格情報は Git の対象外に置く。
