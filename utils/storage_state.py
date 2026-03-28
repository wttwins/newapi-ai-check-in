#!/usr/bin/env python3
"""
storage state 相关工具
"""

import json
import os


def _normalize_cookie_expires(storage_state_data: dict) -> dict:
    """规范化 storage state 中 cookies 的 expires 字段。"""
    cookies = storage_state_data.get("cookies")
    if not isinstance(cookies, list):
        return storage_state_data

    for cookie in cookies:
        if not isinstance(cookie, dict) or "expires" not in cookie:
            continue

        expires = cookie.get("expires")
        if expires == -1:
            continue

        if isinstance(expires, float) and expires.is_integer():
            expires = int(expires)

        if isinstance(expires, int):
            if expires > 10**12:
                cookie["expires"] = expires // 1000
            elif expires > 0:
                continue
            else:
                cookie.pop("expires", None)
            continue

        cookie.pop("expires", None)

    return storage_state_data


def normalize_storage_state_file(cache_file_path: str, account_name: str) -> bool:
    """规范化已有 storage state 文件中的 cookies expires。"""
    if not cache_file_path or not os.path.exists(cache_file_path):
        return False

    try:
        with open(cache_file_path, encoding="utf-8") as file:
            storage_state_data = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"⚠️ {account_name}: Failed to load storage state file {cache_file_path}: {exc}")
        return False

    if not isinstance(storage_state_data, dict):
        print(f"⚠️ {account_name}: Storage state file must contain a JSON object: {cache_file_path}")
        return False

    normalized_state = _normalize_cookie_expires(storage_state_data)
    with open(cache_file_path, "w", encoding="utf-8") as file:
        json.dump(normalized_state, file, ensure_ascii=False, indent=2)

    print(f"ℹ️ {account_name}: Normalized storage state file: {cache_file_path}")
    return True


def ensure_storage_state_from_env(
    cache_file_path: str,
    account_name: str,
    username: str,
    env_name: str = "STORATE_STATES",
) -> bool:
    """当本地缓存不存在时，从环境变量恢复 storage state 文件。"""
    if not cache_file_path:
        print(f"⚠️ {account_name}: Skip restoring storage state because cache_file_path is empty")
        return False

    if os.path.exists(cache_file_path):
        print(f"⚠️ {account_name}: Skip restoring storage state because cache file already exists: {cache_file_path}")
        return False

    storage_states_str = os.getenv(env_name, "")
    if not storage_states_str:
        print(f"⚠️ {account_name}: Skip restoring storage state because {env_name} is empty or not set")
        return False

    try:
        storage_states = json.loads(storage_states_str)
    except json.JSONDecodeError as exc:
        print(f"⚠️ {account_name}: Failed to parse {env_name}: {exc}")
        return False

    if not isinstance(storage_states, dict):
        print(f"⚠️ {account_name}: {env_name} must be a JSON object")
        return False

    storage_state_data = storage_states.get(username)
    if storage_state_data is None:
        print(f"⚠️ {account_name}: Skip restoring storage state because '{username}' was not found in {env_name}")
        return False

    if isinstance(storage_state_data, str):
        try:
            storage_state_data = json.loads(storage_state_data)
        except json.JSONDecodeError as exc:
            print(f"⚠️ {account_name}: Storage state '{username}' is not valid JSON: {exc}")
            return False

    if not isinstance(storage_state_data, dict):
        print(f"⚠️ {account_name}: Storage state '{username}' must be a JSON object")
        return False

    storage_state_data = _normalize_cookie_expires(storage_state_data)

    cache_dir = os.path.dirname(cache_file_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)

    with open(cache_file_path, "w", encoding="utf-8") as file:
        json.dump(storage_state_data, file, ensure_ascii=False, indent=2)

    print(f"ℹ️ {account_name}: Restored storage state from {env_name} -> {username}")
    return True
