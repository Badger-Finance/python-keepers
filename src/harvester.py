from decimal import Decimal


class IHarvester:
    def get_harvestable_rewards_amount(self, *args, **kwargs) -> Decimal:
        raise NotImplementedError

    def get_current_rewards_price(self, *args, **kwargs) -> Decimal:
        raise NotImplementedError

    def is_profitable(self, *args, **kwargs) -> bool:
        raise NotImplementedError

    def harvest(self, *args, **kwargs):
        raise NotImplementedError
