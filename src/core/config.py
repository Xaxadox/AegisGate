import logging
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Chave simetrica padrao para desenvolvimento e testes locais (32 url-safe base64 bytes)
DEFAULT_DEV_FERNET_KEY = "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="


class Settings(BaseSettings):
    """
    Configuracoes centralizadas da aplicacao com validacao de tipos e integridade.
    Segue a regra de Seguranca por Padrao: validacao estrita no startup.
    """
    # Identificacao e Ambiente
    PROJECT_NAME: str = Field(default="AegisGate", description="Nome do microsservico e projeto")
    ENVIRONMENT: str = Field(default="development", description="Ambiente: development, testing ou production")

    # Banco de Dados
    DB_USER: str = Field(default="api_user")
    DB_PASSWORD: str = Field(default="api_password")
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=3306)
    DB_NAME: str = Field(default="fraud_db")
    DATABASE_URL: Optional[str] = Field(default=None, description="URL direta de conexao com o banco (opcional)")

    # Redis
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)

    # Seguranca (JWT)
    JWT_SECRET_KEY: str = Field(default="dev-insecure-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    # Criptografia em Repouso (Fernet/AES-256) e Tokenizacao (HMAC-SHA256)
    AES_ENCRYPTION_KEY: Optional[str] = Field(default=None, description="Chave Fernet Base64 URL-safe de 32 bytes")
    TOKENIZATION_HMAC_SECRET: str = Field(default="dev-secret-tokenization-hmac-key")

    # MaxMind GeoIP
    GEOIP_DB_PATH: str = Field(default="./data/GeoLite2-City.mmdb")

    # Modelo de Machine Learning (Arquitetura Híbrida)
    ML_MODEL_PATH: str = Field(default="./src/ml/fraud_model.joblib", description="Caminho do artefato treinado de Machine Learning")

    # Credenciais homologadas de parceiros/lojistas (client_id: client_secret)
    MERCHANT_CREDENTIALS: dict[str, str] = Field(
        default_factory=lambda: {
            "loja_americanas": "segredo123",
            "loja_magalu": "segredo456",
            "loja_parceira_teste": "segredo_teste_123"
        },
        description="Dicionario de credenciais autorizadas de lojistas parceiros"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_security_invariants(self) -> "Settings":
        """
        Valida regras de integridade de seguranca por padrao.
        Falha no startup se configuracoes criticas forem inseguras em producao.
        """
        is_prod = self.ENVIRONMENT.lower() == "production"

        # Validacao da chave de criptografia Fernet (AES-256)
        if self.AES_ENCRYPTION_KEY:
            try:
                Fernet(self.AES_ENCRYPTION_KEY.encode() if isinstance(self.AES_ENCRYPTION_KEY, str) else self.AES_ENCRYPTION_KEY)
            except Exception as e:
                if is_prod:
                    raise ValueError(
                        f"Configuracao critica invalida: AES_ENCRYPTION_KEY deve ser uma chave Base64 URL-safe de 32 bytes. Erro: {e}"
                    )
                logger.warning(
                    "Chave AES_ENCRYPTION_KEY fornecida e invalida (%s). Utilizando chave estavel de desenvolvimento.",
                    e
                )
                self.AES_ENCRYPTION_KEY = DEFAULT_DEV_FERNET_KEY
        else:
            if is_prod:
                raise ValueError("Configuracao critica ausente: AES_ENCRYPTION_KEY e obrigatoria em ambiente de producao.")
            self.AES_ENCRYPTION_KEY = DEFAULT_DEV_FERNET_KEY

        # Validacao de segredos padrao em producao
        if is_prod:
            if "dev-insecure" in self.JWT_SECRET_KEY:
                raise ValueError("Configuracao critica insegura: JWT_SECRET_KEY nao pode utilizar o valor padrao de desenvolvimento em producao.")
            if "dev-secret" in self.TOKENIZATION_HMAC_SECRET:
                raise ValueError("Configuracao critica insegura: TOKENIZATION_HMAC_SECRET nao pode utilizar o valor padrao de desenvolvimento em producao.")

        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Retorna a URL formatada do banco de dados.
        Prioriza DATABASE_URL se informada; caso contrario, usa SQLite em dev/teste ou MySQL.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        if self.ENVIRONMENT.lower() in ("development", "testing"):
            return "sqlite:///./fraud_test.db"
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    def get_cipher_suite(self) -> Fernet:
        """Retorna a instancia configurada do Fernet para criptografia e descriptografia."""
        key = self.AES_ENCRYPTION_KEY or DEFAULT_DEV_FERNET_KEY
        return Fernet(key.encode() if isinstance(key, str) else key)


settings = Settings()
