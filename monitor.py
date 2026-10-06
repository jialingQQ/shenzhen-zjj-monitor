import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import json
import os

# ===================== 配置区 =====================
URL = "https://zjj.sz.gov.cn/ztfw/gg/"
KEYWORDS = ["保租房", "保障性租赁住房", "租赁住房", "认租", "配租", "选房", "摇号"]

# 邮箱密钥（从仓库secrets读取）
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PWD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# Gist持久化配置（新增两个secrets）
GIST_TOKEN = os.getenv("GIST_TOKEN")
GIST_ID = os.getenv("GIST_ID")
# ==================================================

def load_seen_from_gist():
    """从Gist读取已推送过的公告标题集合"""
    headers = {"Authorization": f"token {GIST_TOKEN}"}
    resp = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=headers, timeout=20)
    if resp.status_code != 200:
        print("Gist读取失败，使用空集合")
        return set()
    gist_data = resp.json()
    file_content = list(gist_data["files"].values())[0]["content"]
    try:
        return set(json.loads(file_content))
    except Exception as e:
        print(f"解析Gist内容异常: {e}")
        return set()

def save_seen_to_gist(seen_set):
    """把更新后的已读列表写回Gist"""
    headers = {"Authorization": f"token {GIST_TOKEN}"}
    payload = {
        "files": {
            "seen_titles.json": {
                "content": json.dumps(list(seen_set), ensure_ascii=False, indent=2)
            }
        }
    }
    requests.patch(f"https://api.github.com/gists/{GIST_ID}", headers=headers, json=payload, timeout=20)

def fetch_announcements():
    """抓取住建局公告列表"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(URL, headers=headers, timeout=20)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("li")
    result = []
    for li in items:
        a_tag = li.find("a")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        link = a_tag.get("href", "")
        if link.startswith("/"):
            link = "https://zjj.sz.gov.cn" + link
        result.append({"title": title, "url": link})
    return result

def send_batch_email(new_items):
    """批量合并发送一封邮件"""
    if not new_items:
        return
    html_lines = []
    html_lines.append("<h3>【深圳住建局保租房新公告提醒】</h3>")
    for item in new_items:
        html_lines.append(f'<p><a href="{item["url"]}">{item["title"]}</a></p>')
    email_body = "\n".join(html_lines)

    msg = MIMEText(email_body, "html", "utf-8")
    msg["Subject"] = "【保租房监控】发现新公告"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PWD)
        server.send_message(msg)
    print(f"已发送邮件，共{len(new_items)}条新公告")

def main():
    seen_titles = load_seen_from_gist()
    all_ann = fetch_announcements()
    new_matched = []
    for ann in all_ann:
        title = ann["title"]
        if title in seen_titles:
            continue
        # 关键词匹配
        if any(k in title for k in KEYWORDS):
            new_matched.append(ann)
            seen_titles.add(title)
    print(f"本次匹配到新公告数量：{len(new_matched)}")
    if new_matched:
        send_batch_email(new_matched)
        save_seen_to_gist(seen_titles)
    else:
        print("本次无新增匹配公告")

if __name__ == "__main__":
    main()
