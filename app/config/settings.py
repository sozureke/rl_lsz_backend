from pydantic_settings import BaseSettings

class Settings(BaseSettings):

	# deterministic | rl
	MODE: str = "deterministic"

	MODELS_DIR: str = "data/models"
	JSON_DIR: str = "data/json"

	TICK_DURATION: float = 1/3 # seconds for one tick
	GAME_DURATION_SECS: int = 5 * 60 # 5 minutes

	KILL_DELAY_TICKS: int = int(1.0 / TICK_DURATION)
	KILL_RADIUS: int = 4
	VOTE_DURATION_TICKS: int = 9
	HEAR_RADIUS: int = 6

	FOV_DISTANCE: int = 5
	FOV_ANGLE: float = 90

	LLM_MODEL: str = "mistral"
	# LLM_MODEL: str = "llama3:8b"
	LLM_CACHE_TTL: int = 60
	LLM_MAX_TOKENS: int = 10

	ENABLE_AUTO_TICK: bool = True

	GROUP_CHAT_RADIUS: int = 5
	GROUP_CHAT_MIN: int = 3
	GROUP_CHAT_DURATION_SECS: int = 15
	GROUP_CHAT_DURATION_TICKS: int = int(GROUP_CHAT_DURATION_SECS / TICK_DURATION)
	GROUP_CHAT_COOLDOWN: int = 5

	GOSSIP_PROB: float = 0.3
	GOSSIP_TRUST_THRESHOLD: float = 0.5
	SOUND_RADIUS: int = 5
	SOUND_TRUST_PENALTY: float = 0.2
	PANIC_DURATION: int = 10

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"

	@ property
	def MAX_TICKS(self) -> int:
		return int(self.GAME_DURATION_SECS / self.TICK_DURATION)


settings = Settings()