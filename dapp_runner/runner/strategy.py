"""Dapp runner's market strategy implementation."""
import logging
from typing import Set

from yapapi import rest
from yapapi.strategy.wrapping_strategy import WrappingMarketStrategy

BLACKLISTED_SCORE = -1.0


class BlacklistOnFailure(WrappingMarketStrategy):
    """A market strategy wrapper that blacklists providers when they fail an activity."""

    def __init__(self, base_strategy):
        """Initialize instance.

        :param base_strategy: the base strategy around which this strategy is wrapped
        """
        super().__init__(base_strategy)
        self._logger = logging.getLogger(f"{__name__}.{type(self).__name__}")
        self._blacklist: Set[str] = set()

    def blacklist_node(self, node_id: str):
        """Add the given node id to the blacklist."""
        self._blacklist.add(node_id)

    async def score_offer(self, offer: rest.market.OfferProposal) -> float:
        """Reject the node if blacklisted, otherwise score the offer using the base strategy."""

        if offer.issuer in self._blacklist:
            self._logger.debug(
                "Rejecting offer %s from a blacklisted node '%s'", offer.id, offer.issuer
            )
            return BLACKLISTED_SCORE

        score = await self.base_strategy.score_offer(offer)
        return score
