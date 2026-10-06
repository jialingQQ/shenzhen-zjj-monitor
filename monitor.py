import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os

# =====================配置区=====================
URL = "https://zjj.sz.gov.cn/ztfw/zfbz/tzgg2017/index.html"
# 自定义监控关键词，自己修改
KEYWORDS = ["安居型商品房", "配售", "摇号", "选房", "认购"]

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PWD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
LAST_RECORD_FILE = "last_record.txt"
# ================================================

def fetch_announcements():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    resp = requests.get(URL, headers=headers, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    items = soup.select("li")
    result = []
    for li in items:
        a_tag = li.select_one("a")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        if not title:
            continue
        link = a_tag.get("href","")
        date_text = li.get_text(strip=True).replace(title,"").strip()
        result.append({
            "title": title,
            "url": link,
            "date": date_text
        })
    return result


def send_notice_email(title, url, date):
    content_text = f"""【深圳住建局-住房保障新公告】
发布日期：{date}
公告标题：{title}
公告链接：{url}

检测到命中监控关键词，请打开链接查看详情。"""
    msg = MIMEText(content_text, "plain", "utf-8")
    msg["Subject"] = "【提醒】深圳住建局新公告命中关键词"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    server = smtplib.SMTP_SSL("smtp.qq.com", 465)
    server.login(SENDER_EMAIL, SENDER_PWD)
    server.send_message(msg)
    server.quit()


def main():
    last_title = ""
    try:
        with open(LAST_RECORD_FILE, "r", encoding="utf-8") as f:
            last_title = f.read().strip()
    except FileNotFoundError:
        last_title = ""

    announcements = fetch_announcements()
    announcements = [x for x in announcements if len(x["title"])>5]
    if not announcements:
        print("未抓取到公告列表")
        return

    latest = announcements[0]
    latest_title = latest["title"]

    if latest_title != last_title:
        print(f"发现新公告：{latest_title}")
        hit = False
        for word in KEYWORDS:
            if word in latest_title:
                hit = True
                break
        if hit:
            print("关键词匹配，发送邮件通知")
            send_notice_email(latest_title, latest["url"], latest["date"])
        # 更新记录
        with open(LAST_RECORD_FILE, "w", encoding="utf-8") as f:
            f.write(latest_title)
    else:
        print("暂无新公告")


if __name__ == "__main__":
    main()
