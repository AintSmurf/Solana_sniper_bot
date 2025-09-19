from config.third_parties import RUGCHECK
from utilities.requests_utility import RequestsUtility
from helpers.logging_manager import LoggingHandler

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

        # Extract key data
        risks = token_data.get("risks", [])
        total_holders = token_data.get("totalHolders", 0)
        top_holders = token_data.get("topHolders", [])
        insider_networks = token_data.get("graphInsidersDetected", 0)
        total_lp_providers = token_data.get("totalLPProviders", 0)

        for risk in risks:
            if risk["level"] == "danger":
                logger.warning(f"🚨 HIGH RISK: {risk['name']} - {risk['description']}")
                return False

        lp_unlocked = token_data.get("markets", [{}])[0].get("lpUnlocked", 0)
        lp_locked = token_data.get("markets", [{}])[0].get("lpLocked", 0)
        if lp_unlocked > 0 and lp_locked == 0:
            logger.warning("🚨 LP is 100% UNLOCKED - High rug pull risk!")
            return False

        if top_holders:
            biggest_holder_pct = top_holders[0].get("pct", 0)
            if biggest_holder_pct > 30:
                logger.warning(
                    f"🚨 TOP HOLDER OWNS {biggest_holder_pct:.2f}% - High risk of manipulation!"
                )
                return False

        if total_holders < 100:
            logger.warning(f"🚨 LOW HOLDERS: Only {total_holders} holders exist!")
            return False

        if insider_networks > 100:
            logger.warning(
                f"🚨 High insider presence detected ({insider_networks} insiders)! Possible manipulation."
            )
            return False

        if total_lp_providers < 5:
            logger.warning(
                f"🚨 LOW LP PROVIDERS: Only {total_lp_providers} liquidity providers found. High risk!"
            )
            return False

        logger.info("✅ Token passes full liquidity & scam check!")
        return True

    def get_liquidity(self, token_address):
        logger.info(f"🔍 Retrieving full liquidity data for {token_address} ...")
        url = self.token_risk + f"/{token_address}/report"
        token_data = self.requests_utility.get(url)

        if not token_data:
            logger.warning("⚠️ No liquidity data found.")
            return None
        total_liquidity = token_data.get("totalMarketLiquidity", 0)

        return total_liquidity

    def is_liquidity_unlocked_test(self, token_address):
        logger.info(f"🔍 Checking LP lock status for {token_address} ...")
        url = self.token_risk + f"/{token_address}/report"
        
        try:
            token_data = self.requests_utility.get(url)
        except Exception as e:
            logger.error(f"⚠️ Failed to fetch LP data: {e}")
            return "unknown"

        markets = token_data.get("markets", [{}])
        lp_unlocked = markets[0].get("lpUnlocked", 0)
        lp_locked = markets[0].get("lpLocked", 0)
        total_lp = lp_locked + lp_unlocked

        logger.debug(f"Token: {token_address}, LP Locked: {lp_locked}, LP Unlocked: {lp_unlocked}")

        if total_lp == 0:
            logger.warning("⚠️ No LP data found. Risk score: 0")
            return "unknown"

        locked_ratio = lp_locked / total_lp
        logger.info(f"🔒 LP Locked Ratio: {locked_ratio:.2f}")

        if locked_ratio < 0.3:
            logger.warning(f"⚠️ Low LP lock ratio ({locked_ratio:.1%}) — risky")
            return "risky"

        logger.info("✅ LP looks healthy.")
        return "safe"


