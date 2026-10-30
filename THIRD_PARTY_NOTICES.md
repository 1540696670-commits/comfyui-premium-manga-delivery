# 第三方组件与分发说明
核对日期：2026-10-30。收费对象为工作流整合、定制布局、教程和支持服务；开源组件及模型的权利归原作者。

- ComfyUI：GPL-3.0，官方 https://github.com/Comfy-Org/ComfyUI 。本包 vendor 内包含未修改的官方 v0.43.0 完整源码 ZIP 与 GPL-3.0 原文，源码可直接解压获取；不包含 Python/PyTorch 二进制。核心使用和再分发遵循其许可证。运行时 attention 开关由独立启动脚本设置，不修改源码包。
- VMNodes 0.3.2：MIT；完整原始 LICENSE 与 THIRD_PARTY_NOTICES 保留在 custom_nodes/VMNodes，来源 https://github.com/VividMuse-AGI/VMNodes 。本包未修改该节点包。
- json-repair 0.64.2：MIT；由安装程序从 PyPI 安装，许可证附 licenses。
- MOSS Image SFT INT8、Qwen3.5 9B INT8：Comfy-Org/MOSS-Image 模型卡 Apache-2.0；原始模型 OpenMOSS-Team/MOSS-Image-SFT，保留对应许可、来源及量化版本标识，不冒充训练作者。
- Qwen3 4B FP8：Comfy-Org/Z-Image-Turbo 的重打包文本编码器，原始 Qwen/Qwen3-4B，Apache-2.0。
- FLUX.2 VAE：Apache-2.0；BFL 官方 flux2 README 的 autoencoder 段落明确单独声明。这里不包含采用其他许可的 FLUX.2 dev 扩散模型。
- 模型完整清单、来源链接、大小及 SHA-256 见 models.json。分卷只拆分原字节，不训练、不修改模型权重。

本项目中的自定义 Director、premium_layout、Launcher 与安装辅助代码以原始源码交付。未对其附加统一开源许可证；买家可用于已购交付的本地运行与维护。第三方组件始终遵循其原许可证，不能用“禁止转发”等服务条款剥夺第三方开源权利。销售方需自行确定自有内容的合同条款与权利归属，不得删除第三方署名或声称对开源模型拥有独占权。

资料与模型不构成对生成图像版权、第三方角色/商标/人物权利或平台准入的保证。售卖前核对当前平台规则，作品发布按平台要求标识 AI 内容。
