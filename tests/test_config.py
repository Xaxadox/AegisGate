import pytest
from cryptography.fernet import Fernet
from src.core.config import Settings, DEFAULT_DEV_FERNET_KEY


def test_settings_carregamento_padrao_em_desenvolvimento():
    """Valida o carregamento dos padroes saudaveis em ambiente de desenvolvimento."""
    settings = Settings(ENVIRONMENT="development")
    assert settings.ENVIRONMENT == "development"
    assert settings.AES_ENCRYPTION_KEY == DEFAULT_DEV_FERNET_KEY
    assert "sqlite" in settings.sqlalchemy_database_url


def test_settings_chave_fernet_customizada_valida():
    """Valida que uma chave Base64 URL-safe de 32 bytes e aceita normalmente."""
    custom_key = Fernet.generate_key().decode()
    settings = Settings(ENVIRONMENT="development", AES_ENCRYPTION_KEY=custom_key)
    assert settings.AES_ENCRYPTION_KEY == custom_key
    cipher = settings.get_cipher_suite()
    encrypted = cipher.encrypt(b"teste")
    assert cipher.decrypt(encrypted) == b"teste"


def test_settings_bloqueia_producao_com_jwt_inseguro():
    """Regra de Seguranca: Em producao, proibe uso de JWT_SECRET_KEY padrao de dev."""
    valid_fernet = Fernet.generate_key().decode()
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            AES_ENCRYPTION_KEY=valid_fernet,
            JWT_SECRET_KEY="dev-insecure-secret-key-change-in-production",
            TOKENIZATION_HMAC_SECRET="segredo-producao-forte"
        )


def test_settings_bloqueia_producao_sem_chave_fernet():
    """Regra de Seguranca: Em producao, proibe boot sem chave AES/Fernet configurada."""
    with pytest.raises(ValueError, match="AES_ENCRYPTION_KEY"):
        Settings(
            ENVIRONMENT="production",
            AES_ENCRYPTION_KEY=None,
            JWT_SECRET_KEY="jwt-super-seguro-prod",
            TOKENIZATION_HMAC_SECRET="hmac-super-seguro-prod"
        )


def test_settings_bloqueia_producao_com_chave_fernet_invalida():
    """Regra de Seguranca: Em producao, proibe chaves Fernet com formato incorreto."""
    with pytest.raises(ValueError, match="Base64 URL-safe"):
        Settings(
            ENVIRONMENT="production",
            AES_ENCRYPTION_KEY="chave-invalida-sem-base64",
            JWT_SECRET_KEY="jwt-super-seguro-prod",
            TOKENIZATION_HMAC_SECRET="hmac-super-seguro-prod"
        )


def test_settings_url_mysql_em_producao():
    """Garante geracao correta de string de conexao MySQL em producao."""
    valid_fernet = Fernet.generate_key().decode()
    settings = Settings(
        ENVIRONMENT="production",
        AES_ENCRYPTION_KEY=valid_fernet,
        JWT_SECRET_KEY="jwt-super-seguro-prod",
        TOKENIZATION_HMAC_SECRET="hmac-super-seguro-prod",
        DB_USER="prod_user",
        DB_PASSWORD="prod_password",
        DB_HOST="mysql-cluster",
        DB_PORT=3306,
        DB_NAME="prod_fraud_db"
    )
    expected_url = "mysql+pymysql://prod_user:prod_password@mysql-cluster:3306/prod_fraud_db"
    assert settings.sqlalchemy_database_url == expected_url
