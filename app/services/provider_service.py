from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.provider import Provider
from app.repositories.game_repository import GameRepository
from app.repositories.provider_repository import ProviderRepository
from app.services.errors import BusinessRuleError, ResourceNotFoundError


class ProviderCatalogService:
    """Validates provider/game catalog entries before adapter use."""

    def __init__(self, db: Session) -> None:
        self.providers = ProviderRepository(db)
        self.games = GameRepository(db)

    def get_active_game(self, provider_code: str, external_game_id: str) -> tuple[Provider, Game]:
        provider = self.providers.get_by_code(provider_code)
        if provider is None:
            raise ResourceNotFoundError("Provider was not found.")
        if provider.status != "ACTIVE":
            raise BusinessRuleError("Provider is not active.")
        game = self.games.get_by_provider_and_external_id(
            provider.id, external_game_id
        )
        if game is None:
            raise ResourceNotFoundError("Game was not found for this provider.")
        if game.status != "ACTIVE":
            raise BusinessRuleError("Game is not active.")
        return provider, game
