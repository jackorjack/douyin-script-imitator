---
name: douyin-script-imitator
description: 抖音短视频脚本仿写技能。当用户提供抖音视频链接/分享文本，要求仿写、改写、借鉴、参考该视频写脚本时触发。核心流程：解析抖音视频→提取视频音频转写文案→读取飞书知识库企业信息→逐句拆解原视频结构→按原结构仿写5条脚本。适用于短视频创作者、自媒体运营、企业短视频营销场景。
metadata:
  requires:
    bins:
      - ffmpeg
      - python3
      - curl
    params:
      - groqApiKey       # Groq API密钥（必填），也可通过环境变量 GROQ_API_KEY 或对话中提供
      - feishuWikiUrl    # 飞书知识库链接（可选），也可通过环境变量 FEISHU_WIKI_URL 或对话中提供
---

# 抖音短视频脚本仿写

## 触发条件

用户提供抖音视频链接或分享文本，并要求：
- 仿写/改写/借鉴/参考视频写脚本
- 按某视频风格出脚本
- 视频脚本拆解后仿写

## 前置依赖

### 参数配置（三选一，任一可用即可）

本技能需要两个外部参数。支持三种配置方式，**按优先级自动回退**——任何一层有值即可运行：

| 参数 | 用途 | 获取方式 |
|------|------|----------|
| groqApiKey | Groq Whisper API 语音转写 | https://console.groq.com 注册获取 |
| feishuWikiUrl | 飞书知识库链接（可选） | 飞书知识库页面URL |

**获取优先级（从高到低）：**

| 优先级 | 方式 | 适用场景 | 示例 |
|--------|------|----------|------|
| 🥇 最高 | 用户对话中当场指定 | 临时使用、测试、一次性任务 | 「用这个key: gsk_xxx」「知识库链接是 https://xxx」 |
| 🥈 次高 | 智能体 params 配置 | 长期使用、团队共享 | 见下方配置方法 |
| 🥉 最低 | 系统环境变量 | 历史兼容、CI/CD 场景 | `export GROQ_API_KEY=gsk_xxx` |

#### 方式一：对话中直接提供（零配置）

无需任何配置，运行时告诉智能体即可：
```
帮我仿写这个视频，API key 用 gsk_xxx，知识库链接是 https://xxx.feishu.cn/wiki/xxx
```

#### 方式二：智能体 params 配置（推荐长期使用）

在 `openclaw.json` 的 `agents.list` 中，给**需要此技能的智能体**添加 `params`：

```json
{
  "id": "your-agent-id",
  "params": {
    "groqApiKey": "gsk_xxxxxxxxxxxx",
    "feishuWikiUrl": "https://xxx.feishu.cn/wiki/xxxxxx"
  }
}
```

> 💡 **多智能体共用：** 每个智能体各自配自己的 params，技能自动读取当前运行智能体的配置。同一个技能可以在 QClaw、Claude Code、Hermes 等任何智能体上使用，互不干扰。

#### 方式三：系统环境变量（兼容旧配置）

```bash
# macOS/Linux: 写入 ~/.zshrc 或 ~/.bashrc
export GROQ_API_KEY="gsk_xxxxxxxxxxxx"
export FEISHU_WIKI_URL="https://xxx.feishu.cn/wiki/xxxxxx"

# Windows: 写入系统环境变量或 PowerShell 配置文件
$env:GROQ_API_KEY = "gsk_xxxxxxxxxxxx"
$env:FEISHU_WIKI_URL = "https://xxx.feishu.cn/wiki/xxxxxx"
```

> ⚠️ 环境变量方式优先级最低，可能被其他配置覆盖。推荐使用方式一或方式二。

### 命令行工具安装

#### ffmpeg（音视频提取转换）

| 操作系统 | 安装命令 |
|----------|----------|
| macOS (Homebrew) | `brew install ffmpeg` |
| macOS (MacPorts) | `sudo port install ffmpeg` |
| Ubuntu/Debian | `sudo apt update && sudo apt install ffmpeg` |
| CentOS/RHEL | `sudo yum install epel-release && sudo yum install ffmpeg` |
| Windows (Scoop) | `scoop install ffmpeg` |
| Windows (Chocolatey) | `choco install ffmpeg` |
| Windows (Winget) | `winget install Gyan.FFmpeg` |

#### Python 3 + pip

| 操作系统 | 安装命令 |
|----------|----------|
| macOS (Homebrew) | `brew install python3` |
| Ubuntu/Debian | `sudo apt update && sudo apt install python3 python3-pip` |
| CentOS/RHEL | `sudo yum install python3 python3-pip` |
| Windows (Scoop) | `scoop install python` |
| Windows (Chocolatey) | `choco install python` |
| Windows (Winget) | `winget install Python.Python.3` |

#### curl（通常系统自带）

| 操作系统 | 安装命令 |
|----------|----------|
| macOS | 系统自带，无需安装 |
| Ubuntu/Debian | `sudo apt install curl` |
| CentOS/RHEL | `sudo yum install curl` |
| Windows | Windows 10+ 自带；旧版下载 https://curl.se/windows/ |

### Python 依赖

转写脚本 `scripts/transcribe.py` 需要以下 Python 包：

```bash
pip3 install requests
```

> 注意：`requests` 是唯一外部依赖，Python 标准库的 `json`、`sys`、`os` 无需安装。

## 完整工作流

### 第1步：解析抖音视频元数据

提取视频的元信息（不含口播文案，口播文案在第2步获取）：

| 提取项 | 说明 |
|--------|------|
| 视频标题 | 视频文案标题 |
| 标签 | #话题标签 |
| 内容形式 | 口播/剧情/测评/教程/Vlog/产品展示等 |
| 高频关键词 | 文案/标题中重复出现的核心词 |
| 评论热点词 | 高赞评论中的关键词和用户关注点 |
| 账号信息 | 昵称、粉丝数、获赞数、简介、账号类型 |

**操作方式（按优先级尝试）：**

1. **curl SSR 提取（首选）：** 抖音 SSR 页面在 HTML 中内嵌 `window._ROUTER_DATA` JSON，包含视频标题、描述、标签、作者、统计数据等全部元信息。命令：
   ```bash
   curl -s -L -H "User-Agent: Mozilla/5.0" "<抖音链接>" | python3 -c "
   import sys, json, re
   html = sys.stdin.read()
   m = re.search(r'window\._ROUTER_DATA\s*=\s*({.*?})\s*</script>', html)
   if m:
       data = json.loads(m.group(1))
       # 遍历找到包含 awemeDetail 的 key
       for k,v in data.items():
           if isinstance(v, dict) and 'awemeDetail' in v:
               detail = v['awemeDetail']
               print(f"标题: {detail.get('desc','')}")
               print(f"作者: {detail.get('author',{}).get('nickname','')}")
               print(f"标签: {' '.join(['#'+t.get('name','') for t in detail.get('textExtra',[]) if t.get('name')])}")
               print(f"点赞: {detail.get('statistics',{}).get('diggCount','')}")
               print(f"评论: {detail.get('statistics',{}).get('commentCount','')}")
               print(f"分享: {detail.get('statistics',{}).get('shareCount','')}")
               # 提取视频下载地址
               play_url = detail.get('video',{}).get('play_addr',{}).get('url_list',[''])[0]
               if play_url:
                   print(f"视频地址: {play_url}")
               break
   "
   ```

2. **浏览器方式（备选）：** 用 `browser` 工具打开抖音链接，`snapshot` 获取页面内容。

3. **web_fetch 方式（备选）：** 用 `web_fetch` 抓取 iesdouyin.com 分享页面提取信息。

**抖音分享链接处理：** 用户可能提供短链接（如 `v.douyin.com/xxx`）或完整链接。短链接会重定向，浏览器/curl 自动跳转即可。

### 第2步：提取视频音频并转写口播文案

**这是获取口播文案的核心步骤，优先于从页面字幕提取。**

#### 2a. 下载视频

从第1步获取的视频下载地址，用 curl 下载视频文件：
```bash
curl -L -o /tmp/douyin_video.mp4 "<视频下载地址>" -H "User-Agent: Mozilla/5.0" -H "Referer: https://www.douyin.com/"
```

如果 curl 下载失败（403），尝试从 SSR 数据中的 `play_addr.url_list` 获取备用地址。

#### 2b. 提取音频

使用 ffmpeg 提取音频为 WAV 格式（16kHz 单声道，Groq API 推荐格式）：
```bash
ffmpeg -y -i /tmp/douyin_video.mp4 -acodec pcm_s16le -ar 16000 -ac 1 /tmp/douyin_audio.wav 2>/dev/null
```

#### 2c. Groq Whisper API 转写

使用本技能内置的转写脚本，调用 Groq Whisper large-v3 模型进行语音转文字。

**API Key 获取方式（三层回退）：**
1. 用户对话中直接提供了 key → 直接使用
2. 智能体 params 中配置了 `groqApiKey` → 读取 params
3. 系统环境变量 `GROQ_API_KEY` → 读取环境变量

```bash
GROQ_API_KEY="<按上述优先级获取>" python3 scripts/transcribe.py /tmp/douyin_audio.wav
```

> 💡 三层回退设计确保技能在任何智能体（QClaw / Claude Code / Hermes 等）上都能运行，无需逐个配环境。

**输出：** 视频的完整口播文案（纯文本）。

**优势：**
- 云端转写，无需下载本地模型（省几百MB空间）
- whisper-large-v3 模型，中文识别准确率高
- 秒级响应，1分钟以内音频通常 <2秒 出结果
- 自动处理音频格式（ffmpeg 可选）

**注意：** 如果转写失败或音频为纯音乐无语音，则回退到从页面字幕/描述中提取文案。

#### 2d. 画面内容分析

通过浏览器截图或人工描述获取画面信息：

| 提取项 | 说明 |
|--------|------|
| 视频内容 | 画面描述、场景、动作 |
| 画面特点 | 运镜、景别、转场、特效等视觉特征 |

**操作：** 用 `browser screenshot` 截取视频画面，或根据视频类型推断画面脚本。

### 第3步：读取飞书知识库企业信息

使用 `feishu_wiki` + `feishu_doc` 读取企业知识库，提取：

| 提取项 | 说明 |
|--------|------|
| 企业基础信息 | 公司名、行业、规模、成立时间 |
| 主推业务 | 产品/服务名称、核心卖点 |
| 目标客户 | 行业+身份角色+痛点 |
| 企业优势 | 差异化竞争力 |
| 目标市场 | 区域/渠道 |
| 内容方向 | 短期目标、转化路径 |

**知识库链接获取优先级（三层回退）：**
1. 🥇 用户本次对话中明确指定了知识库链接 → 使用用户指定的链接
2. 🥈 智能体 params 中配置了 `feishuWikiUrl` → 读取 params
3. 🥉 系统环境变量 `FEISHU_WIKI_URL` → 读取环境变量
4. 以上都没有 → 提示用户提供知识库链接，或告知可跳过此步（飞书知识库为可选功能）

> 💡 **feishuWikiUrl 为可选参数**：如果用户只是仿写脚本但不需要融入企业信息，可跳过第3步直接进入拆解仿写。

**总结输出：** 将企业信息压缩为一段200字以内的核心摘要，用于后续仿写参考。

### 第4步：逐句拆解原视频结构

对原视频文案进行逐句结构拆解，格式如下：

```
句1：[原文] → [功能] → [技巧]
句2：[原文] → [功能] → [技巧]
...
```

**功能类型：** 钩子/痛点/共鸣/方案/卖点/信任/引导/CTA
**技巧标签：** 数字法/对比法/场景法/反问法/共情法/权威法/紧迫法/利益法

### 第5步：仿写5条视频脚本

**核心原则：结构不变，内容替换**

- 严格按原视频的句式结构、节奏、功能分布进行仿写
- 每句的「功能」和「技巧」与原视频一致
- 内容替换为企业自身的产品、卖点、场景、客户
- 融入企业信息中的核心卖点和差异化优势
- 保持原视频的语气节奏（如开头3秒钩子→痛点→方案→CTA）

每条脚本需有差异化角度，参考 `references/script-angles.md` 选择5个不同角度。

**仿写核心原则：**

1. **保留句式骨架，替换行业/产品/数据**
2. **仿写后必须通顺自然**：替换后的语句要保证口语流畅，拗口、生硬、不符合中文表达习惯的词句必须调整
   - 例："传统厂" → "传统工厂" 或 "传统大厂"（多一个字但顺嘴）
   - 例："在一屋做包装盒" → "在义乌做包装盒"（地名要准确）
   - 原则：**宁可多一字，不可卡一秒**

**仿写前先判断原视频风格，选择对应示例模板：**

| 原视频风格 | 特征 | 选择示例 |
|------------|------|----------|
| 口播+产品展示 | 主播手持产品边说边展示 | 示例一 |
| 危机+方案 | 先讲事故/危险场景，再引出解决方案 | 示例二 |
| 工厂探店/Vlog | 带观众参观工厂，边走边讲 | 示例三 |

详细示例及逐句拆解见 `references/imitation-example.md`，仿写前必读。选择与原视频风格匹配的示例作为仿写模板。

### 第6步：输出完整结果

输出格式见 `references/output-format.md`，包含：
1. 原视频完整信息 + 链接
2. 原视频口播文案（来自 Groq Whisper 转写）
3. 企业信息摘要
4. 原视频逐句结构拆解
5. 5条仿写脚本（每条含口播文案+画面脚本+字幕）

## 关键约束

- **不改变原视频结构**：仿写是"换皮不换骨"，句数、功能、节奏一致
- **不编造企业信息**：所有产品/卖点/数据必须来自飞书知识库原文
- **5条脚本必须角度不同**：避免5条脚本雷同
- **仿写后必须通顺**：替换内容后逐句朗读检查，拗口/生硬/不通顺的必须调整，宁可多一字不可卡一秒
- **输出格式美观**：使用表格+分段+emoji，清晰易读
- **口播文案要口语化**：短视频脚本不是写文章，要说人话
- **口播文案优先语音转写**：通过 Groq Whisper API 获取的口播文案比页面字幕更完整准确
- **只输出不保存**：脚本生成后直接输出到对话，不自动写文件。是否保存、保存路径由用户确认后再操作

## 文件结构

```
douyin-script-imitator/
├── SKILL.md                          # 技能主文件（本文件）
├── scripts/
│   └── transcribe.py                 # Groq Whisper 语音转写脚本
└── references/
    ├── script-angles.md              # 仿写角度参考
    ├── imitation-example.md          # 仿写示例对照（仿写前必读）
    └── output-format.md              # 输出格式规范
```
