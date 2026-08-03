# Technic Beat PS2 `menu/thumb.anm` 抽出ツール

アーケードモードで曲選択するときに表示される、元になったゲームのサムネ画像をフレーム別パレットでPNG化するツールです。  
日本版PS2テクニクビート、AC版テクニクビートで動作確認しています。  
AC版はメディアとセキュリティドングルにそれぞれ別のサムネ用画像 `THUMB` が入っており、ゲーム中に呼び出されるのはドングルに入っている方です。

## 動作確認した環境

Python 3.10以上。pillowがない場合はインストールしてください。

```bash
pip3 install pillow
```

## 使い方

`technic_beat_thumb_anm_extract.py` と `thumb.anm` を同じフォルダに置いて、次のコマンドを実行してください。

```bash
python3 technic_beat_thumb_anm_extract.py thumb.anm -o extracted --contact-sheet
```

`extracted` フォルダに次が作成されます。

```text
00.png
01.png
...
32.png
manifest.csv
contact_sheet.png
```

## 画像を整数倍で保存

ドットを崩さず2倍にする例です。

```bat
py technic_beat_thumb_anm_extract.py thumb.anm -o extracted_2x --contact-sheet --scale 2
```

## 色・透明度のオプション

通常はデフォルト設定が正しいです。

```text
PS2 CLUT並べ替え: 有効
アルファ: PS2方式（0x80を完全不透明として2倍）
```

比較調査用に次の指定もできます。

```bat
--no-clut-swizzle
--alpha raw
--alpha opaque
```

## RLE仕様

```text
先頭 u16 × 16 = 展開後サイズ

制御バイト bit7 = 1:
  次の1バイトを (control & 0x7F) + 2 回繰り返す

制御バイト bit7 = 0:
  control + 1 バイトを、その直後からコピーする
```

各フレームは 224×224 = 50176バイトのインデックス画像へ展開されます。
