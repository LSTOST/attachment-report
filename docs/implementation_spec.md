# 实现规范 — 依恋报告产品

适用范围：所有后端代码、API设计、测试、部署

---

## API契约

### POST /webhook/tally

**请求头**
```
Content-Type: application/json
Tally-Signature: sha256={hmac签名}
```

**请求体（Tally标准格式）**
```json
{
  "eventId": "string",
  "eventType": "FORM_RESPONSE",
  "createdAt": "ISO8601",
  "data": {
    "responseId": "string",
    "formId": "string",
    "fields": [
      {"key": "nickname", "label": "昵称", "value": "小月"},
      {"key": "contact", "label": "联系方式", "value": "user@example.com"},
      {"key": "A1", "label": "题目A1", "value": "5"},
      {"key": "A2", "label": "题目A2", "value": "3"},
      ...共14个字段
    ]
  }
}
```

**响应（立刻返回，不等待PDF生成）**
```json
HTTP 200
{"status": "received", "responseId": "string"}
```

**错误响应**
```json
HTTP 400  {"error": "invalid_signature"}
HTTP 422  {"error": "missing_required_fields", "fields": ["A1", "A2"]}
HTTP 500  {"error": "internal_error"}  ← 这个不应该出现，所有错误都要被捕获
```

### GET /health

```json
HTTP 200
{"status": "ok", "version": "1.0.0"}
```

---

## 数据流规范

### 字段解析规则

从Tally的fields数组提取数据时：

1. nickname：找key=="nickname"的field，取value，strip空格，如果为空则用"你"作为默认值
2. contact：找key=="contact"的field，取value，strip空格，不能为空
3. contact_type：如果contact包含"@"则为"email"，否则为"wechat"
4. answers：遍历fields，找所有key匹配正则`^[AB]\d$`的field，value转int

### 数据验证规则

必须在解析后验证：
- answers必须包含完整的12个键（A1-A6, B1-B6）
- 每个answer的值必须在1-7之间（包含）
- contact不能为空字符串
- 验证失败时返回HTTP 422，日志记录具体缺失字段

### responseId的使用

responseId从Tally payload里取，全程作为这条记录的唯一标识：
- 用于OSS文件命名：`reports/{YYYYMMDD}/{responseId}.pdf`
- 用于日志追踪：每条日志必须包含responseId
- 不存入数据库（这个阶段）

---

## 错误处理规范

### 分级处理

**级别1：可恢复错误（重试）**
- OSS上传超时：最多重试3次，间隔5/10/20秒
- SMTP发送失败：最多重试2次，间隔10/30秒

**级别2：不可恢复错误（记录，人工处理）**
- 内容库文件不存在（content/路径下找不到md文件）
- PDF生成失败（WeasyPrint异常）
- 所有重试耗尽后仍失败

**级别3：拒绝处理**
- Webhook签名验证失败 → HTTP 400，不进入业务流程
- 缺少必要字段 → HTTP 422，不进入业务流程

### 日志格式

统一格式，每条日志必须包含：
```
{timestamp} {level} [{responseId}] {module}: {message}
```

示例：
```
2024-01-15 14:23:01 INFO  [resp_abc123] classifier: type=ANXIOUS anxiety=4.83 avoidance=2.17
2024-01-15 14:23:02 INFO  [resp_abc123] storage: uploaded to reports/20240115/resp_abc123.pdf
2024-01-15 14:23:03 ERROR [resp_abc123] notifier: smtp failed attempt 1/2, retrying in 10s
```

不允许出现在日志里的内容：
- 用户的完整联系方式（邮箱只记录@后半部分，如@gmail.com）
- OSS密钥
- SMTP密码

---

## 测试规范

### 必须有测试的模块

**classifier.py** — 单元测试，覆盖：
- 四个象限的典型值（各一个）
- 边界值（anxiety=3.5和avoidance=3.5的组合）
- 极值（全1和全7）
- 输入缺少字段时抛出正确异常

**report_builder.py** — 集成测试：
- 四种type_code能成功读取内容文件并返回完整ReportData
- 找不到内容文件时抛出正确异常并有可读的错误信息

**main.py** — API测试（用FastAPI的TestClient）：
- 正确签名 + 完整payload → 返回200
- 错误签名 → 返回400
- 缺少必要字段 → 返回422

### 测试运行

```bash
pytest tests/ -v
```

所有测试必须能在没有真实OSS/SMTP凭证的情况下运行（mock外部服务）。

---

## 内容库规范

### 文件编码

所有content/下的.md文件：
- 编码：UTF-8（无BOM）
- 换行符：LF（不是CRLF）
- 文件末尾有且仅有一个换行符

### Markdown规范

内容文件里允许使用的Markdown语法：
- `##` 二级标题（不用一级，一级标题在模板里定义）
- `###` 三级标题
- `**粗体**`
- 普通段落（空行分隔）
- `---` 水平线（用于模式之间的分隔，仅patterns.md）

禁止使用：
- 表格（WeasyPrint对复杂表格支持差）
- 代码块
- 图片引用（图片由模板处理，不在内容文件里）
- HTML标签（内容文件必须是纯Markdown）

### 内容长度参考

| 文件 | 建议字数（中文） |
|------|----------------|
| overview.md | 400-600字 |
| patterns.md | 600-800字（5个模式，每个100-150字）|
| conflicts.md | 400-500字 |
| compatibility.md | 300-400字 |
| exercises.md | 600-800字（3个练习，每个150-200字）|

超出1.5倍的内容会导致PDF页面溢出，需要裁剪。

---

## 部署规范

### 环境

- 生产环境：Railway
- 本地开发：直接运行 `uvicorn main:app --reload`
- 没有staging环境（团队规模不需要）

### 部署流程

```
git push main → Railway自动检测Dockerfile → 构建镜像 → 健康检查通过 → 上线
```

Railway的环境变量在Railway控制台手动配置，不通过代码仓库传递。

### 关键部署检查

每次部署后验证：
1. GET /health 返回200
2. 查看Railway日志，确认无启动错误
3. 用测试Webhook（Tally提供的"Test Submission"功能）触发一次完整流程

### 中文字体部署

Noto Sans SC和Noto Serif SC字体文件放在static/fonts/目录下，通过Dockerfile的COPY指令复制到镜像内。

字体文件命名：
```
static/fonts/NotoSansSC-Regular.otf
static/fonts/NotoSansSC-Bold.otf
static/fonts/NotoSerifSC-Regular.otf
static/fonts/NotoSerifSC-Bold.otf
```

字体文件不上传到代码仓库（.gitignore里加上），单独管理（太大），Dockerfile里从可靠来源下载：
```dockerfile
RUN wget -q https://github.com/notofonts/noto-cjk/releases/download/.../NotoSansSC.zip \
    && unzip NotoSansSC.zip -d static/fonts/ \
    && rm NotoSansSC.zip
```

---

## OSS配置规范

### Bucket配置

- 读写权限：私有（不开公共读）
- 所有下载链接必须是临时签名URL（7天有效）
- 开启生命周期规则：30天后自动删除reports/目录下的文件

### 目录结构

```
bucket/
└── reports/
    └── {YYYYMMDD}/
        └── {responseId}.pdf
```

---

## 版本管理

### Git规范

分支：只用main，不搞复杂的分支策略（单人项目）

Commit信息格式：
```
{模块}: {做了什么}

示例：
classifier: add boundary case tests for threshold 3.5
pdf_generator: fix chinese font not loading on Railway
notifier: add smtp retry with exponential backoff
```

### 什么时候打Tag

当一个完整的Task完成并部署成功后：
```
git tag v0.1.0  # Task 01完成
git tag v0.2.0  # Task 02完成（服务号集成）
git tag v0.3.0  # Task 03完成（H5问卷页）
```
