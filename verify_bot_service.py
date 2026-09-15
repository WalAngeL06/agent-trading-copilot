import asyncio
from agent_trading.config import Config
from agent_trading.bot_service import BotService

async def verify():
    print("Testing BotService Wiring...")
    config = Config()
    bot = BotService(config)

    # We will invoke the internals directly to prove the wiring
    bot.start()
    await asyncio.sleep(8)   # Give it time to hit OKX API and bootstrap
    if not bot.market_connected:
        raise RuntimeError("public MCP market runtime did not connect")
    print("Bot State after bootstrap:")
    print("Market Source:", bot.market_source)
    print("Market Connected:", bot.market_connected)
    print("Strategy Decision:", bot.latest_state.get("decision", {}))
    print("Market Last Price:", bot.latest_state.get("market_state", {}).get("last_price"))
    print("Execution Trades:", len(bot.latest_state.get("execution", {}).get("trades", [])))
    print("Brain Event Count:", len(bot.brain.events) if bot.brain else 0)

    events = bot.brain.events if bot.brain else []
    print("First 5 events:", [e.kind for e in events[:5]])
    await bot.shutdown()

if __name__ == '__main__':
    asyncio.run(verify())
