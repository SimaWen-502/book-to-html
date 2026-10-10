# Book to HTML · 把一本书整理成可离线阅读的网页

适用于知识书、实用书、学术书、小说和故事集的 AI 技能。读取你提供的原书，按真实内容整理为有目录、搜索、来源回查、复习问题和阅读进度的单文件 HTML。

本仓库采用第一版阅读样式：内容卡片、清晰正文、少量交互。小说按情节、人物和主题组织，可默认隐藏标有剧透的卡片。

**这是供 AI 助手使用的技能与本地工具。** Python 脚本负责提取、校验、渲染；阅读原书和撰写梳理内容由 AI 助手或你完成。仅运行提取脚本不会自动得到书籍总结。本地脚本与生成网页不需要 API Key，也不调用模型服务；AI 助手本身需要可用的模型环境。

## 先看效果

仓库包含两份专门编写的原创短文，没有商业书籍原文或个人笔记：

- [知识类：把计划变成行动](examples/nonfiction/index.html)，展示要点、对照表、练习和复习问题。
- [小说类：灯塔的最后一封信](examples/fiction/index.html)，展示人物、主题和剧透开关。

从 GitHub 下载 ZIP 并解压，双击示例的 `index.html` 即可离线阅读。GitHub 的文件页显示 HTML 源码；它不是网页预览。手机也可以用浏览器打开下载后的 HTML。

## 在 Codex 中使用

将整个仓库目录命名为 `book-to-html`，放入自己的 Codex 技能目录 `~/.codex/skills/`，使目录下直接有 `SKILL.md`、`scripts/`、`assets/`、`references/` 和 `agents/`。重新启动 Codex 后调用：

```text
使用 $book-to-html 整理我提供的这本书。
请单独创建项目文件夹，先判断体裁，按原书内容梳理。
保留来源回查，生成可离线阅读的 HTML。
```

也可以让 Codex 自带的 `skill-installer` 安装 `SimaWen-502/book-to-html` 仓库根目录，技能名称设为 `book-to-html`。已有同名技能时先备份，再替换。

对于部分阅读或小说，可以这样说：

```text
使用 $book-to-html 只整理第一章，不要读取或概述后续章节。
```

```text
使用 $book-to-html 整理这本小说。
重点梳理情节、人物变化和主题，把关键转折和结局标为剧透。
```

其他支持本地技能文件的 AI 助手可读取 `SKILL.md` 并按其中的流程使用脚本。具体安装目录取决于该助手。

## 本地运行与重建

Python 3.10 或以上。EPUB、DOCX、TXT、Markdown、HTML 的基础提取只依赖标准库。PDF 文本提取额外需要 PyMuPDF 或 pdfplumber；扫描 PDF 需要另行 OCR。图表、公式、多栏版面须人工或 AI 回查。

在仓库根目录运行原创示例：

```bash
python scripts/build_examples.py
python -m unittest discover -s tests -v
python scripts/check_release.py
```

整理自己的书时，将读书项目放在仓库外：

```bash
python scripts/extract_book.py /path/to/book.epub --out /path/to/my-book/source
# 阅读 source.json/segments，按 references/schema.md 编写 knowledge.json
python scripts/render_book.py --source /path/to/my-book/source/source.json --knowledge /path/to/my-book/knowledge.json --out /path/to/my-book/index.html
python scripts/validate_book.py --source /path/to/my-book/source/source.json --knowledge /path/to/my-book/knowledge.json --html /path/to/my-book/index.html
```

Windows 请替换成自己的路径，包含空格的路径用引号括起来。`knowledge.json` 是人工或 AI 整理的内容数据；其中 `source` 和 `interpretation` 观点应关联真实段落，额外建议使用 `editorial` 标记。数据格式见 [schema.md](references/schema.md)。

## 能力与边界

- 非虚构：核心观点、概念、方法、适用条件、对照表、练习和行动模板。
- 小说：分章情节、人物关系与变化、叙事线索、主题分析和剧透标记。
- 来源：章节/页码等定位、段落 ID、短摘录，区分书中内容与整理者补充。
- 阅读：目录、关键词搜索、阅读路线、标记已读、来源抽屉、打印和手动导出草稿。
- 离线：CSS、JS 与所选图片嵌入 HTML；没有远程字体、分析服务或后台上传。

结构校验不能证明总结正确，必须实际阅读原书。PDF 复杂内容的提取可能不完整。小说的剧透隐藏只是阅读控制，完整内容仍在 HTML 文件中；限定章节时必须从内容数据中排除后续章节。

已读状态保存在浏览器本地存储，能否保存取决于浏览器对本地文件的支持。草稿不会自动保存，关闭网页前请手动导出。

## 隐私与公开分享

仓库仅发布通用代码和原创示例。不要上传原书、提取全文、个人笔记、私有图片、密钥或本机配置。代码的 MIT 许可证不会赋予第三方书籍内容的传播权。

`source.json` 与 `segments/` 包含提取的原文，适合本地回查。公开版提取器的 `source_path` 仅保存文件名；文件名本身仍可能包含个人信息。生成 HTML 包含完整整理数据、所选图片和引用短摘录；隐藏卡片和未显示的数据字段也可以被读取，分享前仍须审查。`knowledge.json` 只能使用你信任的文件，因为图像路径会以当前用户权限读取本机文件。

[发布核查说明](docs/release-review.md)记录本次检查范围；[安全说明](SECURITY.md)介绍信任边界和安全反馈方式。发布前可运行 `python scripts/check_release.py`：它检查 `release-manifest.json` 中的全部文件，拒绝清单外文件与常见敏感内容。正则检查不能识别所有隐私，应结合人工阅读。

## 贡献与许可

欢迎通过 Issues 反馈使用问题，通过 Pull Requests 改进提取准确性、无障碍访问和可读性。示例请使用原创或明确允许再分发的内容，附上来源和授权说明。提交前运行上述重建、测试和发布检查。

代码、模板、文档和本仓库原创示例采用 [MIT License](LICENSE)。
