import sys
from unittest.mock import MagicMock

# Mock WSManager at import time to avoid asyncio event loop conflicts
import bot.ws_manager
bot.ws_manager.WSManager = MagicMock()

import bot.service
bot.service.WSManager = bot.ws_manager.WSManager
