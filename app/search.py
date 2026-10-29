"""联网搜索兜底：通过 curl_cffi 模拟浏览器绕过反爬。"""
from curl_cffi import requests
from urllib.parse import quote
import re


def web_search(query: str, max_results: int = 3) -> list[str]:
    """
    多重策略搜索网页：
    1) Bing 国际版（最稳）
    2) 百度
    3) Google（最后兜底）
    """
    results = _search_bing(query, max_results)
    if results:
        return results
    results = _search_baidu(query, max_results)
    if results:
        return results
    results = _search_google(query, max_results)
    if results:
        return results
    print("[搜索失败] 所有搜索引擎均无结果")
    return []


def _clean_text(html_text: str) -> str:
    """去掉 HTML 标签、URL、多余空白，只保留纯文本。"""
    # 去 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', html_text)
    # 去 URL
    text = re.sub(r'https?://\S+', '', text)
    # 去实体
    text = text.replace("&nbsp;", " ").replace("&ensp;", " ").replace("&gt;", ">")
    text = text.replace("&lt;", "<").replace("&amp;", "&").replace("&#0183;", "·")
    # 合并空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _search_bing(query: str, n: int) -> list[str]:
    try:
        url = f"https://www.bing.com/search?q={quote(query)}&setlang=zh-cn&cc=cn"
        resp = requests.get(url, impersonate="chrome120", timeout=15, headers={
            "Accept-Language": "zh-CN,zh;q=0.9"
        })
        html = resp.text

        # 提取每个搜索结果块
        blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.S)

        results = []
        for block in blocks:
            text = _clean_text(block)
            if len(text) > 30:
                results.append(text)
            if len(results) >= n:
                break

        # 如果 b_algo 没命中，用更宽松的方式
        if not results:
            # 把整个 body 去标签后按段落分割
            body = re.search(r'<body[^>]*>(.*?)</body>', html, re.S)
            if body:
                raw = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', '', body.group(1), flags=re.S)
                raw = re.sub(r'<[^>]+>', '\n', raw)
                lines = [l.strip() for l in raw.split('\n') if len(l.strip()) > 40]
                results = [l for l in lines if any('\u4e00' <= c <= '\u9fff' for c in l)][:n]

        if results:
            print(f"[Bing搜索] 拿到 {len(results)} 条结果")
        return results
    except Exception as e:
        print(f"[Bing搜索失败] {e}")
        return []


def _search_baidu(query: str, n: int) -> list[str]:
    try:
        url = f"https://www.baidu.com/s?wd={quote(query)}&rn={n}"
        resp = requests.get(url, impersonate="chrome120", timeout=15, headers={
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept": "text/html,application/xhtml+xml"
        })
        resp.encoding = "utf-8"
        html = resp.text

        # 百度摘要
        snippets = re.findall(
            r'class=["\'][^"\']*c-abstract[^"\']*["\'].*?>(.*?)</',
            html, re.S
        )
        results = []
        for s in snippets:
            text = _clean_text(s)
            if len(text) > 15:
                results.append(text)
            if len(results) >= n:
                break

        if results:
            print(f"[百度搜索] 拿到 {len(results)} 条结果")
        return results
    except Exception as e:
        print(f"[百度搜索失败] {e}")
        return []


def _search_google(query: str, n: int) -> list[str]:
    try:
        url = f"https://www.google.com/search?q={quote(query)}&hl=zh-CN&num={n}"
        resp = requests.get(url, impersonate="chrome120", timeout=15, headers={
            "Accept-Language": "zh-CN,zh;q=0.9"
        })
        html = resp.text

        snippets = []
        for match in re.finditer(
            r'<div[^>]*class=["\'][^"\']*g[ "\'][^>]*>(.*?)</div>\s*</div>',
            html, re.S
        ):
            text = _clean_text(match.group(1))
            if len(text) > 40:
                snippets.append(text)
            if len(snippets) >= n:
                break

        if snippets:
            print(f"[Google搜索] 拿到 {len(snippets)} 条结果")
        return snippets
    except Exception as e:
        print(f"[Google搜索失败] {e}")
        return []