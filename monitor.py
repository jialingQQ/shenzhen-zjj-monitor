import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ===================== 配置区 =====================
# 仅保留：深圳市住建局 + 宝安区住建局
URL_LIST = [
    {
        "name": "深圳市住建局",
        "url": "https://zjj.sz.gov.cn/ztfw/zfbz/tzgg2017/index.html"
    },
    {
        "name": "宝安区住建局",
        "url": "https://www.baoan.gov.cn/bajshej/gkmlpt/index"
    }
]
# 只保留保租房相关关键词
KEYWORDS = ["保租房", "保障性租赁住房", "租赁住房", "认租", "配租", "选房", "摇号"]
# 邮箱密钥（从仓库secrets读取）
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PWD = os.getenv("SENDER_PWD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
# Gist持久化配置
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
    file_content = gist_data["files"]["seen_titles.json"]["content"]
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

def fetch_announcements(site_info):
    """抓取单个页面公告列表，增加重试策略"""
    url = site_info["url"]
    site_name = site_info["name"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    # 重试配置
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    resp = session.get(url, headers=headers, timeout=30)
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
        # 区分域名拼接相对链接
        if link.startswith("/"):
            if "baoan.gov.cn" in url:
                link = "https://www.baoan.gov.cn" + link
            else:
                link = "https://zjj.sz.gov.cn" + link
        result.append({"title": title, "url": link, "site": site_name})
    return result

def send_batch_email(new_items):
    """批量合并发送一封邮件"""
    if not new_items:
        return
    html_lines = []
    html_lines.append("<h3>【深圳保租房新公告提醒】</h3>")
    for item in new_items:
        html_lines.append(f'<p><b>{item["site"]}</b>：<a href="{item["url"]}">{item["title"]}</a></p>')
    email_body = "\n".join(html_lines)
    msg = MIMEText(email_body, "html", "utf-8")
    msg["Subject"] = "【保租房监控】发现新公告"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
        server.login(SENDER_EMAIL, SENDER_PWD)
        server.send_message(msg)
    print(f"✅ 已发送邮件，共{len(new_items)}条新公告")

def main():
    seen_titles = load_seen_from_gist()
    all_ann = []
    # 循环遍历站点
    for site in URL_LIST:
        try:
            ann_list = fetch_announcements(site)
            all_ann.extend(ann_list)
            print(f"✅ {site['name']} 抓取到 {len(ann_list)} 条公告")
        except Exception as e:
            print(f"❌ 抓取 {site['name']} 失败: {e}")
    new_matched = []
    for ann in all_ann:
        title = ann["title"]
        if title in seen_titles:
            continue
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
