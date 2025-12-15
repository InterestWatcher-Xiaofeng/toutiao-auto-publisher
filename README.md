# 🏭 内容工厂（未完成版）

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/PyQt6-GUI-green.svg" alt="PyQt6">
  <img src="https://img.shields.io/badge/Playwright-Automation-orange.svg" alt="Playwright">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
  <img src="https://img.shields.io/badge/Version-1.1.0-red.svg" alt="Version">
</p>

<p align="center">
  <b>多平台自动化内容发布工具</b><br>
  一键发布文章到多个自媒体平台，解放你的双手 🚀
</p>

---

## ✨ 功能特性

| 功能 | 状态 | 说明 |
|------|------|------|
| 🎯 头条号发布 | ✅ 已完成 | 支持文章批量发布、封面选择 |
| 📰 搜狐号发布 | ✅ 已完成 | 支持素材库封面、自动登录 |
| 📝 百家号发布 | 🚧 开发中 | 计划支持 |
| 🎬 抖音发布 | 📋 计划中 | 视频内容发布 |
| 🔄 多账号管理 | ✅ 已完成 | 支持多账号切换发布 |
| 🍪 Cookie管理 | ✅ 已完成 | 自动保存登录状态 |
| 📊 发布日志 | ✅ 已完成 | 详细的发布记录 |

## 🖥️ 软件截图

```
┌─────────────────────────────────────────────────────────┐
│  🏭 内容工厂 v1.1.0                              [─][□][×]│
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────────────────────────────────┐ │
│  │ 📁 账号   │  │ 📄 待发布文章列表                    │ │
│  │ ├─ 头条号 │  │ ┌────┬──────────────┬────────────┐  │ │
│  │ │  └─账号1│  │ │序号│    标题      │   状态     │  │ │
│  │ └─ 搜狐号 │  │ ├────┼──────────────┼────────────┤  │ │
│  │    └─账号2│  │ │ 1  │ AI改变世界  │ ✅ 已发布  │  │ │
│  └──────────┘  │ │ 2  │ 科技新趋势  │ 🔄 发布中  │  │ │
│                │ │ 3  │ 未来展望    │ ⏳ 待发布  │  │ │
│  [🚀 开始发布] │ └────┴──────────────┴────────────┘  │ │
│  [⏹️ 停止]     └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Windows 10/11

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/InterestWatcher-Xiaofeng/toutiao-auto-publisher.git
cd toutiao-auto-publisher

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装 Playwright 浏览器
playwright install chromium

# 4. 运行程序
python main.py
```

## 📁 项目结构

```
内容工厂/
├── 📄 main.py              # 程序入口
├── 📁 src/
│   ├── 📁 adapters/        # 平台适配器
│   │   ├── base_adapter.py # 基础适配器
│   │   ├── toutiao_adapter.py  # 头条号
│   │   └── sohu_adapter.py     # 搜狐号
│   ├── 📁 core/            # 核心模块
│   └── 📁 ui/              # 界面模块
├── 📁 data/                # 数据存储
│   ├── accounts.json       # 账号配置
│   └── cookies/            # 登录状态
├── 📁 articles/            # 待发布文章
└── 📁 logs/                # 运行日志
```

## 🔧 使用说明

### 1. 配置账号

在 `data/accounts.json` 中添加账号信息：

```json
{
  "accounts": [
    {
      "id": "sohu_001",
      "platform": "sohu",
      "name": "我的搜狐号",
      "username": "your_username"
    }
  ]
}
```

### 2. 准备文章

将 Markdown 文章放入 `articles/` 目录，格式：

```markdown
# 文章标题

文章正文内容...
```

### 3. 开始发布

1. 运行 `python main.py`
2. 选择要发布的账号
3. 选择要发布的文章
4. 点击"开始发布"

## 🛠️ 技术栈

- **GUI框架**: PyQt6 - 现代化桌面界面
- **自动化**: Playwright - 可靠的浏览器自动化
- **语言**: Python 3.8+ - 简洁高效

## 📋 开发计划

- [x] 头条号文章发布
- [x] 搜狐号文章发布  
- [x] 多账号管理
- [x] Cookie持久化
- [ ] 百家号支持
- [ ] 企鹅号支持
- [ ] 定时发布
- [ ] 发布数据统计

## ⚠️ 免责声明

本工具仅供学习交流使用，请遵守各平台的使用规则。使用本工具产生的任何后果由使用者自行承担。

## 📄 开源协议

MIT License © 2024

---

<p align="center">
  <b>🌟 如果觉得有帮助，请给个 Star 支持一下！</b>
</p>

