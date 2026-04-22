# AI Translation Project

一个本地翻译GUI，利用本地部署的ai翻译模型进行多种翻译。提供可视化界面、术语表导入、保留词规则、全文一致性记忆。


#下载链接

由于包含运行库的文件过大，此处提供百度网盘和google drive云盘两种下载方式

通过百度网盘分享的文件：LocalTranslation_v1.0.0.zip

链接: https://pan.baidu.com/s/11rjCTplMD7rhMEg85rmIHg?pwd=uysu 提取码: uysu 

链接：https://drive.google.com/file/d/1cg0EJw08vHx1N16tOmr0eCCxyT-bIYJ6/view?usp=drive_link

A native translation GUI that utilizes a locally deployed AI translation model for various translations. It provides a visual interface, terminology import, word retention rules, and full-text consistency memory.

本项目大量使用ai代码，在翻译细节改进部分进行过大规模的ai代码重构，应该不会有屎山堆积的情况

> 此项目重点放在 **视频 / 文件翻译** 场景，尤其优化了 EPUB 的翻译。剩下的部分(网页/文本)现有的浏览器自动翻译功能和翻译软件做的已十分成熟，因此只做了最简单的功能

## 功能特性

- 可视化桌面界面，便于日常翻译任务操作
- 支持质量增强配置：
  - 术语表（Glossary）
  - 保留词规则（Preserve Rules）
  - 全文一致性记忆（Consistency Memory）
  - 自动复查（Auto Review）
- 支持从自定义 CSV 导入术语表
- (需要按照模板进行csv编辑)
- 支持长文本分块与短段合并，减少上下文碎裂
- 支持 EPUB 文件翻译

## 项目结构

```text
app/
├─ config/
│  └─ settings.json
├─ core/
│  └─ quality/
│     ├─ consistency.py
│     ├─ enhanced_pipeline.py
│     ├─ glossary.py
│     └─ protector.py
├─ gui/
│  ├─ pages/
│  │  ├─ file_translate_page.py
│  │  ├─ text_translate_page.py
│  │  ├─ video_translate_page.py
│  │  └─ web_translate_page.py
│  ├─ main_window.py
│  └─ settings_window.py
├─ models/
│  ├─ registry.py
│  └─ scanner.py
├─ services/
│  ├─ chunk_service.py
│  ├─ config_service.py
│  ├─ protection_service.py
│  ├─ quality_check_service.py
│  ├─ subtitle_service.py
│  └─ translation_core.py
├─ tasks/
│  ├─ file_translation_task.py
│  ├─ text_translation_task.py
│  ├─ video_translation_task.py
│  └─ web_translation_task.py
└─ main.py

data/
├─ glossary.csv
└─ preserve_patterns.json
```

## 核心设计思路

### 1. 术语表
术语表用于强制固定专有名词、人物名、设定名等译法，避免同一文本中出现多个译名。

推荐格式：

```csv
source,target,case_sensitive
House of Suns,太阳之屋,false
Abigail,阿比盖尔,false
```

### 2. 保留词规则
对变量、占位符、路径、HTML 标签、URL 等内容进行保护，避免模型将其误翻译或破坏结构。

### 3. 全文一致性记忆
对重复出现的原文片段记录固定译文，尽量保持全文风格统一，尤其适合小说、长文档与重复术语较多的文本。

### 4. EPUB 处理策略

- 解析 XHTML / HTML 正文节点
- 只翻译正文可翻译标签
- 尽量保留非正文资源（图片、CSS、字体、导航文件等）
- 避免简单地将译文追加到原文后面造成双语残留与格式混乱

## 环境要求

- Python 3.10+
- Windows 为主要开发/测试环境

正常来说所有依赖已经打包进了程序，无需额外安装


> 具体入口请以你本地实际可运行方式为准。

## 设置说明

在设置窗口中可以配置：

- 是否启用术语表
- 是否启用保留词规则
- 是否启用全文一致性记忆
- 是否默认启用自动复查
- 术语表路径
- 保留规则路径
- 一致性记忆路径
- 短段合并阈值
- 单块最大字符数

## 自定义术语表导入

项目支持通过设置窗口导入自定义 CSV 术语表。

### 导入流程

1. 打开设置窗口
2. 选择 CSV 文件
3. 读取表头
4. 选择“源语言列”和“目标语言列”
5. 点击“导入为术语表”
6. 程序会生成内部统一格式的术语表 CSV，并更新配置

### 推荐输入 CSV

至少需要两列：

```csv
source,target
book,书
chapter,章节
```

如果你的 CSV 原始列名不同，也可以通过设置窗口手动指定映射列。

## 适用场景

- 小说翻译
- 长篇英文文本翻译
- EPUB 电子书翻译
- 有术语统一需求的项目文本翻译



## 开发建议

如果你打算继续扩展这个项目，推荐优先从以下方向入手：

1. 增强翻译核心的质量检查与重试逻辑
2. 提高 EPUB 内联标签保留能力
3. 为不同文件类型设计更多元细致的处理方案
4. 增加术语表热更新与预览功能

## 免责声明

本项目主要用于个人学习、研究和本地工作流优化。请在遵守模型服务条款、文件版权与相关法律法规的前提下使用。

## 许可证

使用 MIT Licence
