# UI设计规范 — 知我实验室·依恋报告

适用范围：H5问卷页、报告PDF、服务号内所有页面

---

## 品牌基调

**一句话定位：** 克制的温柔，带有学术感的亲密。

不是心理咨询机构的冷静专业，也不是小红书美妆博主的粉嫩可爱。
知我实验室的调性是：**懂你，但不滥情**。

类比参考：《存在主义咖啡馆》的封面，或一本设计好的心理学科普书。

---

## 色彩系统

### 核心色板

```css
:root {
  /* 主色 — 暖紫，品牌识别色 */
  --color-primary: #7C5CBF;
  --color-primary-light: #9B7FD4;
  --color-primary-dark: #5E3FA3;
  --color-primary-surface: #F0EBFA;  /* 浅紫底色，用于卡片背景 */

  /* 中性色 */
  --color-ink: #1A1A2E;          /* 主文字，近黑带蓝调 */
  --color-ink-secondary: #4A4A6A; /* 次要文字 */
  --color-ink-tertiary: #8A8AAA;  /* 辅助文字、标注 */
  --color-border: #E8E4F0;        /* 分割线、边框 */
  --color-surface: #FAFAF8;       /* 页面背景，暖白 */
  --color-surface-raised: #FFFFFF; /* 卡片、浮层背景 */

  /* 功能色 */
  --color-success: #4CAF87;
  --color-warning: #E8A838;
  --color-error: #D4544A;
}
```

### 四种依恋类型的专属色

每种类型有自己的主题色，用于报告封面、类型标签和坐标轴高亮点：

```css
--color-type-secure:   #4CAF87;  /* 绿，稳定 */
--color-type-anxious:  #E8A838;  /* 琥珀，热切 */
--color-type-avoidant: #5B8FC9;  /* 蓝，疏离 */
--color-type-fearful:  #9B6B9E;  /* 深紫，复杂 */
```

### 使用规则

- 主文字永远用 `--color-ink`，不用纯黑 #000000
- 背景不用纯白 #FFFFFF，用 `--color-surface`（暖白）
- 强调色（primary）不用于大面积背景，只用于按钮、标签、关键词高亮
- 禁止使用渐变色作为按钮背景（太俗气）

---

## 字体系统

### 字体选择

```css
/* 标题字体 — 衬线，有质感 */
font-family-display: 'Noto Serif SC', 'Source Han Serif SC', serif;

/* 正文字体 — 无衬线，易读 */
font-family-body: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
```

**为什么用衬线标题：** 心理学内容需要一点"书卷气"，衬线字体有这种气质，同时和无衬线正文形成层次对比。

### 字号比例（H5页面，基础单位rem）

```css
--text-xs:   0.75rem;   /* 12px — 版权、极小注释 */
--text-sm:   0.875rem;  /* 14px — 辅助说明、标注 */
--text-base: 1rem;      /* 16px — 正文 */
--text-lg:   1.125rem;  /* 18px — 小标题、强调段落 */
--text-xl:   1.25rem;   /* 20px — 次级标题 */
--text-2xl:  1.5rem;    /* 24px — 区块标题 */
--text-3xl:  1.875rem;  /* 30px — 页面主标题 */
```

### 行高

```css
--leading-tight:  1.4;  /* 标题 */
--leading-normal: 1.7;  /* 正文（中文正文用1.7以上，比英文宽松）*/
--leading-loose:  2.0;  /* 需要呼吸感的段落 */
```

---

## 间距系统

使用8px基础网格：

```css
--space-1:  4px;
--space-2:  8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  20px;
--space-6:  24px;
--space-8:  32px;
--space-10: 40px;
--space-12: 48px;
--space-16: 64px;
```

### H5页面内容区宽度

```css
max-width: 390px;     /* 适配iPhone主流尺寸 */
padding: 0 20px;      /* 左右内边距 */
```

---

## 组件规范

### 按钮

**主按钮（提交、下一题）**
```css
background: var(--color-primary);
color: #FFFFFF;
border-radius: 12px;
padding: 14px 24px;
font-size: var(--text-base);
font-weight: 600;
width: 100%;           /* 全宽，移动端更易点击 */
min-height: 52px;      /* 最小点击高度 */
border: none;
/* 按下状态 */
active: { background: var(--color-primary-dark); transform: scale(0.98); }
```

**次级按钮（上一题、跳过）**
```css
background: transparent;
color: var(--color-ink-secondary);
border: 1px solid var(--color-border);
border-radius: 12px;
/* 其他同主按钮 */
```

禁止：
- 圆形按钮（不符合品牌调性）
- 渐变背景按钮
- 文字按钮（链接式）出现在主操作区

### 问卷选项（7级Likert量表）

7个选项横向排列，每个是一个可点击的圆形区域：

```
完全不符合  1  2  3  4  5  6  7  完全符合
```

选中状态：圆圈填充 `--color-primary`，文字变白
未选中状态：圆圈边框 `--color-border`，背景白

圆圈尺寸：36px × 36px（确保可点击）
圆圈间距：均等分布，不要固定间距

### 进度条

```
问题 3 / 12
████████░░░░░░░░░░░░  (已完成3/12)
```

- 进度条高度：4px
- 已完成色：`--color-primary`
- 未完成色：`--color-border`
- 圆角：2px
- 文字：`问题 X / 12`，右对齐，`--text-sm`，`--color-ink-tertiary`

### 卡片

```css
background: var(--color-surface-raised);
border-radius: 16px;
padding: var(--space-6);
box-shadow: 0 2px 12px rgba(124, 92, 191, 0.06);  /* 主色调的极淡投影 */
border: 1px solid var(--color-border);
```

禁止：
- 卡片叠加多重投影
- 卡片内再嵌套卡片

---

## H5问卷页面结构

### 页面流程

```
欢迎页 → 基本信息页 → 题目页（12页，每页1题）→ 提交中 → 完成页
```

### 欢迎页

- 知我实验室Logo（顶部居中）
- 标题：「了解你的依恋类型」（Noto Serif SC，--text-3xl）
- 副标题：「12道题，5分钟，看见你在感情里的真实模式」（--text-base，--color-ink-secondary）
- 说明文字：隐私说明（不收集敏感信息，仅用于生成报告）
- 主按钮：「开始测试」

### 基本信息页

- 昵称输入框（选填，placeholder：「给报告起个专属称呼，比如"小月"」）
- 联系方式输入框（必填，placeholder：「邮箱或微信号，用于接收报告」）
- 联系方式类型自动判断：包含@判断为邮箱，否则为微信号
- 主按钮：「继续」

### 题目页

- 顶部：进度条 + 题号
- 题目文字：Noto Serif SC，--text-xl，--leading-tight，居中
- 7级量表选项（见组件规范）
- 量表两端标签：「完全不符合」「完全符合」，--text-xs，--color-ink-tertiary
- 选中后自动进入下一题（不需要点"下一题"按钮）
- 底部："上一题"文字按钮（--color-ink-tertiary）

### 提交中页

- 不要用spinner（太普通）
- 用一句话：「正在生成你的依恋报告，通常需要30秒左右」
- 下方放知我实验室的一句话品牌语（如「了解自己，是一切关系的起点」）

### 完成页

- 标题：「报告已发送」
- 说明：「请查收你的[邮箱/微信]，报告链接7天内有效」
- 小字：「如果5分钟内未收到，请检查垃圾邮件箱」
- 不放任何引流链接（这一步用户已经完成，不要再让他们做其他事）

---

## PDF报告视觉规范

### 页面设置

```
纸张：A4（210mm × 297mm）
边距：上下 20mm，左右 18mm
内容宽度：174mm
```

### 字体（PDF内嵌）

- 标题：Noto Serif SC Bold
- 正文：Noto Sans SC Regular
- 注释：Noto Sans SC Light

必须将字体文件内嵌到PDF中，不依赖系统字体。

### 封面（第1页）

布局从上到下：
1. 知我实验室 Logo + 文字（顶部，较小）
2. 空白留白（约40mm）
3. 类型色的大圆形色块（直径约60mm，居中）
4. 类型名称（如「焦虑型」），Noto Serif SC，28pt，类型主题色
5. 副标题：「依恋类型深度解读报告」，16pt，--color-ink-secondary
6. 用户昵称 + 生成日期（底部）

### 内页标题层级（PDF）

```
H1（章节标题）: Noto Serif SC Bold, 18pt, --color-ink
H2（小节标题）: Noto Sans SC Bold, 14pt, --color-primary
H3（模式标题）: Noto Sans SC Bold, 12pt, --color-ink
正文:            Noto Sans SC Regular, 11pt, --color-ink，行高1.8
注释/说明:       Noto Sans SC Light, 9pt, --color-ink-tertiary
```

### 坐标轴图（第2页）

用SVG内嵌到HTML，然后由WeasyPrint渲染：

- 横轴：回避维度（低→高，左→右）
- 纵轴：焦虑维度（低→高，下→上）
- 四象限用四种类型色填充（极淡，透明度10%）
- 四象限标签：安全型/焦虑型/回避型/恐惧型（--text-sm，对应类型色）
- 用户位置：实心圆点（直径8px，类型主题色），带微弱光晕效果
- 轴刻度：1-7

### 内页分隔

每个大章节之间用一条细线分隔：
```css
border-top: 1px solid var(--color-border);
margin: 24pt 0;
```

### 水印

每页底部居中，极淡灰色：
```
知我实验室出品 · [生成日期] · 仅供[昵称]个人参考
```
字号：8pt，颜色：--color-ink-tertiary

---

## 禁止清单

以下设计模式禁止出现在任何页面：

- 紫色渐变背景（太常见，丧失品牌辨识度）
- 卡通插画或emoji作为主要视觉元素
- 超过3种字体
- 红色用于非错误状态
- 表单输入框带有彩色边框
- 按钮带有阴影效果（flat design）
- 加载中用旋转圆圈spinner
- 弹窗（modal）用于提示信息（用内联提示替代）
