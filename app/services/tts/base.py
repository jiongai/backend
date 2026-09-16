"""Common contract implemented by every TTS provider."""

from abc import ABC, abstractmethod
from typing import Any


class TTSProvider(ABC):
    """Provider-neutral speech synthesis interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @property
    def is_enabled(self) -> bool:
        """Whether both the SDK and required configuration are available."""
        return False

    @abstractmethod
    async def generate(
        self,
        text: str,
        output_file: str,
        voice: str,
        speed: float = 1.0,
        **kwargs: Any,
    ) -> None:
        """Generate MP3 speech at ``output_file`` or raise an exception."""
