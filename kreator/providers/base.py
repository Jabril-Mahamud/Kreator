from abc import ABC, abstractmethod
from pathlib import Path

from kreator.core.config import KreatorConfig


class BaseProvider(ABC):
    def __init__(self, config: KreatorConfig, project_dir: Path) -> None:
        self.config = config
        self.project_dir = project_dir

    @abstractmethod
    def setup(self) -> None:
        """Provision infrastructure and deploy the application."""

    @abstractmethod
    def destroy(self) -> None:
        """Tear down all provisioned resources."""

    @abstractmethod
    def get_context(self) -> str:
        """Return the kubectl context for this provider."""
