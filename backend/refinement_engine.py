"""
Refinement Engine - Core autonomous loop logic
Handles backtest execution, Claude analysis, and code updates
"""

import asyncio
import json
from datetime import datetime
from typing import Callable, Optional
import anthropic
import httpx

from models import (
    Strategy,
    Iteration,
    RefinementConfig,
    BacktestResult,
    AnalysisResult
)
from database import Database
from quantconnect_client import QuantConnectClient


class RefinementEngine:
    """
    Autonomous refinement loop that:
    1. Runs backtests via QuantConnect API
    2. Analyzes results with Claude
    3. Generates and applies code improvements
    4. Tracks iteration history
    5. Broadcasts updates to connected clients
    """
    
    def __init__(
        self,
        db: Database,
        config: RefinementConfig,
        on_update: Callable
    ):
        self.db = db
        self.config = config
        self.on_update = on_update
        
        self.is_running = False
        self.is_paused = False
        self.current_strategy_id: Optional[str] = None
        self.iteration_count = 0
        self.last_update: Optional[datetime] = None
        
        # Initialize clients
        self.claude = anthropic.Anthropic()
        self.qc = QuantConnectClient()
        
        # Track recent iterations for context
        self.iteration_history: list[Iteration] = []
        self.plateau_count = 0
    
    async def run(self, strategy: Strategy):
        """Main refinement loop"""
        self.is_running = True
        print(f"Starting refinement loop for strategy: {strategy.name}")
        print(f"Strategy QC Project ID: {strategy.qc_project_id}")
        print(f"Config: {self.config}")
        self.current_strategy_id = strategy.id
        self.iteration_count = 0
        self.plateau_count = 0
        
        # Load existing iteration history
        self.iteration_history = await self.db.get_iterations(
            strategy.id, 
            limit=10
        )
        
        await self.on_update("loop_started", {
            "strategy_id": strategy.id,
            "strategy_name": strategy.name
        })
        
        try:
            while self.is_running:
                try:
                    # Check pause state
                    while self.is_paused:
                        await asyncio.sleep(1)
                        if not self.is_running:
                            break

                    if not self.is_running:
                        break

                    # Check iteration limit
                    if self.config.max_iterations and self.iteration_count >= self.config.max_iterations:
                        await self.on_update("max_iterations_reached", {
                            "count": self.iteration_count
                        })
                        break

                    # Run one refinement cycle
                    iteration = await self._run_iteration(strategy)

                    if iteration:
                        self.iteration_count += 1
                        self.iteration_history.append(iteration)

                        # Keep only recent history
                        if len(self.iteration_history) > 10:
                            self.iteration_history.pop(0)

                        # Check for plateau
                        if self._check_plateau(iteration):
                            self.plateau_count += 1
                            if self.config.auto_stop_on_plateau and self.plateau_count >= 3:
                                await self.on_update("plateau_detected", {
                                    "message": "Performance has plateaued, stopping loop"
                                })
                                break
                        else:
                            self.plateau_count = 0

                    # Cooldown between iterations
                    await self.on_update("cooldown", {
                        "seconds": self.config.backtest_cooldown
                    })
                    await asyncio.sleep(self.config.backtest_cooldown)
                except Exception as e:
                    print(f"Loop error: {e}")
                    import traceback
                    traceback.print_exc()
                    raise

        except Exception as e:
            await self.on_update("error", {"message": str(e)})
        finally:
            self.is_running = False
            await self.on_update("loop_stopped", {
                "total_iterations": self.iteration_count
            })
    
    async def _run_iteration(self, strategy: Strategy) -> Optional[Iteration]:
        """Execute a single refinement iteration"""
        iteration_id = f"iter_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        await self.on_update("iteration_started", {
            "iteration_id": iteration_id,
            "iteration_number": self.iteration_count + 1
        })
        
        # Step 1: Run backtest
        await self.on_update("phase", {"phase": "backtesting"})
        backtest_result = await self._run_backtest(strategy)
        
        if not backtest_result:
            await self.on_update("backtest_failed", {})
            return None
        
        await self.on_update("backtest_complete", {
            "sharpe": backtest_result.sharpe_ratio,
            "max_drawdown": backtest_result.max_drawdown,
            "total_return": backtest_result.total_return
        })
        
        # Step 2: Analyze with Claude
        await self.on_update("phase", {"phase": "analyzing"})
        analysis = await self._analyze_results(strategy, backtest_result)
        
        await self.on_update("analysis_complete", {
            "diagnosis": analysis.diagnosis,
            "suggested_changes": len(analysis.suggested_changes)
        })
        
        # Step 3: Generate code changes
        await self.on_update("phase", {"phase": "generating_code"})
        new_code = await self._generate_code_changes(
            strategy, 
            analysis,
            backtest_result
        )
        
        # Step 4: Save iteration
        iteration = Iteration(
            id=iteration_id,
            strategy_id=strategy.id,
            version=strategy.current_version,
            timestamp=datetime.now(),
            backtest_result=backtest_result,
            analysis=analysis,
            code_before=strategy.code,
            code_after=new_code,
            improvement=self._calculate_improvement(backtest_result)
        )
        
        await self.db.save_iteration(iteration)
        
        # Step 5: Update strategy code
        strategy.code = new_code
        strategy.current_version += 1
        await self.db.save_strategy(strategy)
        
        self.last_update = datetime.now()
        
        await self.on_update("iteration_complete", {
            "iteration_id": iteration_id,
            "improvement": iteration.improvement,
            "new_version": strategy.current_version
        })
        
        return iteration
    
    async def _run_backtest(self, strategy: Strategy) -> Optional[BacktestResult]:
        """Submit strategy to QuantConnect and get results"""
        print(f"_run_backtest called for strategy: {strategy.name}, project: {strategy.qc_project_id}")

        try:
            print("Attempting to compile project...")
            compile_result = await self.qc.compile_project(
                strategy.qc_project_id,
                strategy.code
            )
            print(f"Compile result: {compile_result}")

            if not compile_result.get("success"):
                print(f"Compile failed: {compile_result}")
                return None

            print("Creating backtest...")
            backtest_id = await self.qc.create_backtest(
                strategy.qc_project_id,
                compile_result["compileId"],
                f"Refinement v{strategy.current_version}"
            )
            print(f"Backtest ID: {backtest_id}")

            print("Waiting for backtest to complete...")
            result = await self.qc.wait_for_backtest(backtest_id)
            print(f"Backtest result: {result}")

            if not result:
                return None

            return BacktestResult(
                backtest_id=backtest_id,
                sharpe_ratio=result.get("sharpeRatio", 0),
                max_drawdown=result.get("drawdown", 0),
                total_return=result.get("totalPerformance", 0),
                win_rate=result.get("winRate", 0),
                trade_count=result.get("totalNumberOfTrades", 0),
                avg_trade_duration=result.get("averageTradeDuration", "0"),
                raw_data=result
            )

        except Exception as e:
            print(f"Backtest error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _analyze_results(
        self, 
        strategy: Strategy, 
        result: BacktestResult
    ) -> AnalysisResult:
        """Use Claude to analyze backtest results"""
        
        # Build context from iteration history
        history_context = self._build_history_context()
        
        prompt = f"""You are analyzing trading strategy backtest results for autonomous refinement.

## Strategy
Name: {strategy.name}
Description: {strategy.description or "N/A"}

## Current Backtest Results
Sharpe Ratio: {result.sharpe_ratio:.3f}
Max Drawdown: {result.max_drawdown:.2%}
Total Return: {result.total_return:.2%}
Win Rate: {result.win_rate:.2%}
Trade Count: {result.trade_count}
Avg Trade Duration: {result.avg_trade_duration}

## Previous Iterations
{history_context}

## Focus Metric
Primary optimization target: {self.config.focus_metric}
Improvement threshold: {self.config.improvement_threshold:.1%}

## Current Code
```python
{strategy.code}
```

Analyze these results and provide:
1. DIAGNOSIS: What is the single biggest weakness or opportunity for improvement?
2. HYPOTHESIS: A specific, testable change to address the diagnosis
3. CONFIDENCE: Your confidence level (low/medium/high) that this change will improve the focus metric
4. RISK: Any risks or potential negative effects of this change

Respond in JSON format:
{{
    "diagnosis": "string describing the main issue",
    "hypothesis": "string describing the proposed change",
    "suggested_changes": [
        {{
            "type": "parameter|logic|filter|exit|entry",
            "description": "what to change",
            "rationale": "why this should help"
        }}
    ],
    "confidence": "low|medium|high",
    "risk_assessment": "string describing potential downsides"
}}
"""
        
        response = self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Parse response
        try:
            content = response.content[0].text
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            
            return AnalysisResult(
                diagnosis=data["diagnosis"],
                hypothesis=data["hypothesis"],
                suggested_changes=data["suggested_changes"],
                confidence=data["confidence"],
                risk_assessment=data["risk_assessment"]
            )
        except Exception as e:
            # Fallback analysis
            return AnalysisResult(
                diagnosis="Unable to parse detailed analysis",
                hypothesis="Consider parameter optimization",
                suggested_changes=[],
                confidence="low",
                risk_assessment="Analysis parsing failed"
            )
    
    async def _generate_code_changes(
        self,
        strategy: Strategy,
        analysis: AnalysisResult,
        result: BacktestResult
    ) -> str:
        """Generate updated strategy code based on analysis"""
        
        prompt = f"""You are modifying a QuantConnect Lean trading algorithm based on analysis.

## Current Code
```python
{strategy.code}
```

## Analysis
Diagnosis: {analysis.diagnosis}
Hypothesis: {analysis.hypothesis}
Suggested Changes: {json.dumps(analysis.suggested_changes, indent=2)}

## Current Performance
Sharpe: {result.sharpe_ratio:.3f}
Max DD: {result.max_drawdown:.2%}
Win Rate: {result.win_rate:.2%}

## Instructions
1. Implement the suggested changes
2. Keep changes minimal and focused on the hypothesis
3. Preserve all existing functionality unless explicitly changing it
4. Add a comment noting the change (e.g., "# v{strategy.current_version + 1}: adjusted X for Y")
5. Ensure the code remains valid QuantConnect Lean Python

Return ONLY the complete updated code, no explanations. The code must be syntactically valid and ready to compile.
"""
        
        response = self.claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.content[0].text
        
        # Extract code from response
        if "```python" in content:
            content = content.split("```python")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        return content.strip()
    
    def _build_history_context(self) -> str:
        """Build context string from recent iterations"""
        if not self.iteration_history:
            return "No previous iterations"
        
        lines = []
        for i, iteration in enumerate(self.iteration_history[-5:], 1):
            result = iteration.backtest_result
            lines.append(
                f"v{iteration.version}: Sharpe {result.sharpe_ratio:.3f}, "
                f"DD {result.max_drawdown:.2%}, WR {result.win_rate:.2%} | "
                f"Change: {iteration.analysis.hypothesis[:50]}..."
            )
        
        return "\n".join(lines)
    
    def _calculate_improvement(self, result: BacktestResult) -> float:
        """Calculate improvement over previous iteration"""
        if not self.iteration_history:
            return 0.0
        
        prev = self.iteration_history[-1].backtest_result
        metric = self.config.focus_metric
        
        if metric == "sharpe":
            if prev.sharpe_ratio == 0:
                return 0.0
            return (result.sharpe_ratio - prev.sharpe_ratio) / abs(prev.sharpe_ratio)
        elif metric == "drawdown":
            if prev.max_drawdown == 0:
                return 0.0
            # Lower drawdown is better, so invert
            return (prev.max_drawdown - result.max_drawdown) / abs(prev.max_drawdown)
        elif metric == "return":
            if prev.total_return == 0:
                return 0.0
            return (result.total_return - prev.total_return) / abs(prev.total_return)
        
        return 0.0
    
    def _check_plateau(self, iteration: Iteration) -> bool:
        """Check if improvement has plateaued"""
        return abs(iteration.improvement) < self.config.improvement_threshold
    
    async def stop(self):
        """Stop the refinement loop"""
        self.is_running = False
    
    def pause(self):
        """Pause the loop"""
        self.is_paused = True
    
    def resume(self):
        """Resume paused loop"""
        self.is_paused = False
