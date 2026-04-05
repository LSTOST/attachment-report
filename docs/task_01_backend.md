# Task 01 — 后端核心链路

## 任务目标

搭建依恋类型报告的完整后端交付链路：
接收问卷提交 → 计算分型 → 生成PDF → 上传OSS → 发送下载链接给用户

完成后，用户从提交问卷到收到PDF链接的全程不超过60秒，无需人工介入。

---

## 技术栈

- 运行时：Python 3.11+
- Web框架：FastAPI
- PDF生成：WeasyPrint
- 对象存储：阿里云OSS（aliyun-oss2）
- 邮件发送：SMTP（smtplib，标准库）
- 部署：Railway（提供Dockerfile）
- 环境变量管理：python-dotenv

---

## 项目结构

按以下结构创建文件，不要偏离：

```
attachment-report/
├── main.py
├── classifier.py
├── report_builder.py
├── pdf_generator.py
├── storage.py
├── notifier.py
├── models.py
├── config.py
├── content/
│   ├── anxious/
│   │   ├── overview.md
│   │   ├── patterns.md
│   │   ├── conflicts.md
│   │   ├── compatibility.md
│   │   └── exercises.md
│   ├── avoidant/   （同上结构）
│   ├── secure/     （同上结构）
│   └── fearful/    （同上结构）
├── templates/
│   └── report.html
├── static/
│   └── fonts/      （放中文字体文件）
├── tests/
│   └── test_classifier.py
├── Dockerfile
├── railway.toml
├── requirements.txt
└── .env.example
```

---

## 各模块实现规格

### config.py

用 pydantic-settings 管理环境变量，所有配置从环境变量读取，不硬编码：

```python
OSS_ACCESS_KEY_ID: str
OSS_ACCESS_KEY_SECRET: str
OSS_BUCKET_NAME: str
OSS_ENDPOINT: str
OSS_URL_EXPIRY_SECONDS: int = 604800  # 7天
SMTP_HOST: str
SMTP_PORT: int = 465
SMTP_USER: str
SMTP_PASSWORD: str
TALLY_WEBHOOK_SECRET: str  # 用于验证Webhook来源
APP_ENV: str = "development"
```

### models.py

定义两个Pydantic模型：

```python
class TallyWebhookPayload  # Tally发来的原始数据结构
class QuizAnswers           # 解析后的答题数据
    nickname: str
    contact: str            # 邮箱或微信号
    contact_type: str       # "email" | "wechat"
    answers: dict[str, int] # {"A1": 5, "A2": 3, ...}
```

### classifier.py

实现分型算法：

- 输入：QuizAnswers.answers（12个键值对，键为A1-A6和B1-B6，值为1-7的整数）
- 计算焦虑分 = A1到A6的均值，回避分 = B1到B6的均值
- 阈值3.5划分四象限：
  - 焦虑<3.5 且 回避<3.5 → SECURE
  - 焦虑≥3.5 且 回避<3.5 → ANXIOUS
  - 焦虑<3.5 且 回避≥3.5 → AVOIDANT
  - 焦虑≥3.5 且 回避≥3.5 → FEARFUL
- 输出：TypeCode（str）、anxiety_score（float，保留2位小数）、avoidance_score（float，保留2位小数）
- 必须写单元测试，覆盖四个象限的边界情况和极值

### report_builder.py

从content/目录读取markdown文件，组装报告所需的数据结构：

- 根据TypeCode读取对应类型下的5个md文件
- 将md内容转为HTML（使用markdown库）
- 返回ReportData对象，包含：type_code、type_name_cn、anxiety_score、avoidance_score、nickname、sections（dict，键为文件名，值为HTML字符串）

type_name_cn映射：
- SECURE → 安全型
- ANXIOUS → 焦虑型
- AVOIDANT → 回避型
- FEARFUL → 恐惧型

### pdf_generator.py

使用WeasyPrint将HTML模板渲染为PDF bytes：

- 接收ReportData对象
- 使用Jinja2渲染templates/report.html
- 字体：Noto Sans SC（从static/fonts/加载，不依赖系统字体）
- 返回bytes
- 注意：WeasyPrint在Railway上需要安装系统依赖（pango、cairo等），在Dockerfile中处理

### storage.py

上传PDF到阿里云OSS：

- 文件名格式：reports/{YYYYMMDD}/{response_id}.pdf
- 上传完成后生成带签名的临时下载链接（7天有效）
- 返回带签名的URL字符串

### notifier.py

发送报告链接给用户：

- 如果contact_type == "email"：发送HTML邮件，包含下载链接和有效期说明
- 如果contact_type == "wechat"：写入日志（暂时不实现自动发送，人工处理）
- 邮件模板要简洁，不要花哨，包含：称呼、链接、有效期、知我实验室署名

### main.py

FastAPI应用，一个端点：

```
POST /webhook/tally
```

处理流程：
1. 验证Webhook签名（从header取Tally-Signature，与TALLY_WEBHOOK_SECRET比对）
2. 解析payload，提取答题数据
3. 立刻返回HTTP 200（不要让Webhook等待后续处理）
4. 用BackgroundTasks异步执行：classifier → report_builder → pdf_generator → storage → notifier
5. 任何步骤失败：记录完整错误日志，不抛出500（不能影响Webhook响应）

另外提供：
```
GET /health
```
返回 {"status": "ok"}，用于Railway健康检查。

---

## Dockerfile

基础镜像：python:3.11-slim

需要安装的系统依赖（WeasyPrint需要）：
libpango-1.0-0、libpangocairo-1.0-0、libgdk-pixbuf2.0-0、libffi-dev、shared-mime-info、libcairo2

步骤：安装系统依赖 → 复制requirements.txt → pip install → 复制项目文件 → 设置启动命令

启动命令：uvicorn main:app --host 0.0.0.0 --port $PORT

---

## railway.toml

```toml
[build]
builder = "DOCKERFILE"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
```

---

## .env.example

列出所有需要的环境变量（值填写说明，不填真实值）：

```
OSS_ACCESS_KEY_ID=your_aliyun_access_key_id
OSS_ACCESS_KEY_SECRET=your_aliyun_access_key_secret
OSS_BUCKET_NAME=your_bucket_name
OSS_ENDPOINT=https://oss-cn-hangzhou.aliyuncs.com
SMTP_HOST=smtp.example.com
SMTP_USER=noreply@example.com
SMTP_PASSWORD=your_smtp_password
TALLY_WEBHOOK_SECRET=your_webhook_secret
APP_ENV=development
```

---

## 完成标准

以下所有条件满足，Task 01才算完成：

- [ ] `pytest tests/` 全部通过，classifier四个象限和边界情况均有测试
- [ ] 本地运行后，手动POST一个模拟Tally Webhook，60秒内能收到邮件或看到日志输出
- [ ] PDF能正常生成，中文不乱码，字体加载正常
- [ ] OSS上传成功，签名链接可以在浏览器直接下载PDF
- [ ] Railway部署成功，/health 返回200
- [ ] 没有任何硬编码的密钥或路径

---

## 不在这个Task里做的事

- 微信服务号集成（Task 02）
- 问卷H5页面（Task 03）
- PDF的视觉设计（report.html暂时用简单占位模板，能渲染中文内容即可）
- 管理后台
- 数据库（这个阶段不需要）
