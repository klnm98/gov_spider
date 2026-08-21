"""
scraper.py —— 爬虫核心
流程：请求列表页 → 解析出条目 → 关键词过滤 → 增量去重 → 请求详情页 → 存库
"""
import random
import time
import logging
from urllib.parse import urljoin

from curl_cffi import requests as requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)


class GovScraper:
    def __init__(self, config: dict):
        self.config = config
        req = config["request"]
        self.delay_min = req["delay_min"]
        self.delay_max = req["delay_max"]
        self.timeout = req["timeout"]
        self.retries = req["retries"]

        # 初始化 fake_useragent
        self.ua = UserAgent()

        # Session 会复用 TCP 连接，比每次新建 requests.get 更快更稳
        self.session = requests.Session(impersonate="chrome")

    # ---------- 第 1 层：请求 ----------
    def fetch_page(self, url: str) -> str:
        """GET 一个页面，失败自动重试，成功返回 HTML 文本。"""
        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                # 使用 fake_useragent 生成随机 User-Agent
                headers = {"User-Agent": self.ua.random}
                resp = self.session.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()          # 状态码不是 2xx 会抛异常
                if not resp.encoding:
                    resp.encoding = "utf-8"  # 自动识别编码，中文网站防乱码
                return resp.text
            except Exception as e:
                last_exc = e
                logger.warning("请求失败 %s，第 %d/%d 次重试：%s", url, attempt, self.retries, e)
                time.sleep(2 * attempt)          # 重试间隔递增，别连着重试把网站惹毛
        raise RuntimeError(f"请求 {url} 失败（已重试 {self.retries} 次）：{last_exc}")

    def polite_sleep(self):
        """礼貌性随机间隔：既保护网站，也降低被封风险。"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    # ---------- 第 2 层：解析 ----------
    def parse_list_page(self, html: str) -> list:
        """
        解析“列表页”，返回条目列表，每条格式：
            {"title": "标题", "url": "详情页链接", "publish_date": "日期"}
        """
        soup = BeautifulSoup(html, "lxml")
        items = []
        for tr in soup.select(self.config["list_selectors"]["item"]):
            a = tr.select_one(self.config["list_selectors"]["title"])
            if not a:
                continue
            title = a.get_text(strip=True)
            # urljoin 把相对链接（如 /zhengce/xxx.htm）补全成绝对地址
            url = urljoin(self.config["base_url"], a.get("href", ""))
            date_el = tr.select_one(self.config["list_selectors"]["date"])
            publish_date = date_el.get_text(strip=True) if date_el else ""
            items.append({"title": title, "url": url, "publish_date": publish_date})
        return items

    def parse_detail_page(self, html: str) -> str:
        """
        解析“详情页”，返回正文纯文本。
        """
        soup = BeautifulSoup(html, "lxml")
        content_els = soup.select(self.config["detail_selector"]["content"])
        if not content_els:
            return ""
        # 拼接所有匹配元素的文本
        return "\n".join(el.get_text(strip=True) for el in content_els)

    # ---------- 第 3 层：主流程 ----------
    def run_once(self, db) -> dict:
        """执行一次完整爬取，返回统计：看到几条、新增几条、各跳过几条。"""
        keywords = self.config.get("keywords", [])
        existing = db.get_existing_urls()      # 已爬过的 URL 集合（增量判断的基准）

        stats = {"seen": 0, "new": 0, "skipped_existing": 0, "skipped_keyword": 0}
        mp = self.config.get("max_page",34)
        start_urls = [self.config["base_url"] + "/hnszf/xxgk/wjk/szfwj/wjk_glrb.html"] + [self.config["base_url"] + f"/hnszf/xxgk/wjk/szfwj/wjk_glrb_{i}.html" for i in range(2, mp+1)]
        for list_url in start_urls:
            logger.info("抓列表页：%s", list_url)
            list_html = self.fetch_page(list_url)
            items = self.parse_list_page(list_html)
            logger.info("列表页解析出 %d 条", len(items))

            for item in items:
                stats["seen"] += 1
                title = item["title"]

                # 1.关键词过滤
                if keywords and not any(k in title for k in keywords):
                    stats["skipped_keyword"] += 1
                    continue

                # 2.增量判断：这个 URL 已经爬过 → 跳过（不请求、不入库）
                if item["url"] in existing:
                    stats["skipped_existing"] += 1
                    continue

                # 3.没爬过的才去请求详情页
                detail_html = self.fetch_page(item["url"])
                content = self.parse_detail_page(detail_html)
                db.insert_file(title, item["url"], item["publish_date"], content)

                existing.add(item["url"])      # 入库后立刻加入集合，防止同一轮里重复
                stats["new"] += 1

                self.polite_sleep()            # 每次详情请求之间礼貌间隔

        return stats