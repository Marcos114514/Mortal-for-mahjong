# Mortal-for-mahjong
baseline model： Mortal

link：https://github.com/Equim-chan/Mortal

这是一个基于 Mortal 的麻将 AI/分析工具项目。

## 简介
本项目旨在通过 Mortal 引擎分析天凤/雀魂的牌谱。

## 功能特点
* 功能一：牌谱输入与解析
* 功能二：Mortal 权重推荐打法展示
* 功能三：数据可视化分析

## 关于数据集和训练模型
# Training Pipeline

1. Prepare mjai dataset by yourself(.json.gz)

2. Configure `config.toml`

3. Start training:

```bash
python train.py
```

4. Training outputs:

```text
mortal.train
mortal.best
```
The final best-performing checkpoint will be saved as:

```text
mortal.best
```

---

# 下一步：API Inference

通过api调用mortal.best模型进行推理，实现agent打麻将。


