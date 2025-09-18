from __future__ import annotations
import logging
import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Check for proxy configuration
proxy_url = os.getenv('PROXY_URL')
if proxy_url:
    logger.info(f"Using proxy: {proxy_url}")
    PROXIES = {'http': proxy_url, 'https': proxy_url}
else:
    PROXIES = None


@dataclass
class NewsItem:
    """新闻项目数据结构"""

    title: str
    content: str
    url: str
    published_at: str
    source: str
    symbol: Optional[str] = None


def fetch_crypto_news(symbols: List[str], limit: int = 5) -> Dict[str, List[NewsItem]]:
    """
    获取加密货币相关新闻

    Args:
        symbols: 加密货币符号列表 (如 ['BTC', 'ETH'])
        limit: 每个币种获取的新闻数量限制

    Returns:
        Dict[str, List[NewsItem]]: 按币种分组的新闻列表
    """
    news_by_symbol = {}

    for symbol in symbols:
        try:
            # 去掉USDT后缀，获取基础币种名称
            base_symbol = (
                symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol
            )
            news_items = _fetch_news_for_symbol(base_symbol, limit)
            news_by_symbol[symbol] = news_items
            logger.info(f"获取到 {len(news_items)} 条 {symbol} 相关新闻")
        except Exception as e:
            logger.error(f"获取 {symbol} 新闻失败: {e}")
            news_by_symbol[symbol] = []

    return news_by_symbol


def _fetch_news_for_symbol(symbol: str, limit: int) -> List[NewsItem]:
    """
    为单个币种获取新闻
    使用免费的新闻API或RSS源
    """
    news_items = []

    try:
        # 使用CoinDesk API (免费)
        news_items.extend(_fetch_from_coindesk(symbol, limit // 2))

        # 使用CryptoNews API (模拟数据，实际使用时需要替换为真实API)
        news_items.extend(_fetch_from_crypto_news_api(symbol, limit // 2))

    except Exception as e:
        logger.error(f"获取 {symbol} 新闻时出错: {e}")

    # 按发布时间排序，取最新的
    news_items.sort(key=lambda x: x.published_at, reverse=True)
    return news_items[:limit]


def _fetch_from_coindesk(symbol: str, limit: int) -> List[NewsItem]:
    """从CoinDesk获取新闻"""
    news_items = []

    try:
        # CoinDesk RSS feed (免费)
        url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
        response = requests.get(url, timeout=10, proxies=PROXIES)

        if response.status_code == 200:
            # 简单的RSS解析 (实际项目中建议使用feedparser库)
            content = response.text

            # 模拟解析结果 (实际需要解析RSS XML)
            if symbol.upper() in content.upper():
                news_items.append(
                    NewsItem(
                        title=f"{symbol} Market Analysis - CoinDesk",
                        content=f"Latest market analysis and trends for {symbol}. The cryptocurrency market shows continued volatility with {symbol} experiencing significant trading volume.",
                        url=f"https://www.coindesk.com/markets/{symbol.lower()}",
                        published_at=datetime.now().isoformat(),
                        source="CoinDesk",
                        symbol=symbol,
                    )
                )

    except Exception as e:
        logger.error(f"从CoinDesk获取 {symbol} 新闻失败: {e}")

    return news_items


def _fetch_from_crypto_news_api(symbol: str, limit: int) -> List[NewsItem]:
    """从加密货币新闻API获取新闻 (模拟实现)"""
    news_items = []

    try:
        # 模拟新闻数据 (实际项目中替换为真实API调用)
        mock_news = [
            {
                "title": f"{symbol} Shows Strong Technical Indicators",
                "content": f"Technical analysis reveals that {symbol} is showing bullish patterns with increased trading volume and positive momentum indicators. Market sentiment remains optimistic as institutional adoption continues to grow.",
                "url": f"https://cryptonews.com/{symbol.lower()}-technical-analysis",
                "published_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                "source": "CryptoNews",
            },
            {
                "title": f"Institutional Interest in {symbol} Surges",
                "content": f"Major financial institutions are showing increased interest in {symbol}, with several announcing new investment products and trading services. This institutional adoption is driving significant market growth.",
                "url": f"https://cryptonews.com/{symbol.lower()}-institutional-interest",
                "published_at": (datetime.now() - timedelta(hours=6)).isoformat(),
                "source": "CryptoNews",
            },
        ]

        for news_data in mock_news[:limit]:
            news_items.append(
                NewsItem(
                    title=news_data["title"],
                    content=news_data["content"],
                    url=news_data["url"],
                    published_at=news_data["published_at"],
                    source=news_data["source"],
                    symbol=symbol,
                )
            )

    except Exception as e:
        logger.error(f"从CryptoNews API获取 {symbol} 新闻失败: {e}")

    return news_items
