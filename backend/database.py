"""
Database layer using SQLite with aiosqlite
Stores strategies, iterations, and configuration
"""

import json
import aiosqlite
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import (
    Strategy,
    Iteration,
    RefinementConfig,
    BacktestResult,
    AnalysisResult
)


class Database:
    """
    Async SQLite database for persisting refinement data
    """
    
    def __init__(self, db_path: str = "refinery.db"):
        self.db_path = Path(db_path)
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def initialize(self):
        """Create tables if they don't exist"""
        self._connection = await aiosqlite.connect(self.db_path)
        
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                current_version INTEGER DEFAULT 1,
                qc_project_id TEXT,
                best_sharpe REAL DEFAULT 0,
                best_version INTEGER DEFAULT 1
            );
            
            CREATE TABLE IF NOT EXISTS iterations (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                backtest_result TEXT NOT NULL,
                analysis TEXT NOT NULL,
                code_before TEXT NOT NULL,
                code_after TEXT NOT NULL,
                improvement REAL DEFAULT 0,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            );
            
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                data TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_iterations_strategy 
                ON iterations(strategy_id);
            CREATE INDEX IF NOT EXISTS idx_iterations_timestamp 
                ON iterations(timestamp DESC);
        """)
        
        await self._connection.commit()
    
    async def close(self):
        """Close database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
    
    # ============ Strategy Operations ============
    
    async def save_strategy(self, strategy: Strategy):
        """Insert or update a strategy"""
        await self._connection.execute("""
            INSERT OR REPLACE INTO strategies 
            (id, name, code, description, created_at, current_version, 
             qc_project_id, best_sharpe, best_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy.id,
            strategy.name,
            strategy.code,
            strategy.description,
            strategy.created_at.isoformat(),
            strategy.current_version,
            strategy.qc_project_id,
            strategy.best_sharpe,
            strategy.best_version
        ))
        await self._connection.commit()
    
    async def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Get a strategy by ID"""
        cursor = await self._connection.execute(
            "SELECT * FROM strategies WHERE id = ?",
            (strategy_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        return Strategy(
            id=row[0],
            name=row[1],
            code=row[2],
            description=row[3],
            created_at=datetime.fromisoformat(row[4]),
            current_version=row[5],
            qc_project_id=row[6],
            best_sharpe=row[7],
            best_version=row[8]
        )
    
    async def get_all_strategies(self) -> list[Strategy]:
        """Get all strategies"""
        cursor = await self._connection.execute(
            "SELECT * FROM strategies ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        
        return [
            Strategy(
                id=row[0],
                name=row[1],
                code=row[2],
                description=row[3],
                created_at=datetime.fromisoformat(row[4]),
                current_version=row[5],
                qc_project_id=row[6],
                best_sharpe=row[7],
                best_version=row[8]
            )
            for row in rows
        ]
    
    async def delete_strategy(self, strategy_id: str):
        """Delete a strategy and its iterations"""
        await self._connection.execute(
            "DELETE FROM iterations WHERE strategy_id = ?",
            (strategy_id,)
        )
        await self._connection.execute(
            "DELETE FROM strategies WHERE id = ?",
            (strategy_id,)
        )
        await self._connection.commit()
    
    # ============ Iteration Operations ============
    
    async def save_iteration(self, iteration: Iteration):
        """Save an iteration"""
        await self._connection.execute("""
            INSERT INTO iterations 
            (id, strategy_id, version, timestamp, backtest_result, 
             analysis, code_before, code_after, improvement)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            iteration.id,
            iteration.strategy_id,
            iteration.version,
            iteration.timestamp.isoformat(),
            iteration.backtest_result.model_dump_json(),
            iteration.analysis.model_dump_json(),
            iteration.code_before,
            iteration.code_after,
            iteration.improvement
        ))
        await self._connection.commit()
    
    async def get_iterations(
        self, 
        strategy_id: str, 
        limit: int = 50
    ) -> list[Iteration]:
        """Get iterations for a strategy"""
        cursor = await self._connection.execute("""
            SELECT * FROM iterations 
            WHERE strategy_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (strategy_id, limit))
        
        rows = await cursor.fetchall()
        
        return [
            Iteration(
                id=row[0],
                strategy_id=row[1],
                version=row[2],
                timestamp=datetime.fromisoformat(row[3]),
                backtest_result=BacktestResult(**json.loads(row[4])),
                analysis=AnalysisResult(**json.loads(row[5])),
                code_before=row[6],
                code_after=row[7],
                improvement=row[8]
            )
            for row in rows
        ]
    
    async def get_latest_iteration(
        self, 
        strategy_id: str
    ) -> Optional[Iteration]:
        """Get the most recent iteration"""
        iterations = await self.get_iterations(strategy_id, limit=1)
        return iterations[0] if iterations else None
    
    # ============ Config Operations ============
    
    async def get_config(self) -> Optional[RefinementConfig]:
        """Get the refinement configuration"""
        cursor = await self._connection.execute(
            "SELECT data FROM config WHERE id = 1"
        )
        row = await cursor.fetchone()
        
        if not row:
            return None
        
        return RefinementConfig(**json.loads(row[0]))
    
    async def save_config(self, config: RefinementConfig):
        """Save refinement configuration"""
        await self._connection.execute("""
            INSERT OR REPLACE INTO config (id, data)
            VALUES (1, ?)
        """, (config.model_dump_json(),))
        await self._connection.commit()
