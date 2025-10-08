-- SPDX-License-Identifier: Apache-2.0
-- Copyright 2025 Vova Orig

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    gifts_autorefresh BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    bot_token VARCHAR(128),
    notify_chat_id BIGINT,
    buy_target_id BIGINT,
    updated_at TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS api_profiles (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    api_id INTEGER NOT NULL,
    api_hash VARCHAR(128) NOT NULL,
    name VARCHAR(64),
    created_at TIMESTAMP,
    UNIQUE(user_id, api_id),
    UNIQUE(user_id, api_hash),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    api_profile_id INTEGER NOT NULL,
    phone VARCHAR(32) NOT NULL,
    username VARCHAR(64),
    first_name VARCHAR(128),
    stars_amount BIGINT NOT NULL DEFAULT 0,
    is_premium BOOLEAN NOT NULL DEFAULT 0,
    premium_until VARCHAR(64),
    session_path VARCHAR(256) NOT NULL,
    created_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    UNIQUE(user_id, phone),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(api_profile_id) REFERENCES api_profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    channel_id BIGINT NOT NULL,
    title VARCHAR(256),
    price_min BIGINT,
    price_max BIGINT,
    supply_min BIGINT,
    supply_max BIGINT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(user_id, channel_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_channels_user_id ON channels(user_id);
CREATE INDEX IF NOT EXISTS idx_channels_channel_id ON channels(channel_id);

CREATE TABLE IF NOT EXISTS session_tokens (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token VARCHAR(256) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

COMMIT;
