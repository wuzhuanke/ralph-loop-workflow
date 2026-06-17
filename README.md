# ralph-loop-workflow

Trae-CN 工作流自动化 Skill

## 安装

```bash
# 从 GitHub 安装
npx skills add wuzhuanke/ralpha-loop-workflow

# 从本地安装
npx skills add ./ralpha-loop-workflow

# 强制覆盖
npx skills add wuzhuanke/ralpha-loop-workflow --force
```

## 功能

- 🔄 携带失败上下文的自动重试
- 🔍 独立会话验证
- 📦 自然语言 YAML 工作流定义
- 🔀 分支与恢复

## 工具

| 工具 | 功能 |
|------|------|
| rf-start | 启动工作流 |
| rf-status | 查看状态 |
| rf-continue | 恢复工作流 |
| rf-cancel | 取消工作流 |
| rf-list | 列出工作流 |
| rf-detect | 检测标记 |

## 工作流

- **loop**: 循环执行
- **spec**: 规范驱动开发流水线

## 使用示例

### 启动 loop 工作流

```
用户：/ralpha-loop-workflow 用 JWT 和 refresh token 实现用户认证模块

助手：我来启动 loop 工作流来执行这个任务。
[调用 rf-start 工具]
工作流已启动，现在开始执行 DO 阶段...
```

### 启动 spec 工作流

```
用户：/ralpha-loop-workflow spec 添加 OAuth2 用户认证功能

助手：这是一个需要规范开发流程的任务，我来启动 spec 工作流。
[调用 rf-start 工具]
工作流已启动，第一步：需求分析与方案提议...
```

## 文档

- [命令参考](docs/commands_CN.md)
- [自定义工作流](docs/custom-workflows_CN.md)
- [工作原理](docs/how-it-works_CN.md)
