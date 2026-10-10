# 通用讲义数据

输入为 `source.json` 与 `knowledge.json`。所有路径相对各自JSON所在目录解析。字符串写为实际内容，无脚手架占位。标记字段为布尔值。

## source.json

提取脚本生成 `metadata`、`source_path`、`sha256`、`warnings`、`segments` 和 `images`。每个segment有唯一 `id`、`locator`、`titles` 与 `paragraphs`；每个paragraph有唯一 `id`、`text`、`kind`。引用格式：

```json
{"segment":"S0003","paragraphs":["P0002","P0003"]}
```

PDF locator保留物理页；其他输入保留文件/文档位置。需要其他工具提取时可适配到该schema。不得生成实际不存在的来源段落。

## knowledge.json

```json
{
  "title":"真实书名",
  "author":"作者或未确认",
  "mode":"nonfiction",
  "summary":"对全书结构与阅读目的的简明概括",
  "spoiler_default":"hide",
  "coverage":{"scope":"full","items":[{"label":"第一章","segments":["S0003"],"status":"read"}]},
  "groups":[{"id":"chapter-1","title":"第一章"}],
  "units":[{
    "id":"unit-1","group":"chapter-1","title":"不泄露隐藏情节的单元名称",
    "kind":"知识梳理","spoiler":false,"lead":"核心概括",
    "points":[{"text":"概括内容","origin":"source","refs":[{"segment":"S0003","paragraphs":["P0002"]}]}],
    "tables":[{"title":"模型对照","headers":["要素","含义"],"rows":[["A","解释"]],"origin":"editorial"}],
    "figures":[{"path":"../01_原书解析/images/figure.png","alt":"实际图像的描述","caption":"来源及阅读提示","origin":"source","refs":[{"segment":"S0003","paragraphs":["P0003"]}]}],
    "exercise":{"title":"阅读/应用练习","steps":["整理者补充的练习"]},
    "question":{"prompt":"思考问题","answer":"参考读法或要点"},
    "note":"重要条件、矛盾或不确定事项"
  }],
  "routes":[{"title":"真实阅读问题","keywords":["关键词"],"units":["unit-1"]}],
  "route_label":"工作问题检索",
  "templates":[{"title":"可填写记录","description":"用途及整理者补充说明","text":"填写内容"}]
}
```

其中 `tables`、`figures`、`exercise`、`question`、`note`、`routes`、`templates` 均可省略。`units` 不为空；每个单元至少有一个有来源的要点。`mode`可为`nonfiction`、`fiction`、`mixed`；`kind`可以是情节梳理、人物分析、主题解读、诗篇赏析等真实类型。

`origin=source`为原书内容概括，`interpretation`为整理者解读，`editorial`为新增辅助内容。解释性要点也要有文本证据；模板、练习与题目统一显示为整理者补充。表格保留来源说明，若表格单元含关键新判断，使用有refs的points说明依据。

`coverage.items`应覆盖所有提取单元（可一条映射多个segment），每条有`read`、`excluded`或`unread`状态；`excluded`和`unread`填写`reason`。同一个segment若跨章可在多个条目使用，不代表读了多次。`full`与`partial`声明针对用户指定的范围；解释读取范围及遗漏。

`spoiler=true`的单元默认不可见，目录和结果不会推荐它。一个可见单元内的任何摘要、题目和来源摘录都不得含用户想避开的后续剧情。需要不同剧透层次时拆单元，不使用隐藏答案掩盖可见题目中的泄露。

图片必须是实际本地可用图像。渲染器对PNG/JPEG/GIF/WebP做内嵌；自行生成SVG先检查并转成可嵌图像，或直接修改模板安全呈现。页面不外载资源。JSON不能传入未经检查的原始HTML当内容。
