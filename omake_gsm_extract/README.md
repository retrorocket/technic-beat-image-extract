# Technic Beat PS2 `omake/xxx.gsm` 抽出ツール

PS2版のおまけに収録された画像をPNG化するツールです。

## 動作確認した環境

Python 3.10以上。numpyがない場合はインストールしてください。

```bash
pip3 install numpy
```

## 使い方

`technic_beat_gsm_extract.py` と `omake/xxx.gsm` を同じフォルダに置いて、次のコマンドを実行してください。

```bash
python3 technic_beat_gsm_extract.py {input}.gsm {output}.png --crop
```
