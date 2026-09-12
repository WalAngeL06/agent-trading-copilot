import asyncio
import os
from agent_trading.config import Config
from agent_trading.okx import OkxMarketAdapter
from agent_trading.bot_service import BotService
from datetime import datetime, timezone, timedelta

async def verify():
    print("Testing BotService Wiring...")
    config = Config()
    adapter = OkxMarketAdapter(config.okx_site, config.cli_timeout_seconds, config.node_path, config.okx_cli_path)
    bot = BotService(config, adapter)
    
    # We will invoke the internals directly to prove the wiring
    bot.start()
    await asyncio.sleep(8)   # Give it time to hit OKX API and bootstrap
    
    bot.stop()
    print("Bot State after bootstrap:")
    print("Strategy Decision:", bot.latest_state.get("decision", {}))
    print("Market State (Prices):", bot.latest_state.get("market_state", {}).get("prices", []))
    print("Execution Trades:", len(bot.latest_state.get("execution", {}).get("trades", [])))
    print("Brain Event Count:", len(bot.brain.events) if bot.brain else 0)
    
    events = bot.brain.events if bot.brain else []
    print("First 5 events:", [e.kind for e in events[:5]])
    
if __name__ == '__main__':
    asyncio.run(verify())
