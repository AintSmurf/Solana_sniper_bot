from config.urls import RUGCHECK
from utilities.requests_utility import RequestsUtility
from helpers.logging_manager import LoggingHandler
from pprint import pprint

# set up logger
logger = LoggingHandler.get_logger()


class RugCheckUtility:
    def __init__(self):
        base_url = RUGCHECK["BASE_URL"]
        self.token_risk = RUGCHECK["TOKEN_RISK"]
        self.requests_utility = RequestsUtility(base_url)
        logger.info("initialized Rugcheck class.")

    def check_token_security(self, token_address):
        logger.info("checking token security ...")
        url = self.token_risk + f"/{token_address}/report/summary"
        data = self.requests_utility.get(url)
        return data["score"] <= 3000

    def is_liquidity_unlocked(self, token_address):
        logger.info(f"🔍 Checking token liquidity for {token_address} ...")
        url = self.token_risk + f"/{token_address}/report"
        token_data = self.requests_utility.get(url)

        risks = token_data.get("risks", [])
        total_liquidity = token_data.get("totalMarketLiquidity", 0)
        total_holders = token_data.get("totalHolders", 0)
        top_holders = token_data.get("topHolders", [])

        # Check for major risk flags
        for risk in risks:
            if risk["level"] == "danger":
                logger.warning(f"🚨 HIGH RISK: {risk['name']} - {risk['description']}")
                return False  # Don't trade

        #  Check if LP is fully unlocked (Rug Pull Risk)
        lp_unlocked = token_data.get("markets", [{}])[0].get("lpUnlocked", 0)
        lp_locked = token_data.get("markets", [{}])[0].get("lpLocked", 0)
        if lp_unlocked > 0 and lp_locked == 0:
            logger.warning("🚨 LP is 100% UNLOCKED - High rug pull risk!")
            return False

        # Check top holders for insider control
        if top_holders:
            biggest_holder_pct = top_holders[0].get("pct", 0)
            if biggest_holder_pct > 50:
                logger.warning(
                    f"🚨 TOP HOLDER OWNS {biggest_holder_pct:.2f}% - High risk of manipulation!"
                )
                return False

        # Check if liquidity is too low (Prevents trading illiquid tokens)
        if total_liquidity < 10_000:
            logger.warning(f"🚨 LOW LIQUIDITY: Only ${total_liquidity:.2f} available!")
            return False

        #  Check if the token has too few holders
        if total_holders < 100:
            logger.warning(f"🚨 LOW HOLDERS: Only {total_holders} holders exist!")
            return False

        # If no major risks detected, it’s safe to trade
        logger.info("✅ Token passes risk check!")
        return True
