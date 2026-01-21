# Trading Refinery

Autonomous trading strategy refinement platform. Runs backtests on QuantConnect, analyzes results with Claude, and iteratively improves your strategies—all while you're away.

![Dashboard](docs/dashboard.png)

## Features

- **Autonomous Loop**: Continuous backtest → analyze → refine cycle
- **Real-time Dashboard**: Monitor progress from any browser
- **WebSocket Updates**: Live activity log and metrics
- **Iteration History**: Track every change and its impact
- **Configurable**: Set focus metrics, iteration limits, plateau detection
- **Multi-Strategy**: Manage and refine multiple strategies

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React UI      │────▶│   FastAPI       │────▶│  QuantConnect   │
│   (Browser)     │◀────│   Backend       │◀────│  API            │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Claude API    │
                        │   (Analysis)    │
                        └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- QuantConnect account with API access
- Anthropic API key

### 1. Clone and configure

```bash
git clone <your-repo>
cd trading-refinery

# Create environment file
cp .env.example .env
```

Edit `.env`:
```
QC_USER_ID=your_quantconnect_user_id
QC_API_TOKEN=your_quantconnect_api_token
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### 2. Deploy with Docker

```bash
docker-compose up -d
```

Access the dashboard at `http://localhost:3000`

### 3. Or deploy to Railway/Render

**Railway:**
1. Connect your GitHub repo
2. Add environment variables in Railway dashboard
3. Deploy both services

**Render:**
1. Create a Web Service for backend (Python)
2. Create a Static Site for frontend
3. Configure environment variables

## Usage

### 1. Add a Strategy

Click the `+` button in the sidebar and paste your QuantConnect Lean algorithm code.

### 2. Configure Refinement

- **Max Iterations**: Limit total iterations (leave blank for unlimited)
- **Cooldown**: Seconds between iterations (respects QC rate limits)
- **Focus Metric**: Sharpe, Drawdown, or Return
- **Improvement Threshold**: Minimum improvement to continue
- **Auto-stop on Plateau**: Stop if 3 consecutive iterations show no improvement

### 3. Start the Loop

Click **Start Loop** and let it run. You can:
- Close your browser—it continues on the server
- Check back from any device
- Pause/Resume as needed
- View the activity log in real-time

### 4. Review Results

- **Metrics cards**: Current performance snapshot
- **Sharpe chart**: Visual evolution across iterations
- **Analysis section**: Claude's diagnosis and hypothesis
- **Code viewer**: See current strategy code

## How It Works

Each iteration:

1. **Backtest**: Submits strategy to QuantConnect
2. **Analyze**: Claude examines results, identifies weaknesses
3. **Hypothesize**: Claude proposes a specific, testable change
4. **Generate**: Claude writes the code modification
5. **Apply**: New code is saved, next iteration begins

The analysis prompt includes:
- Current metrics
- Recent iteration history (what's been tried)
- Focus metric and threshold

This context prevents Claude from repeating failed experiments and keeps changes focused.

## API Reference

### Strategies
- `GET /api/strategies` - List all strategies
- `POST /api/strategies` - Create strategy
- `GET /api/strategies/{id}` - Get strategy with iterations

### Loop Control
- `GET /api/loop/status` - Current loop status
- `POST /api/loop/start` - Start refinement
- `POST /api/loop/stop` - Stop loop
- `POST /api/loop/pause` - Pause loop
- `POST /api/loop/resume` - Resume loop

### Configuration
- `GET /api/config` - Get config
- `PUT /api/config` - Update config

### WebSocket
Connect to `/ws` for real-time updates:
```javascript
const ws = new WebSocket('ws://your-server/ws');
ws.onmessage = (e) => {
  const { event, data } = JSON.parse(e.data);
  // Handle: iteration_started, backtest_complete, analysis_complete, etc.
};
```

## Advanced Configuration

### Custom Analysis Prompts

Edit `refinement_engine.py` to customize Claude's analysis prompt. You can add:
- Specific constraints ("never use more than 20 positions")
- Domain knowledge ("this trades energy futures")
- Risk parameters ("max drawdown must stay under 15%")

### Multiple Focus Metrics

Modify `_calculate_improvement()` to create composite scores:
```python
def _calculate_improvement(self, result):
    # Weight multiple metrics
    sharpe_delta = ...
    drawdown_delta = ...
    return 0.7 * sharpe_delta + 0.3 * drawdown_delta
```

### Email Notifications

Add a notification service for important events:
```python
async def _run_iteration(self, strategy):
    ...
    if iteration.improvement > 0.1:  # 10% improvement
        await send_notification(f"Major improvement in {strategy.name}!")
```

## Troubleshooting

**Backtest fails repeatedly**
- Check QuantConnect API credentials
- Verify project exists in QC
- Check QC rate limits (free tier is limited)

**No improvement after many iterations**
- Strategy may be near optimal
- Try changing focus metric
- Consider broader parameter ranges

**WebSocket disconnects**
- Normal for mobile/sleep
- Auto-reconnects after 3 seconds

## License

MIT
