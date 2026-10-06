import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import os

# =====================配置区=====================
URL = "https://zjj.sz.gov.cn/ztfw/zfbz/tzgg2017/index.html"
# 保租房监控关键词
KEYWORDS = ["保租房", "保障性租赁住房", "租赁住房", "认租", "配租", "选房", "摇号"]

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PWD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
LAST_RECORD_FILE = "/tmp/seen_titles.txt"
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
    content_text = f"""【深圳住建局-保租房新公告】
发布日期：{date}
公告标题：{title}
公告链接：{url}

检测到命中保租房关键词，请打开链接查看详情。"""
    msg = MIMEText(content_text, "plain", "utf-8")
    msg["Subject"] = "【提醒】深圳保租房新公告发布"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    server = smtplib.SMTP_SSL("smtp.qq.com", 465)
    server.login(SENDER_EMAIL, SENDER_PWD)
    server.send_message(msg)
    server.quit()


def load_seen_titles():
    seen = set()
    if os.path.exists(LAST_RECORD_FILE):
        with open(LAST_RECORD_FILE, "r", encoding="utf-8") as f:
            for line in f:
                t = line.strip()
                if t:
                    seen.add(t)
    return seen

def save_seen_titles(seen_set):
    with open(LAST_RECORD_FILE, "w", encoding="utf-8") as f:
        for t in seen_set:
            f.write(t + "\n")

def main():
    seen_titles = load_seen_titles()
    announcements = fetch_announcements()
    announcements = [x for x in announcements if len(x["title"])>5]
    if not announcements:
        print("未抓取到公告列表")
        return

    new_announcements = []
    for item in announcements:
        t = item["title"]
        if t not in seen_titles:
            new_announcements.append(item)

    if not new_announcements:
        print("本次没有发现新公告")
        return

    print(f"发现{len(new_announcements)}条未读公告")
    hit_any = False
    for item in new_announcements:
        title = item["title"]
        url = item["url"]
        date = item["date"]
        for kw in KEYWORDS:
            if kw in title:
                print(f"关键词命中：{title}")
                send_notice_email(title, url, date)
                hit_any = True
                break
        seen_titles.add(title)

    save_seen_titles(seen_titles)
    if not hit_any:
        print("新公告，但不包含保租房关键词，不发邮件，已加入已读列表")

if __name__ == "__main__":
    main()
