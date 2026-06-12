# 后端编码规范

本目录是 MaxKB Django 后端代码。

## 快速规则

- 保持 Django app 边界清晰：`models`、`serializers`、`views`、`api`、`sql` 不要随意跨层塞逻辑。
- 知识库单体模式下，默认只维护知识库、模型、用户、文件、系统设置相关能力。
- 未经明确要求，不要恢复或扩展 `application`、`chat`、`tools`、`trigger` 的产品入口。
- 非必要不改数据库表结构；必须改时补齐迁移、回滚影响说明和验证。
- API 返回保持项目现有 `Result` / serializer 风格，不要引入新的响应包装。
- 配置优先走现有 `CONFIG` / 环境变量机制，不要写死本机路径、密钥或端口。
- 新增文件写入、模型缓存、日志目录时必须支持本地开发目录，避免再次写死 `/opt/maxkb`。
- 处理异常时保留原始错误信息用于日志或调试，不要静默吞错。
- 后端改动后至少运行 Django check；Python 文件改动优先运行 Ruff。

## 推荐校验

```bash
./scripts/validate-code-rules.sh
```

针对后端的最小手动检查：

```bash
.venv/bin/ruff check <changed-python-files>
PYTHONPATH=apps .venv/bin/python apps/manage.py check
```

