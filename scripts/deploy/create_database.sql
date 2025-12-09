-- ==========================================================
-- WOTCS — Estrutura de Banco de Dados
-- Feito pela maior cientista do universo: Washu Hakubi!
-- ==========================================================

-- CRIAR DATABASE (rode isso no psql ou PgAdmin)
-- CREATE DATABASE wotcs OWNER postgres ENCODING 'UTF8';

-- Depois use:
-- \c wotcs;

-- ============================
-- TABELA: user
-- ============================
CREATE TABLE IF NOT EXISTS "user" (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'member'
);

CREATE INDEX IF NOT EXISTS idx_user_username ON "user"(username);

-- ============================
-- TABELA: player
-- ============================
CREATE TABLE IF NOT EXISTS player (
    account_id BIGINT PRIMARY KEY,
    nickname VARCHAR(100) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_player_nickname ON player(nickname);

-- ============================
-- TABELA: garage_tank
-- ============================
CREATE TABLE IF NOT EXISTS garage_tank (
    id SERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL,
    tank_id BIGINT NOT NULL,
    tank_name VARCHAR(150) NOT NULL,
    tier INT NOT NULL,

    CONSTRAINT fk_garage_player
        FOREIGN KEY (account_id)
        REFERENCES player (account_id)
        ON DELETE CASCADE
);

-- Índices úteis para performance em listagens
CREATE INDEX IF NOT EXISTS idx_garage_account ON garage_tank(account_id);
CREATE INDEX IF NOT EXISTS idx_garage_tier ON garage_tank(tier);
CREATE INDEX IF NOT EXISTS idx_garage_tankid ON garage_tank(tank_id);
