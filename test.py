import requests
from bs4 import BeautifulSoup
import pandas as pd
import math

# CSV読み込み
df = pd.read_csv("companies.csv")

results = []

for url in df["url"]:
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        links = soup.find_all("a")
        link_count = len(links)

        # =================
        # スコア計算
        # =================

        score = 0

        # ① SSL
        if url.startswith("https"):
            score += 10

        # ② リンク数
        if link_count > 300:
            score += 20
        elif link_count > 100:
            score += 15
        elif link_count > 50:
            score += 10
        elif link_count > 10:
            score += 5

        # ③ 採用ページ検出
        recruit_keywords = ["recruit", "career", "jobs", "採用"]

        recruit_found = False

        for a in links:
            href = str(a.get("href")).lower()
            if any(word in href for word in recruit_keywords):
                recruit_found = True
                break

        if recruit_found:
            score += 20

        sns_keywords = {
            "twitter": "twitter",
            "x.com": "twitter",
            "facebook": "facebook",
            "linkedin": "linkedin",
            "instagram": "instagram",
            "youtube": "youtube"
        }

        sns_types = set()

        for a in links:
            href = a.get("href")
            if href:
                href = href.lower()
                for key, name in sns_keywords.items():
                    if key in href:
                        sns_types.add(name)

        sns_count = len(sns_types)

        if sns_count >= 3:
            score += 20
        elif sns_count >= 1:
            score += 10

        # =================

        results.append({
            "url": url,
            "link_count": link_count,
            "sns_count": sns_count,
            "recruit": recruit_found,
            "score": score
        })

    except:
        results.append({
            "url": url,
            "link_count": 0,
            "sns_count": 0,
            "recruit": False,
            "score": 0
        })

# DataFrame化
df_result = pd.DataFrame(results)

# recruitを数値化
df_result["recruit_score"] = df_result["recruit"].astype(int)

# 偏差値計算関数
def deviation(series):
    mean = series.mean()
    std = series.std()
    return 50 + 10 * (series - mean) / std

df_result["link_dev"] = deviation(df_result["link_count"])
df_result["sns_dev"] = deviation(df_result["sns_count"])
df_result["recruit_dev"] = deviation(df_result["recruit_score"])

# 総合偏差値
df_result["total_dev"] = (
    df_result["link_dev"] +
    df_result["sns_dev"] +
    df_result["recruit_dev"]
) / 3

# 総合ランキング
df_result["rank"] = df_result["total_dev"].rank(ascending=False)

# ソート
df_result = df_result.sort_values("rank")

print(df_result)

# Excel出力
df_result.to_excel("analysis.xlsx", index=False)

print("分析完了")

import matplotlib.pyplot as plt

plt.hist(df_result["link_count"], bins=10)
plt.title("Link Count Distribution")
plt.xlabel("Link Count")
plt.ylabel("Number of Companies")

plt.show()
