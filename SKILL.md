---
name: douyin-script-imitator
description: 抖音/短视频脚本仿写。用户提供抖音链接+仿写/改写/借鉴/参考等意图时触发。流程：解析链接→音频转写→读飞书知识库→拆解结构→仿写3条脚本。
version: 1.2.0
metadata:
  requires:
    bins: [ffmpeg,lark-wiki]
  env:
    - SILICONFLOW_API_KEY
    - FEISHU_WIKI_URL
---

## 何时使用（触发条件）

当用户意图为**仿写/模仿/改写/参考已有视频**时触发，典型信号：

- 用户提供了抖音/短视频链接，并要求「仿写」「模仿」「改写」「借鉴」「参考」「照着写」
- 用户说「像这个视频一样写个脚本」「按这个风格来」
- 用户发来链接 + 任何暗示复用结构/风格/节奏的表述
- 用户说「拆解这个视频」「分析这个视频再仿写」


## 完整工作流

### 第1步：解析抖音视频元数据

提取：标题、作品描述、标签、内容形式、高频关键词、评论热点词、账号信息（昵称/粉丝/获赞/类型）、点赞/评论/收藏量。

**操作（按优先级）：**
1. **OpenClaw browser（首选）：** 抖音是纯JS渲染SPA，浏览器是唯一稳定方案。`browser`打开链接→`snapshot`提取信息→`screenshot`截取画面用于第2d步→`act evaluate`提取`<video>.currentSrc`获取视频源地址
2. **Playwright Stealth 脚本（备选）：** 当OpenClaw browser超时或不稳定时，使用`scripts/fetch_video_detail.js`（需在douyin-search目录下运行以复用node_modules）
3. **web_fetch（兜底）：** 通常只能拿空壳，效果有限
4. 短链接（`v.douyin.com/xxx`）浏览器会自动跳转

**⚠️ 浏览器使用注意事项：**
- 抖音页面是重SPA，标签页堆积会导致CDP超时。操作前先检查并清理多余标签页（`browser tabs`查看，关闭非必要页面）
- 每次操作完成后立即关闭标签页，避免残留
- 如果snapshot/evaluate超时，先清理标签页再重试
- 视频源地址需用`act evaluate`从`<video>.currentSrc`获取，snapshot中不包含

**标题与作品描述的区分规则：**

抖音PC网页端将标题和描述合并为一个`<h1>`展示，无法从DOM直接区分。按以下规则推断拆分：

1. **标签提取**：以`#`开头的文本块，单独提取为标签列表
2. **标题推断**：去除标签后，第一个句号`。`或感叹号`！`之前的短句作为标题
3. **描述推断**：标题之后、标签之前的剩余内容作为作品描述
4. **无标点情况**：如果整段无句号/感叹号，字数≤20则整段作为标题，描述为空

示例：
```
原始heading：带大家在线验厂，参观下我们的塑料瓶生产工厂！食品瓶，肉松瓶，糖果瓶，鱼肠瓶，蜂蜜瓶，饮料瓶，果汁瓶，奶茶瓶，化妆品瓶生产厂家/工厂 #工厂实拍视频 #源头实力厂家 #塑料制品 #塑料瓶 #专业生产厂家

→ 标题：带大家在线验厂，参观下我们的塑料瓶生产工厂！
→ 描述：食品瓶，肉松瓶，糖果瓶，鱼肠瓶，蜂蜜瓶，饮料瓶，果汁瓶，奶茶瓶，化妆品瓶生产厂家/工厂
→ 标签：#工厂实拍视频 #源头实力厂家 #塑料制品 #塑料瓶 #专业生产厂家
```
### 第2步：提取音频并转写口播文案

**核心步骤，优先于页面字幕提取。**

#### 2a. 获取视频源地址并下载视频

**获取视频源地址：**
用`browser act evaluate`从页面提取：
```javascript
document.querySelector('video')?.currentSrc || document.querySelector('video')?.src || ''
```

**下载视频：**
```bash
curl -L -o /tmp/douyin_video.mp4 "<视频下载地址>" -H "User-Agent: Mozilla/5.0" -H "Referer: https://www.douyin.com/"
```

**降级方案：**
- curl 403 → 检查视频源URL是否已过期，重新从页面获取
- OpenClaw browser整体不可用 → 使用Playwright Stealth脚本`scripts/fetch_video_detail.js`获取视频源，需在douyin-search目录下运行：
  ```bash
  cd skills/douyin-search && node scripts/fetch_video_detail.js <aweme_id>
  ```
  注意：该脚本依赖`playwright-extra`和`puppeteer-extra-plugin-stealth`，仅在douyin-search目录下有node_modules

#### 2b. 提取音频
```bash
ffmpeg -y -i /tmp/douyin_video.mp4 -acodec pcm_s16le -ar 16000 -ac 1 /tmp/douyin_audio.wav 2>/dev/null
```

#### 2c. 语音转写

```bash
python3 scripts/transcribe.py $SILICONFLOW_API_KEY /tmp/douyin_audio.wav
```
API失败或纯音乐→回退到页面字幕/描述提取。SiliconFlow API偶发500错误，建议重试2-3次（间隔3秒）。

#### 2d. 画面分析
用`browser screenshot`截取画面，提取画面内容（场景/动作）和画面特点（运镜/景别/转场）。

### 第3步：读取飞书知识库企业信息

优先读取`../../wiki-monitor/content/`目录下的文件内容,目录下没文件再使用`lark-wiki`+`lark-doc`读取，
提取：公司名/行业/规模、主推业务/卖点、目标客户/痛点、差异化优势、目标市场、内容方向。

**压缩为≤150字摘要**，用于仿写参考。

### 第4步：拆解原视频结构

逐句拆解，格式：`句N：[原文] → [功能] → [技巧]`

功能：钩子/痛点/共鸣/方案/卖点/信任/引导/CTA
技巧：数字法/对比法/场景法/反问法/共情法/权威法/紧迫法/利益法

### 第5步：仿写3条视频脚本

**仿写要求**

- 严格按原视频句式结构、节奏、功能分布仿写,句数/功能/节奏一致
- 每句「功能」和「技巧」与原视频一致
- 内容替换为企业产品/卖点/场景/客户/数据
- 融入企业核心卖点和差异化优势
- 仿写后必须通顺,拗口/生硬必须调整，宁可多一字不可卡一秒
- 标签：围绕品牌+产品+行业+人群+热点关键词
- 目标用户：文案针对客户人群，注意人称
- 每条脚本选不同角度，参考`references/script-angles.md`选3个。

**仿写前按原视频风格只读1个示例文件,也作为仿写的参考：**
- 大字报（口播展示卖点）→ `references/imitation-example-oral.md`
- 危机+方案（事故→解决方案）→ `references/imitation-example-crisis.md`
- 工厂探店/Vlog（边走边讲）→ `references/imitation-example-vlog.md`

### 第6步：输出结果

输出格式见`references/output-format.md`

- 内容输出给用户看后保存文件
