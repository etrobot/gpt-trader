from __future__ import annotations

from datetime import date as dt_date, datetime as dt_datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, create_engine, Session
import pandas as pd
import secrets
import string
import os
from pathlib import Path


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float  # 0.0 to 1.0
    message: str
    created_at: str
    completed_at: Optional[str] = None
    top_n: int
    selected_factors: Optional[List[str]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    version: int = 0  # For SSE version tracking


class RunRequest(BaseModel):
    top_n: int = 50
    selected_factors: Optional[List[str]] = None
    collect_latest_data: bool = True


class NewsEvaluationRequest(BaseModel):
    top_n: int = 10
    news_per_symbol: int = 3
    openai_model: str = "gpt-oss-120b"


class RunResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float
    message: str
    created_at: str
    completed_at: Optional[str]
    top_n: int
    selected_factors: Optional[List[str]] = None
    data: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None
    extended: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class NewsTaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    progress: float
    message: str
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class Message(BaseModel):
    message: str


class AuthRequest(BaseModel):
    name: str
    email: str
    password: Optional[str] = None  # 密码变为可选，用于弱校验


class AuthResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str


# 数据库模型


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(
        default_factory=lambda: "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(8)
        ),
        primary_key=True,
    )
    name: Optional[str] = None
    email: str
    password_hash: Optional[str] = None  # Store hashed password
    image: Optional[str] = None
    is_admin: bool = Field(default=False, description="Whether the user is an admin")
    created_at: dt_datetime = Field(
        default_factory=lambda: dt_datetime.now(timezone.utc)
    )


class CryptoSymbol(SQLModel, table=True):
    """加密货币交易对基本信息"""

    __tablename__ = "crypto_symbol"

    symbol: str = Field(primary_key=True, description="交易对，例如 BTCUSDT")
    name: str = Field(description="名称，例如 BTC/USDT")
    created_at: dt_datetime = Field(
        default_factory=dt_datetime.now, description="创建时间"
    )
    updated_at: dt_datetime = Field(
        default_factory=dt_datetime.now, description="更新时间"
    )


class DailyMarketData(SQLModel, table=True):
    """日行情表"""

    __tablename__ = "daily_market_data"

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(foreign_key="crypto_symbol.symbol", description="交易对")
    date: dt_date = Field(description="日期")
    open_price: float = Field(description="开盘价")
    high_price: float = Field(description="最高价")
    low_price: float = Field(description="最低价")
    close_price: float = Field(description="收盘价")
    volume: float = Field(description="成交量")
    amount: Optional[float] = Field(description="成交额")
    change_pct: float = Field(description="涨跌百分比")


# 数据库连接配置
# 使用环境变量配置数据库路径，支持Docker挂载
import os

BASE_DIR = Path(__file__).parent
DATABASE_PATH = os.getenv(
    "DATABASE_PATH", str(BASE_DIR / "data_management" / "crypto_data.db")
)
# 确保数据库目录存在
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    """创建数据库和表"""
    SQLModel.metadata.create_all(engine)


# ---- Factor plugin types ----


class Factor(BaseModel):
    id: str
    name: str
    description: str = ""
    columns: List[Dict[str, Any]] = []  # ColumnSpec dicts
    # compute(history, top_spot) -> pd.DataFrame with '代码' and defined columns
    compute: Callable[[Dict[str, pd.DataFrame], Optional[pd.DataFrame]], pd.DataFrame]


def get_session():
    """获取数据库会话"""
    with Session(engine) as session:
        yield session
