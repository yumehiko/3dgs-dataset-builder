# Roadmap

## v0.2

現状の到達点:

* Blender addon として install 可能
* Brush 互換 dataset を出力可能
* modal 実行と進捗表示あり
* 初期点群の位置と、シンプルなマテリアルの色を出力可能

## v0.3

テーマ: warning / metadata の可視化

予定:

* 実行結果の warning をより明確に一覧化する
* fallback が発生した material 名や件数を出力する
* dataset ごとの `metadata.json` を追加する
* 最低限の診断情報を残す

候補項目:

* addon version
* export timestamp
* frame count
* point sample count
* target collection 名
* output image resolution
* render engine
* fallback material list
* warning list

目的:

* 「なぜこの dataset 品質になったか」を後から追えるようにする
* Brush で問題が出たときの切り分けを楽にする

## v0.4

テーマ: 実データでのテストと精度調整

予定:

* 実運用データを使った複数ケース検証
* 半径レンジ、close-up ratio、frame count、point count の調整
* Brush 上での学習の進みやすさを観察して default 値を見直す
* カメラ分布とレンダリング条件の実用チューニングを行う

目的:

* テスト用サンプルではなく、実運用の asset でも安定して結果が出る状態に近づける

## v0.5

テーマ: 複雑マテリアルの強化

予定:

* 複雑ノードの色取得戦略を改善する
* glass や視点依存材質に対する fallback 方針を整理する
* procedural texture や複数ノード経路への対応可能性を調査する
* 「何が正確に取れて、何は近似なのか」を明文化する

目的:

* 初期点群色の品質を上げる
* 複雑マテリアルを含む asset でも初期状態の見た目を改善する

## Out Of Scope For Now

当面は後回しにする項目:

* 汎用 3DGS exporter としての多ターゲット対応
* COLMAP 互換や OpenCV 事前変換の再導入
* depth map export
* lighting variation

