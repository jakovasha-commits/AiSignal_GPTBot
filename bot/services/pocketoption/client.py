import logging
from dataclasses import dataclass

from bot.config import settings
from bot.services.pocketoption.store import PocketOptionStore

log = logging.getLogger(__name__)


@dataclass
class PocketOptionStatus:
    pocket_id: str
    registered: bool = False
    deposit_amount: float = 0.0
    meets_deposit: bool = False
    registered_at: float | None = None
    deposit_updated_at: float | None = None


class PocketOptionClient:
    def __init__(self):
        min_deposit = float(getattr(settings, "pocketoption_min_deposit_usd", 50.0))
        self.min_deposit = max(0.0, min_deposit)
        self.store = PocketOptionStore(getattr(settings, "pocketoption_store_path", "./data/pocketoption_store.json"))

    async def get_status(self, pocket_id: str) -> PocketOptionStatus:
        pocket_id = pocket_id.strip()
        if not pocket_id:
            return PocketOptionStatus(pocket_id="", registered=False)
        record = self.store.get(pocket_id)
        if not record:
            return PocketOptionStatus(pocket_id=pocket_id)

        meets_deposit = record.deposit_amount >= self.min_deposit
        return PocketOptionStatus(
            pocket_id=pocket_id,
            registered=bool(record.registered_at),
            deposit_amount=record.deposit_amount,
            meets_deposit=meets_deposit,
            registered_at=record.registered_at,
            deposit_updated_at=record.deposit_updated_at,
        )

    async def check_deposit_or_registration(self, pocket_id: str) -> bool:
        status = await self.get_status(pocket_id)
        return status.registered and status.meets_deposit
