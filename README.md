# 3DGS Dataset Builder

Blender 5.x 用の addon。Brush でそのまま読み込める training dataset を生成することを主目的にしている。

現行バージョンは `v0.3.0`。  
優先ターゲットは汎用 3DGS exporter ではなく、**Brush / Nerfstudio format 互換**。

## Current Status

`v0.3` で確認できていること:

* Blender からランダム視点の PNG 群を出力できる
* `transforms_train.json` / `transforms_test.json` を Brush が読める形式で書き出せる
* `points3d.ply` を初期点群として読み込める
* dataset ごとに `metadata.json` を出力し、warning / fallback 情報を残せる
* Brush 上で、少なくともテストデータでは初期形状の再現と学習進行を確認できている

## Supported Workflow

出力レイアウト:

* `images/*.png`
* `transforms_train.json`
* `transforms_test.json`
* `points3d.ply`
* `metadata.json`

UI:

* `Save Path`
* `Dataset Name`
* `Include Extension`
* `Target Collection`
* `Focus Object`
* `Total Frames`
* `Min Radius` / `Max Radius`
* `Close-up Ratio`
* `View Distribution`
* `Sample Count`

## Brush Compatibility

現行実装は Brush を前提にしている。

* `transform_matrix` は Blender ワールド行列をそのまま書き出す
* exporter 側で OpenCV 形式への事前変換はしない
* `Include Extension` は Brush 互換のため `ON` 必須
* `points3d.ply` は `ply_file_path` と同名ファイル探索の両方で拾えるように同ディレクトリへ出力する

## Material Support

初期点群の色は限定対応。

期待通りに色が出やすいもの:

* UV 展開済みメッシュ
* `Principled BSDF`
* `Base Color` に単色または画像テクスチャが接続されているケース

弱いもの:

* 複雑ノード
* glass / transmission / reflection 依存の見た目
* procedural texture 中心のマテリアル
* UV 未設定

unsupported な場合は、画像テクスチャ色を取れなければ `Base Color`、それも難しければ白に近い fallback を使う。

`v0.3` ではこの fallback 情報を `metadata.json` に記録する。

主に残すもの:

* addon version
* export timestamp
* frame count
* point sample count
* target collection 名
* output image resolution
* render engine
* warning list
* fallback material list と triangle 件数

## Render Behavior

Blender の Scene Render 設定を基本的に尊重する。

そのまま使うもの:

* render engine
* resolution
* resolution percentage
* pixel aspect
* 既存 camera の lens / sensor 系設定

一時的に上書きするもの:

* output format = `PNG`
* color mode = `RGBA`
* film transparent = `ON`
* scene camera
* render filepath

## Known Limitations

* Brush 前提のため、汎用 3DGS exporter としての互換性はまだ整理していない
* glass や複雑マテリアルでは、初期点群色は不正確になりやすい
* modal 化で UI 応答性は改善したが、各フレームの render 自体は同期処理
* `metadata.json` は成功完了時のみ出力する。cancel / error 時の診断永続化はまだ行わない
* fallback の可視化は material / triangle 集計までで、複雑ノードの詳細解析までは行わない

## Verification

ローカル確認済み:

* `pytest -q`
* `python3 -m compileall three_dgs_dataset_builder tests`

手動確認済み:

* Blender 上で dataset 出力
* Brush 上で初期点群読込
* テストデータでの学習進行確認

手動確認観点:

* dataset 出力後に `metadata.json` が生成される
* fallback material を含むシーンで warning と `metadata.json` の内容が一致する
* fallback のないシーンで warning 配列と fallback list が空になる

## Roadmap

今後の予定は [docs/roadmap.md](docs/roadmap.md) に記載。
