# 湖南省政府文件监测爬虫

每日自动采集湖南省人民政府公开的政策文件，增量去重存入 SQLite，支持关键词过滤与定时调度。
适合用于政策文件追踪、信息公开资料整理等场景。

## 功能特点

- **每日定时采集**：通过 APScheduler 每天自动执行（可配置时间）
- **增量去重**：基于 URL 唯一约束，重复内容自动跳过，不重复入库
- **关键词过滤**：仅保留标题命中所配关键词的文件
- **翻页采集**：自动翻遍列表全部页面（当前配置 34 页）
- **请求健壮性**：随机 User-Agent、随机间隔、失败自动重试
- **反爬兼容**：使用 curl_cffi 模拟 Chrome 指纹，解决 TLS 握手被拦截问题

## 技术栈

- Python 3.10+
- 请求：curl_cffi（TLS 指纹伪装），fake_useragent(随机 User-Agent)
- 解析：BeautifulSoup + lxml
- 存储：SQLite
- 调度：APScheduler

## 目录结构

```
gov_spider/
├── config.json      # 配置文件（网址、关键词、请求参数、定时时间）
├── db.py            # 数据库层（建表、查询、写入、去重）
├── scraper.py       # 爬虫核心（请求、解析、增量、入库）
├── main.py          # 程序入口（手动跑 / 定时跑）
├── requirements.txt # 依赖清单
└── README.md        # 本文档
```

## 快速开始

### 1. 环境准备

```bash
pip install -r requirements.txt
```

### 2. 修改配置

打开 `config.json`，按需修改：
- `keywords`：关键词列表，`[]` 表示不过滤全部采集
- `schedule`：定时执行时间（小时、分钟）
- `base_url`：要爬的政府网址

### 3. 运行

```bash
# 立刻手动跑一次（调试用，推荐）
python main.py --once

# 定时模式（按 config.json 里的 schedule 每天执行）
python main.py
```

## 输出说明

运行后数据保存在 `gov_files.db`（SQLite 数据库），`files` 表字段：

| 字段 | 说明 |
|---|---|
| title | 文件标题 |
| url | 原文链接 |
| publish_date | 发布日期 |
| content | 正文内容 |
| fetched_at | 抓取时间 |

日志写入 `scraper.log`。


## 查看数据
命令行快速查看已采集的记录：
```bash
python -c "import sqlite3; db=sqlite3.connect('gov_files.db'); [print(r) for r in db.execute('select id,title,publish_date from files limit 10')]"
```
或用 DB Browser for SQLite 打开 `gov_files.db` 图形化查看。

## 常见问题

**Q：为什么第一次跑很久？**
A：列表页和详情页之间有随机间隔（防封），第一次全量抓取需要几分钟到十几分钟，属正常。

**Q：运行后 new 一直是 0 正常吗？**
A：正常。说明数据已全部入库，增量去重生效；以后只有网站出现新文件时 new 才会 > 0。

**Q：提示 SSL 相关错误？**
A：本项目的请求基于 curl_cffi，请确认已安装并在代码中使用了 impersonate="chrome"。

## 免责声明

本项目仅用于合法、合规的公开信息采集与学习交流，请遵守目标网站的 robots 协议及相关法律法规，勿将采集数据用于非法用途。

