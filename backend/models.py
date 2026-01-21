"""
Data models for Trading Refinery
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class BacktestResult(BaseModel):
    """Results from a QuantConnect backtest"""
    backtest_id: str
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    win_rate: float = 0.0
    trade_count: int = 0
    avg_trade_duration: str = "0"
    raw_data: dict = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Claude's analysis of backtest results"""
    diagnosis: str
    hypothesis: str
    suggested_changes: list[dict] = Field(default_factory=list)
    confidence: str = "medium"
    risk_assessment: str = ""


class Iteration(BaseModel):
    """A single refinement iteration"""
    id: str
    strategy_id: str
    version: int
    timestamp: datetime
    backtest_result: BacktestResult
    analysis: AnalysisResult
    code_before: str
    code_after: str
    improvement: float = 0.0


class Strategy(BaseModel):
    """A trading strategy being refined"""
    id: str
    name: str
    code: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    current_version: int = 1
    qc_project_id: Optional[str] = None
    
    # Performance tracking
    best_sharpe: float = 0.0
    best_version: int = 1


class RefinementConfig(BaseModel):
    """Configuration for the refinement loop"""
    max_iterations: Optional[int] = None  # None = unlimited
    backtest_cooldown: int = 60  # Seconds between iterations
    improvement_threshold: float = 0.01  # 1% minimum improvement
    focus_metric: str = "sharpe"  # sharpe, drawdown, return
    auto_stop_on_plateau: bool = True
    
    # Advanced settings
    max_code_changes_per_iteration: int = 3
    preserve_winning_logic: bool = True
    exploration_rate: float = 0.2  # Chance to try riskier changes


class LoopStatus(BaseModel):
    """Current status of the refinement loop"""
    is_running: bool = False
    is_paused: bool = False
    current_strategy_id: Optional[str] = None
    current_iteration: int = 0
    last_update: Optional[datetime] = None
    error: Optional[str] = None
