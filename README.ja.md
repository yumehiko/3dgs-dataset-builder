# 3DGS Dataset Builder

Language: [English](README.md) | 日本語

3DGS Dataset Builder は、Blender のコレクションから Brush 互換の学習用データセットを出力する Blender 5.x アドオンです。

現在のリリース: `v0.3.3`

## 概要

このアドオンは、次の用途に絞って作られています。

* Blender 内のコレクションを選ぶ
* その周囲にランダムなカメラを配置してレンダリングする
* 対応するカメラ変換を出力する
* 初期化用の `points3d.ply` を面サンプリングで出力する

汎用的な 3DGS エクスポータを目指しているわけではありません。現状は Brush / Nerfstudio 系のデータセット構成に最適化されています。

## インストール

1. GitHub Releases から `three_dgs_dataset_builder.zip` をダウンロードします。
2. Blender で `Edit > Preferences > Add-ons` を開きます。
3. `Install from Disk` をクリックします。
4. ダウンロードした zip ファイルを選択します。
5. `3DGS Dataset Builder` を有効化します。

## UI の場所

アドオンを有効化したあと:

1. 3D ビューポートを開きます。
2. 右サイドバーが閉じていれば `N` キーで開きます。
3. `3DGS Dataset` タブを開きます。

パネルの場所は `View3D > Sidebar > 3DGS Dataset` です。

## クイックスタート

1. 出力したいメッシュを 1 つのコレクションにまとめます。
2. 出力画像に使いたいレンダー解像度とレンダーエンジンを Blender 側で設定します。
3. アドオンのパネルで `Save Path` と `Dataset Name` を設定します。
4. `Target Collection` を選択します。
5. カメラの注視先を特定オブジェクトにしたい場合は `Focus Object` を設定します。空の場合はワールド原点を使います。
6. フレーム数、カメラ半径、点群サンプル数を調整します。
7. `Generate Dataset` をクリックします。
8. レンダリング、点群サンプリング、最終書き出しが完了するまで待ちます。

## UI 項目

### Dataset

* `Save Path`: データセットフォルダを作るベースディレクトリ
* `Dataset Name`: `Save Path` の下に作られる出力フォルダ名
* `Include Extension`: Brush 互換のため有効のままにしてください

### Camera Sampling

* `Target Collection`: レンダリングと点群サンプリングの対象になるメッシュ入りコレクション
* `Focus Object`: 一時カメラの注視先になるオブジェクト。未設定時はワールド原点を使用
* `Total Frames`: 書き出す学習用ビュー数
* `View Distribution`: `Full Sphere` または `Upper Hemisphere`
* `Min Radius` / `Max Radius`: 注視点からの最小距離と最大距離
* `Close-up Ratio`: 最小距離寄りのビューをどの程度混ぜるか

### Point Cloud

* `Sample Count`: `points3d.ply` に書き出す面サンプル数

### Status And Actions

* `Status`: 現在のフェーズと進行状況を表示
* `Generate Dataset`: 出力を開始
* `Cancel Generation`: 現在の処理単位が終わったあとにキャンセル要求を出す

## 出力構成

各エクスポートは `Save Path / Dataset Name` に次のようなフォルダを作ります。

```text
my_dataset/
├── images/
│   ├── 00000.png
│   ├── 00001.png
│   └── ...
├── metadata.json
├── points3d.ply
├── transforms_test.json
└── transforms_train.json
```

補足:

* `transforms_train.json` にはレンダリングしたフレームが入ります。
* `transforms_test.json` は `frames` が空配列の状態で出力されます。
* `metadata.json` は成功時のみ書き出されます。

## 推奨シーン構成

次の条件だと安定しやすいです。

* 対象コレクションにメッシュオブジェクトが入っている
* メッシュが UV 展開されている
* マテリアルが `Principled BSDF` を使っている
* `Base Color` が単色またはシンプルな画像テクスチャで駆動されている

複雑なノードグラフ、反射や透過が強いマテリアル、プロシージャルテクスチャ、UV 未設定のメッシュでは結果が不安定になりやすいです。

## トラブルシュート

よくあるバリデーションエラー:

* `Save Path is required.`
* `Dataset Name is required.`
* `Target Collection is required.`
* `Target collection does not contain any mesh objects.`
* `Brush compatibility requires Include Extension to be enabled.`
* `Min Radius must be smaller than Max Radius.`

大きいアセットで止まって見える場合、重いのは最初のレンダーパスか、ワーカープロセスが進捗を出し始める前の点群サンプリング準備であることが多いです。

## 関連ドキュメント

* 技術背景とフォーマット詳細: [docs/technical-background.md](docs/technical-background.md)
* リリース履歴: [docs/releases.md](docs/releases.md)
* 今後の計画: [docs/roadmap.md](docs/roadmap.md)
* メンテナ向けメモ: [docs/development.md](docs/development.md)

アドオンを `make package` でパッケージングする手順は利用者向けではなく、[docs/development.md](docs/development.md) に記載しています。
