# 高级自动漫画交付包 v1.0

从自然语言故事到主视觉、特写和环境格组合的黑白漫画页。默认 768×1152，Windows + NVIDIA；RTX 4070 Laptop 8GB / 32GB RAM 已实测。

## 开始

1. 阅读 `安装与使用手册.pdf` 或 `.txt`，下载官方 NVIDIA 便携版并单独解压。
2. 在全新专用便携版上运行 `准备核心环境.bat`，输入根目录，核对目标后输入 INSTALL。
3. 运行 `下载模型.bat`；或者下载 Release 中所有模型分卷与清单至 `model_parts/` 后运行 `合并模型分卷.bat`。
4. 运行 `校验模型.bat`，四模型通过后双击便携根目录 `run_premium_manga.bat`。
5. 导入 `workflow.json`，修改故事，运行一次。

小 ZIP 不含约 21.13GB 模型，也不含 Python/PyTorch 便携运行时。模型放私有 Release，下载需要仓库读取权限。安装依赖需要联网。

旧驱动 attention 错误可尝试 `run_premium_manga.bat --compat-sdpa`，详细边界见手册。结果有随机性，边框不是硬遮罩；支持范围与验收记录见 `validation.json`。

本包包含原始 GPL-3.0 ComfyUI 核心源码压缩包（vendor）及完整许可证；模型和其他第三方组件来源见 `THIRD_PARTY_NOTICES.md`。销售价值来自整合、文档和服务，不表示独占开源模型。
