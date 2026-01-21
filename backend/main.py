"""
Trading Refinery - Autonomous Strategy Refinement Platform
FastAPI backend with background refinement loop
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import httpx

from refinement_engine import RefinementEngine
from models import (
    Strategy, 
    Iteration, 
    RefinementConfig, 
    LoopStatus,
    BacktestResult
)
from database import Database


# Global state
db = Database()
engine: Optional[RefinementEngine] = None
connected_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup"""
    await db.initialize()
    yield
    # Cleanup
    if engine and engine.is_running:
        await engine.stop()


app = FastAPI(
    title="Trading Refinery",
    description="Autonomous trading strategy refinement platform",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Models ============

class StartLoopRequest(BaseModel):
    strategy_id: str
    config: RefinementConfig


class StrategyCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None


class ConfigUpdate(BaseModel):
    max_iterations: Optional[int] = None
    backtest_cooldown: Optional[int] = None
    improvement_threshold: Optional[float] = None
    focus_metric: Optional[str] = None
    auto_stop_on_plateau: Optional[bool] = None


# ============ WebSocket for Live Updates ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Keep connection alive, listen for pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


async def broadcast_update(event: str, data: dict):
    """Send update to all connected clients"""
    message = json.dumps({"event": event, "data": data})
    for client in connected_clients:
        try:
            await client.send_text(message)
        except:
            pass


# ============ Strategy Endpoints ============

@app.get("/api/strategies")
async def list_strategies():
    """Get all strategies"""
    strategies = await db.get_all_strategies()
    return {"strategies": strategies}


@app.post("/api/strategies")
async def create_strategy(req: StrategyCreate):
    """Create a new strategy"""
    strategy = Strategy(
        id=f"strat_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        name=req.name,
        code=req.code,
        description=req.description,
        created_at=datetime.now(),
        current_version=1
    )
    await db.save_strategy(strategy)
    return {"strategy": strategy.model_dump()}


@app.get("/api/strategies/{strategy_id}")
async def get_strategy(strategy_id: str):
    """Get strategy details with iteration history"""
    strategy = await db.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    iterations = await db.get_iterations(strategy_id)
    return {
        "strategy": strategy.model_dump(),
        "iterations": [i.model_dump() for i in iterations]
    }


@app.put("/api/strategies/{strategy_id}/code")
async def update_strategy_code(strategy_id: str, code: str):
    """Manually update strategy code"""
    strategy = await db.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    strategy.code = code
    strategy.current_version += 1
    await db.save_strategy(strategy)
    return {"strategy": strategy.model_dump()}


# ============ Refinement Loop Endpoints ============

@app.get("/api/loop/status")
async def get_loop_status():
    """Get current refinement loop status"""
    if not engine:
        return {"status": "stopped", "current_strategy": None}
    return {
        "status": "running" if engine.is_running else "stopped",
        "current_strategy": engine.current_strategy_id,
        "current_iteration": engine.iteration_count,
        "last_update": engine.last_update.isoformat() if engine.last_update else None
    }


@app.post("/api/loop/start")
async def start_loop(req: StartLoopRequest):
    """Start the autonomous refinement loop"""
    global engine
    
    strategy = await db.get_strategy(req.strategy_id)
    if not strategy:
        raise HTTPException(404, "Strategy not found")
    
    if engine and engine.is_running:
        raise HTTPException(400, "Loop already running. Stop it first.")
    
    engine = RefinementEngine(
        db=db,
        config=req.config,
        on_update=broadcast_update
    )
    
    # Start loop in background
    asyncio.create_task(engine.run(strategy))
    
    return {"status": "started", "strategy_id": req.strategy_id}


@app.post("/api/loop/stop")
async def stop_loop():
    """Stop the refinement loop"""
    global engine
    if not engine or not engine.is_running:
        raise HTTPException(400, "No loop running")
    
    await engine.stop()
    return {"status": "stopped"}


@app.post("/api/loop/pause")
async def pause_loop():
    """Pause the refinement loop"""
    if not engine or not engine.is_running:
        raise HTTPException(400, "No loop running")
    engine.pause()
    return {"status": "paused"}


@app.post("/api/loop/resume")
async def resume_loop():
    """Resume paused loop"""
    if not engine:
        raise HTTPException(400, "No loop to resume")
    engine.resume()
    return {"status": "resumed"}


# ============ Iteration History ============

@app.get("/api/iterations/{strategy_id}")
async def get_iterations(strategy_id: str, limit: int = 50):
    """Get iteration history for a strategy"""
    iterations = await db.get_iterations(strategy_id, limit=limit)
    return {"iterations": [i.model_dump() for i in iterations]}


@app.get("/api/iterations/{strategy_id}/latest")
async def get_latest_iteration(strategy_id: str):
    """Get the most recent iteration"""
    iteration = await db.get_latest_iteration(strategy_id)
    if not iteration:
        raise HTTPException(404, "No iterations found")
    return {"iteration": iteration.model_dump()}


# ============ Configuration ============

@app.get("/api/config")
async def get_config():
    """Get current refinement configuration"""
    config = await db.get_config()
    return {"config": config.model_dump() if config else RefinementConfig().model_dump()}


@app.put("/api/config")
async def update_config(updates: ConfigUpdate):
    """Update refinement configuration"""
    config = await db.get_config() or RefinementConfig()
    
    for field, value in updates.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    
    await db.save_config(config)
    
    # Update running engine if exists
    if engine:
        engine.config = config
    
    return {"config": config.model_dump()}


# ============ Health Check ============

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "loop_running": engine.is_running if engine else False
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
