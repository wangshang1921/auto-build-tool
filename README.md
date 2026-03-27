# Auto Build Tool

一个基于 Python + Flask + SQLite 的工程自动构建工具。

## 功能

- 新建工程并保存配置（名称、仓库地址、用户名、Token、本地仓库地址、构建脚本）
- 创建后自动执行 `git clone` 到本地指定目录
- 工程列表展示与操作：
  - 同步：拉取远程最新代码并显示输出
  - 构建：执行工程配置中的构建脚本（Windows: PowerShell，Linux: bash/sh）
- 更多操作：
  - 修改：允许修改仓库地址、用户名、Token、构建脚本
  - 删除：删除工程、构建记录目录、克隆仓库

## 启动

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 启动服务

```bash
python app.py
```

3. 打开页面

- `http://127.0.0.1:5000`

## 数据库

- 数据库文件：`build_tool.db`
- 表：
  - `projects`

## 注意事项

- 构建执行的是你在页面配置的脚本：
  - Windows 环境会使用 PowerShell 执行。
  - Linux 环境（含 Docker image）会使用 bash/sh 执行。
  - 请确保脚本语法与部署环境一致。
- 仓库认证按 HTTP/HTTPS 地址拼接用户名和 Token，请确保仓库地址格式正确。
