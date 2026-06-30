#!/usr/bin/env python3
"""
Daily AI News Collector
Reddit, Hacker News, Zenn, YouTube (optional) から
その日に話題になったAI活用情報を最大10件収集して Markdown に保存する。
"""

import os
import requests
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- 設定 ---
JST = timezone(timedelta(hours=9))
now_jst = datetime.now(JST)
date_str = now_jst.strftime('%Y%m%d')
output_file = f"{date_str}_aiinfo.md"

# 今日0:00 JST のUNIXタイムスタンプ
today_start_jst = datetime(now_jst.year, now_jst.month, now_jst.day, tzinfo=JST)
today_start_ts = today_start_jst.timestamp()

HEADERS = {
    'User-Agent': 'AINewsBot/1.0 (Daily AI Digest; github.com/makubass/ai-info)'
}

AI_KEYWORDS = [
    'AI', 'artificial intelligence', 'machine learning', 'LLM', 'GPT', 'Claude',
    'Gemini', 'ChatGPT', 'OpenAI', 'Anthropic', 'Google AI', 'Meta AI',
    'generative AI', 'neural network', 'deep learning', 'foundation model',
    'AGI', 'agent', 'RAG', 'fine-tuning', 'diffusion', 'multimodal',
    'Copilot', 'Grok', 'Llama', 'Mistral', 'Perplexity', 'Midjourney',
    '生成AI', 'AI活用', '人工知能', '機械学習', '大規模言語モデル'
]

def is_ai_related(title: str, body: str = '') -> bool:
    combined = (title + ' ' + body).lower()
    return any(kw.lower() in combined for kw in AI_KEYWORDS)

# --- Reddit ---
def fetch_reddit() -> list[dict]:
    subreddits = [
        'artificial', 'MachineLearning', 'ChatGPT', 'LocalLLaMA',
        'singularity', 'AITools', 'StableDiffusion', 'OpenAI'
    ]
    posts = []
    for sub in subreddits:
        try:
            url = f'https://www.reddit.com/r/{sub}/hot.json?limit=25'
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            for child in r.json()['data']['children']:
                p = child['data']
                if p.get('created_utc', 0) < today_start_ts:
                    continue
                title = p.get('title', '')
                selftext = p.get('selftext', '')
                if not is_ai_related(title, selftext):
                    continue
                # 外部リンクがあればそちら、なければ Reddit スレッド
                link_url = p.get('url', '')
                if link_url.startswith('https://www.reddit.com') or not link_url:
                    link_url = f"https://reddit.com{p['permalink']}"
                summary = selftext[:200].strip() or f"r/{sub} でのディスカッション"
                posts.append({
                    'title': title,
                    'url': link_url,
                    'discussion_url': f"https://reddit.com{p['permalink']}",
                    'score': p.get('score', 0),
                    'source': f'Reddit r/{sub}',
                    'summary': summary,
                })
        except Exception as e:
            print(f"[Reddit] r/{sub} エラー: {e}")
    return posts


# --- Hacker News ---
def fetch_hackernews() -> list[dict]:
    posts = []
    try:
        r = requests.get(
            'https://hacker-news.firebaseio.com/v1/topstories.json', timeout=10
        )
        ids = r.json()[:100]
        for story_id in ids:
            try:
                r2 = requests.get(
                    f'https://hacker-news.firebaseio.com/v1/item/{story_id}.json',
                    timeout=5
                )
                item = r2.json()
                if not item or item.get('time', 0) < today_start_ts:
                    continue
                title = item.get('title', '')
                if not is_ai_related(title):
                    continue
                url = item.get('url') or f"https://news.ycombinator.com/item?id={story_id}"
                posts.append({
                    'title': title,
                    'url': url,
                    'discussion_url': f"https://news.ycombinator.com/item?id={story_id}",
                    'score': item.get('score', 0),
                    'source': 'Hacker News',
                    'summary': f"HN スコア: {item.get('score', 0)}, コメント: {item.get('descendants', 0)} 件",
                })
            except Exception:
                pass
    except Exception as e:
        print(f"[HackerNews] エラー: {e}")
    return posts


# --- Zenn (日本語テック記事) ---
def fetch_zenn() -> list[dict]:
    posts = []
    today_str = now_jst.strftime('%Y-%m-%d')
    try:
        url = 'https://zenn.dev/api/articles?order=trending&count=30'
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return posts
        for article in r.json().get('articles', []):
            # 今日公開・更新された記事のみ
            published = article.get('published_at', '') or ''
            if not published.startswith(today_str):
                continue
            title = article.get('title', '')
            if not is_ai_related(title):
                continue
            slug = article.get('slug', '')
            username = article.get('user', {}).get('username', '')
            article_url = f"https://zenn.dev/{username}/articles/{slug}"
            posts.append({
                'title': title,
                'url': article_url,
                'discussion_url': article_url,
                'score': article.get('liked_count', 0),
                'source': 'Zenn',
                'summary': f"Zenn の技術記事。いいね: {article.get('liked_count', 0)} 件",
            })
    except Exception as e:
        print(f"[Zenn] エラー: {e}")
    return posts


# --- Qiita (日本語テック記事) ---
def fetch_qiita() -> list[dict]:
    posts = []
    today_str = now_jst.strftime('%Y-%m-%d')
    try:
        url = 'https://qiita.com/api/v2/items'
        params = {
            'query': 'AI OR 生成AI OR LLM OR ChatGPT',
            'per_page': 20,
            'sort': 'created',
        }
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return posts
        for item in r.json():
            created = item.get('created_at', '')
            if not created.startswith(today_str):
                continue
            title = item.get('title', '')
            if not is_ai_related(title):
                continue
            posts.append({
                'title': title,
                'url': item.get('url', ''),
                'discussion_url': item.get('url', ''),
                'score': item.get('likes_count', 0),
                'source': 'Qiita',
                'summary': f"Qiita の技術記事。いいね: {item.get('likes_count', 0)} 件",
            })
    except Exception as e:
        print(f"[Qiita] エラー: {e}")
    return posts


# --- YouTube (API キーがある場合のみ) ---
def fetch_youtube() -> list[dict]:
    api_key = os.environ.get('YOUTUBE_API_KEY', '')
    if not api_key:
        return []
    posts = []
    try:
        date_after = today_start_jst.strftime('%Y-%m-%dT%H:%M:%SZ')
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            'part': 'snippet',
            'q': 'AI 活用 生成AI',
            'type': 'video',
            'order': 'viewCount',
            'publishedAfter': date_after,
            'maxResults': 10,
            'key': api_key,
            'relevanceLanguage': 'ja',
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return posts
        for item in r.json().get('items', []):
            video_id = item['id'].get('videoId', '')
            title = item['snippet'].get('title', '')
            if not is_ai_related(title):
                continue
            posts.append({
                'title': title,
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'discussion_url': f"https://www.youtube.com/watch?v={video_id}",
                'score': 9999,  # ビュー数でソートされているので高スコア扱い
                'source': 'YouTube',
                'summary': item['snippet'].get('description', '')[:200].strip() or 'YouTube 動画',
            })
    except Exception as e:
        print(f"[YouTube] エラー: {e}")
    return posts


# --- Markdown 生成 ---
def generate_markdown(items: list[dict]) -> str:
    date_fmt = now_jst.strftime('%Y年%m月%d日')
    lines = [
        f"# AI活用 情報ダイジェスト {date_fmt}",
        "",
        f"収集日時: {now_jst.strftime('%Y-%m-%d %H:%M')} JST  ",
        f"件数: {len(items)} 件",
        "",
        "---",
        "",
    ]
    for i, item in enumerate(items, 1):
        lines += [
            f"## {i}. {item['title']}",
            "",
            f"**要約**: {item['summary']}",
            "",
            f"**元記事**: {item['url']}",
            "",
            f"*ソース: {item['source']}*",
            "",
            "---",
            "",
        ]
    return '\n'.join(lines)


# --- メイン ---
def main():
    print(f"AI ニュース収集開始: {now_jst.strftime('%Y-%m-%d %H:%M')} JST")

    # ソースごとに取得し、各ソース最大3件に制限してから結合
    MAX_PER_SOURCE = 3

    def cap(posts: list[dict]) -> list[dict]:
        """スコア降順で各ソース最大 MAX_PER_SOURCE 件に絞る"""
        return sorted(posts, key=lambda x: x['score'], reverse=True)[:MAX_PER_SOURCE]

    all_posts: list[dict] = []
    all_posts += cap(fetch_reddit())
    all_posts += cap(fetch_hackernews())
    all_posts += cap(fetch_zenn())
    all_posts += cap(fetch_qiita())
    all_posts += cap(fetch_youtube())

    # URL重複排除
    seen: set[str] = set()
    unique: list[dict] = []
    for p in all_posts:
        if p['url'] not in seen:
            seen.add(p['url'])
            unique.append(p)

    # スコア降順で上位10件
    top10 = sorted(unique, key=lambda x: x['score'], reverse=True)[:10]

    if not top10:
        content = (
            f"# AI活用 情報ダイジェスト {now_jst.strftime('%Y年%m月%d日')}\n\n"
            "本日は収集できた情報がありませんでした。\n"
        )
        print("本日の AI 情報は見つかりませんでした。")
    else:
        content = generate_markdown(top10)
        print(f"{len(top10)} 件収集完了")

    Path(output_file).write_text(content, encoding='utf-8')
    print(f"保存完了: {output_file}")


if __name__ == '__main__':
    main()
