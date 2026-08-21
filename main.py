"""
main.py —— 程序入口

用法：
    python main.py --once   # 立刻跑一次（调试阶段天天用这个）
    python main.py          # 按 config 里的 schedule 定时跑（进程不能关）
"""
import argparse
import json
import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler

from db import Database
from scraper import GovScraper


def setup_logging(log_file: str):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),  # 日志写文件，出问题好排查
            logging.StreamHandler(sys.stdout),                # 同时打印到屏幕，调试看得见
        ],
    )


def run_once(config: dict) -> dict:
    """封装“跑一次”：建库 → 爬 → 统计 → 关库（finally 保证一定会关）。"""
    db = Database(config["db_path"], config)
    try:
        scraper = GovScraper(config)
        return scraper.run_once(db)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="政府文件监测爬虫")
    parser.add_argument("--once", action="store_true", help="立刻跑一次（调试用）")
    args = parser.parse_args()

    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    setup_logging(config["log_file"])
    logger = logging.getLogger("main")

    # args.once = 1
    if args.once:
        # 手动跑一次：调试阶段建议永远用这个，先别开定时
        stats = run_once(config)
        logger.info("本次执行完成：%s", stats)
        return

    # 定时模式：到点自动执行 run_once
    sc = config["schedule"]
    if not sc["enabled"]:
        logger.error("schedule.enabled 为 false 且没加 --once，程序退出")
        return

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_once,
        "cron",
        args=[config],
        hour=sc["hour"],
        minute=sc["minute"],
        id="daily_gov_scrape",
    )
    logger.info("定时任务已启动：每天 %02d:%02d 执行", sc["hour"], sc["minute"])
    scheduler.start()   # 阻塞运行，这个终端/进程不能关



main()